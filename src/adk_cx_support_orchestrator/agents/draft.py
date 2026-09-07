"""Draft response agent — generates the initial customer reply.

This agent is the "generator" in the generator/critic loop.  It looks up
relevant knowledge-base articles and customer CRM data to ground its
response in facts.
"""

from __future__ import annotations

from google.adk.agents import Agent

from adk_cx_support_orchestrator.core.config import settings
from adk_cx_support_orchestrator.tools import knowledge_base_search, get_customer_info

draft_agent = Agent(
    name="DraftResponseAgent",
    model=settings.model_name,
    description="Drafts a customer-support reply grounded in KB and CRM data.",
    instruction="""\
You are a customer-support drafter. Given:
- The original ticket text (in state key 'original_ticket')
- The classified category (in state key 'final_category')
- Any specialist reasoning (in state keys 'billing_score', 'technical_score', 'refund_score')

Do the following:
1. Call 'knowledge_base_search' with a query derived from the ticket to find
   relevant FAQ/policy articles.
2. If a customer_id is present in the ticket, call 'get_customer_info' to
   look up their account and order history.
3. Draft a clear, professional, empathetic reply that:
   - Acknowledges the customer's issue.
   - Provides actionable steps or policy information.
   - References specific order numbers or account details when available.
   - Ends with a follow-up offer ("Let me know if you need anything else").

Your entire output must be ONLY the draft reply text — no JSON, no meta-commentary.
""",
    output_key="draft_response",
    tools=[knowledge_base_search, get_customer_info],
)
