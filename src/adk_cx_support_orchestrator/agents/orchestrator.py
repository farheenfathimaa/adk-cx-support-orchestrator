"""Orchestrator — composes all agents into the full triage workflow.

Workflow:
  1. IntakePipeline  (SequentialAgent) — extract + classify.
  2. RoutingDecision (BaseAgent)        — deterministic parse + branch.
  3. [If ambiguous] ParallelAgent fan-out to 3 specialists → gather.
  4. LoopAgent (Draft ↔ Critic) up to MAX_CRITIC_ITERATIONS iterations.
  5. FinalResponse    (BaseAgent)       — deterministic assembly.
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import aclosing
from typing import AsyncGenerator

from google.adk.agents import (
    Agent,
    BaseAgent,
    ParallelAgent,
    LoopAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from adk_cx_support_orchestrator.agents.intake import intake_agent
from adk_cx_support_orchestrator.agents.specialists import SPECIALIST_AGENTS
from adk_cx_support_orchestrator.agents.draft import draft_agent
from adk_cx_support_orchestrator.agents.critic import critic_agent
from adk_cx_support_orchestrator.core.config import settings
from adk_cx_support_orchestrator.core.exceptions import ClassificationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: extract JSON from agent output (strips markdown fences, etc.)
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from arbitrary LLM output."""
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        raise ClassificationError(f"No JSON found in output: {text[:300]!r}")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# Deterministic routing agent (non-LLM)
# ---------------------------------------------------------------------------


class RoutingDecision(BaseAgent):
    """Parses the classification output and decides whether to fan out.

    Writes to session state:
      - 'final_category'  : the chosen category string
      - 'is_ambiguous'    : 'true' or 'false'
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raw = ctx.session.state.get("classification", "")
        try:
            parsed = _extract_json(str(raw))
            confidence = float(parsed.get("confidence", 0))
            category = parsed.get("category", "general")
        except (json.JSONDecodeError, ClassificationError, ValueError) as exc:
            logger.warning("Classification parse failed, defaulting to general: %s", exc)
            confidence = 0.0
            category = "general"

        is_ambiguous = confidence < settings.ambiguity_threshold
        ctx.session.state["final_category"] = category
        ctx.session.state["is_ambiguous"] = "true" if is_ambiguous else "false"

        logger.info(
            "RoutingDecision: category=%s confidence=%.2f ambiguous=%s",
            category,
            confidence,
            is_ambiguous,
        )

        yield Event(
            author=self.name,
            content={
                "role": "model",
                "parts": [{"text": f"Routed to {category} (confidence {confidence:.2f})"}],
            },
        )


# ---------------------------------------------------------------------------
# Conditional specialist fan-out (deterministic gate)
# ---------------------------------------------------------------------------


class ConditionalSpecialistFanOut(BaseAgent):
    """Runs the ParallelAgent fan-out ONLY when the ticket is ambiguous.

    Checks ``ctx.session.state['is_ambiguous']``:
      - ``"true"``  → invoke the parallel specialist agents inline.
      - otherwise  → skip (no LLM cost for confident classifications).
    """

    parallel_agent: ParallelAgent

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if ctx.session.state.get("is_ambiguous") != "true":
            logger.info(
                "ConditionalSpecialistFanOut: skipping fan-out (not ambiguous)"
            )
            yield Event(
                author=self.name,
                content={
                    "role": "model",
                    "parts": [{"text": "Skipping specialist fan-out — classification is confident."}],
                },
            )
            return

        logger.info(
            "ConditionalSpecialistFanOut: ambiguous ticket — fanning out to specialists"
        )
        async with aclosing(self.parallel_agent.run_async(ctx)) as agen:
            async for event in agen:
                yield event


# ---------------------------------------------------------------------------
# Gather agent (deterministic — picks best specialist score)
# ---------------------------------------------------------------------------


class GatherSpecialistScores(BaseAgent):
    """Parses specialist scores from parallel fan-out and picks the winner.

    Writes to session state:
      - 'final_category'  : overridden with the specialist winner
      - 'specialist_detail': human-readable summary
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        scores: dict[str, float] = {}
        for key in ("billing_score", "technical_score", "refund_score"):
            raw = ctx.session.state.get(key, "")
            try:
                parsed = _extract_json(str(raw))
                scores[parsed["category"]] = float(parsed.get("confidence", 0))
            except Exception:
                logger.warning("Failed to parse specialist score for key=%s", key)

        if not scores:
            # Fall back to the original classification
            winner = ctx.session.state.get("final_category", "general")
            detail = "No specialist scores parsed — falling back to original classification."
        else:
            winner = max(scores, key=scores.get)  # type: ignore[arg-type]
            detail = f"Specialist scores: {scores}. Winner: {winner} ({scores[winner]:.2f})"

        ctx.session.state["final_category"] = winner
        ctx.session.state["specialist_detail"] = detail

        logger.info("GatherSpecialistScores: %s", detail)

        yield Event(
            author=self.name,
            content={"role": "model", "parts": [{"text": detail}]},
        )


