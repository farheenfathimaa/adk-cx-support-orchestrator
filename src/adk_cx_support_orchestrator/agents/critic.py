"""Critic agent — evaluates the draft reply against a quality rubric.

This agent is the "critic" in the generator/critic loop.  It scores the
draft on three dimensions (tone, accuracy, policy compliance) and either
passes or fails it.  The LoopAgent reads its output to decide whether to
iterate or stop.
"""

from __future__ import annotations

from google.adk.agents import Agent

from adk_cx_support_orchestrator.core.config import settings

critic_agent = Agent(
    name="CriticAgent",
    model=settings.model_name,
    description="Evaluates a draft reply against tone, accuracy, and policy rubrics.",
    instruction="""\
You are a quality-assurance critic for customer-support responses. Given the
draft reply (in state key 'draft_response') and the original ticket (in state
key 'original_ticket'), evaluate the draft on three criteria:

1. **Tone** — Is it professional, empathetic, and free of jargon?
2. **Accuracy** — Does it address the actual issue? Are facts consistent
   with what a support agent would know?
3. **Policy compliance** — Does it avoid promising things outside company
   policy (e.g. unconditional refunds beyond 30 days, unauthorised discounts)?

Output EXACTLY this JSON (no markdown fences):
{
  "passed": true|false,
  "tone_ok": true|false,
  "accuracy_ok": true|false,
  "policy_compliant": true|false,
  "feedback": "<specific improvement suggestions if passed is false, or 'Looks good.' if passed>"
}

Pass the draft only if ALL THREE criteria are true.  Be strict — the goal is
to catch issues before the customer sees the reply.
""",
    output_key="critic_verdict",
)
