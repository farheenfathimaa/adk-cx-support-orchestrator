"""Specialist sub-agents used in the parallel fan-out / gather pattern.

Each specialist independently scores its confidence that the ticket belongs
to its domain.  The orchestrator collects scores and picks the winner
deterministically (highest confidence, with tie-breaking).
"""

from __future__ import annotations

from google.adk.agents import Agent

from adk_cx_support_orchestrator.core.config import settings
from adk_cx_support_orchestrator.tools import knowledge_base_search

# Each specialist writes to a *unique* output_key (ADK requirement for
# ParallelAgent — no key collisions).

billing_agent = Agent(
    name="BillingSpecialist",
    model=settings.model_name,
    description="Scores confidence that a ticket is a billing issue.",
    instruction="""\
You are a billing specialist. Given a support ticket, determine whether it is
a billing-related issue (payments, subscriptions, invoices, plan changes).

Search the knowledge base if it helps you decide.

Output EXACTLY this JSON:
{
  "category": "billing",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}
""",
    output_key="billing_score",
    tools=[knowledge_base_search],
)

technical_agent = Agent(
    name="TechnicalSpecialist",
    model=settings.model_name,
    description="Scores confidence that a ticket is a technical issue.",
    instruction="""\
You are a technical support specialist. Given a support ticket, determine
whether it is a technical issue (bugs, errors, connectivity, performance).

Search the knowledge base if it helps you decide.

Output EXACTLY this JSON:
{
  "category": "technical",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}
""",
    output_key="technical_score",
    tools=[knowledge_base_search],
)

refund_agent = Agent(
    name="RefundSpecialist",
    model=settings.model_name,
    description="Scores confidence that a ticket is a refund request.",
    instruction="""\
You are a refund specialist. Given a support ticket, determine whether it is
a refund or cancellation request.

Search the knowledge base for refund policy if it helps you decide.

Output EXACTLY this JSON:
{
  "category": "refund",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}
""",
    output_key="refund_score",
    tools=[knowledge_base_search],
)

SPECIALIST_AGENTS = [billing_agent, technical_agent, refund_agent]