# ---------------------------------------------------------------------------
# Critic status checker (deterministic — controls loop termination)
# ---------------------------------------------------------------------------


class CriticStatusChecker(BaseAgent):
    """Checks the critic verdict and escalates if the draft passes or the
    iteration budget is exhausted.

    The critic writes JSON to state['critic_verdict'].  We parse it and set
    ``EventActions(escalate=True)`` when:
      - The draft passed (passed == true), OR
      - We've already hit max iterations (counted via 'loop_iteration').
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raw = ctx.session.state.get("critic_verdict", "")
        iteration = int(ctx.session.state.get("loop_iteration", 0))

        try:
            verdict = _extract_json(str(raw))
            passed = bool(verdict.get("passed", False))
        except Exception:
            passed = False
            verdict = {}

        iteration += 1
        ctx.session.state["loop_iteration"] = str(iteration)

        should_stop = passed or iteration >= settings.max_critic_iterations

        if should_stop:
            reason = "passed" if passed else f"loop limit ({iteration})"
            logger.info("CriticStatusChecker: stopping loop — %s", reason)
        else:
            logger.info(
                "CriticStatusChecker: iteration %d/%d — retrying",
                iteration,
                settings.max_critic_iterations,
            )

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop),
            content={
                "role": "model",
                "parts": [{"text": f"Loop status: {'stop' if should_stop else 'continue'} (iter {iteration})"}],
            },
        )


# ---------------------------------------------------------------------------
# Final response assembler (deterministic)
# ---------------------------------------------------------------------------


class FinalResponseAssembler(BaseAgent):
    """Assembles the final response from the (possibly iterated) draft."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        draft = ctx.session.state.get("draft_response", "")
        raw_verdict = ctx.session.state.get("critic_verdict", "")
        iteration = ctx.session.state.get("loop_iteration", "1")

        try:
            verdict = _extract_json(str(raw_verdict))
            passed = bool(verdict.get("passed", False))
        except Exception:
            passed = False

        if not passed:
            # Loop exhausted without approval — add disclaimer
            final = (
                f"{draft}\n\n"
                "---\n"
                "*This response was auto-generated and may need review. "
                "A human agent will follow up shortly.*"
            )
            logger.warning(
                "FinalResponseAssembler: draft NOT approved after %s iterations",
                iteration,
            )
        else:
            final = draft
            logger.info("FinalResponseAssembler: draft approved on iteration %s", iteration)

        ctx.session.state["final_response"] = final

        yield Event(
            author=self.name,
            content={"role": "model", "parts": [{"text": final}]},
        )


# ---------------------------------------------------------------------------
# Assemble the full orchestration graph
# ---------------------------------------------------------------------------

# Parallel specialist fan-out (only used when ticket is ambiguous)
_parallel_specialists = ParallelAgent(
    name="ParallelSpecialistFanOut",
    description="Fans out to billing, technical, and refund specialists in parallel.",
    sub_agents=SPECIALIST_AGENTS,
)

# Draft ↔ Critic refinement loop
_draft_critic_loop = LoopAgent(
    name="DraftCriticLoop",
    description=(
        "Iteratively drafts and critiques a customer reply. Stops when the "
        "critic passes the draft or max iterations are hit."
    ),
    max_iterations=settings.max_critic_iterations,
    sub_agents=[draft_agent, critic_agent, CriticStatusChecker(name="LoopTerminator")],
)

# Full orchestrator
orchestrator_agent = SequentialAgent(
    name="CXSupportOrchestrator",
    description=(
        "End-to-end customer support triage: intake classification, "
        "ambiguous-ticket fan-out, draft/critic refinement loop, and "
        "final response assembly."
    ),
    sub_agents=[
        intake_agent,                  # Step 1: Sequential extract + classify
        RoutingDecision(name="Router"),  # Step 2: deterministic routing decision
        ConditionalSpecialistFanOut(   # Step 3: fan-out ONLY if ambiguous
            name="ConditionalSpecialistFanOut",
            parallel_agent=_parallel_specialists,
        ),
        GatherSpecialistScores(name="Gatherer"),  # Step 4: pick winner (or fall back)
        _draft_critic_loop,            # Step 5: draft ↔ critic loop
        FinalResponseAssembler(name="FinalAssembler"),  # Step 6: assemble
    ],
)
