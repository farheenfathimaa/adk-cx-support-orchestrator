"""Intake agent — classifies incoming support tickets into categories.

Uses a SequentialAgent pipeline:
  1. ExtractorAgent: pulls key entities from the raw ticket text.
  2. ClassifierAgent: assigns a category + confidence score.
"""

from __future__ import annotations

from google.adk.agents import Agent, SequentialAgent

from adk_cx_support_orchestrator.core.config import settings

# ---------------------------------------------------------------------------
# Step 1 – Extract key facts from the ticket
# ---------------------------------------------------------------------------

_extractor = Agent(
    name="ExtractorAgent",
    model=settings.model_name,
    description="Extracts key entities and intent from a raw support ticket.",
    instruction="""\
You are a ticket analyst. Given a customer support ticket, extract:
1. The customer's core issue in one sentence.
2. Any mentioned product names, order IDs, or account details.
3. The apparent urgency (low / medium / high).

Write your output as a concise bullet list. Do NOT classify the category yet.
""",
    output_key="extracted_facts",
)

# ---------------------------------------------------------------------------
# Step 2 – Classify into one of the four categories
# ---------------------------------------------------------------------------

_classifier = Agent(
    name="ClassifierAgent",
    model=settings.model_name,
    description="Classifies the extracted ticket facts into a support category.",
    instruction="""\
You are a support ticket classifier. Given extracted ticket facts, determine the
single best category from: billing, technical, refund, general.

Output EXACTLY this JSON (no markdown fences):
{
  "category": "<billing|technical|refund|general>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one-sentence justification>"
}

Confidence guidelines:
- 0.9+ : crystal-clear intent (e.g. "I want a refund").
- 0.7-0.89 : strong signal but slightly ambiguous.
- 0.5-0.69 : ambiguous, could belong to multiple categories.
- Below 0.5 : very unclear — default to "general" with low confidence.
""",
    output_key="classification",
)

# ---------------------------------------------------------------------------
# Composed sequential pipeline
# ---------------------------------------------------------------------------

intake_agent = SequentialAgent(
    name="IntakePipeline",
    description=(
        "Two-step pipeline that extracts key facts from a support ticket "
        "then classifies it into a category (billing, technical, refund, "
        "general) with a confidence score."
    ),
    sub_agents=[_extractor, _classifier],
)
