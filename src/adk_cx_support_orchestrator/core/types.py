"""Shared domain types."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TicketCategory(str, Enum):
    """Canonical support ticket categories."""

    BILLING = "billing"
    TECHNICAL = "technical"
    REFUND = "refund"
    GENERAL = "general"


class TicketInput(BaseModel):
    """Incoming support ticket."""

    ticket_id: str
    text: str
    customer_id: str | None = None


class SpecialistScore(BaseModel):
    """Confidence score returned by a specialist sub-agent."""

    category: TicketCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class RoutingResult(BaseModel):
    """Deterministic routing decision after fan-out/gather."""

    category: TicketCategory
    confidence: float
    specialist_scores: list[SpecialistScore] = Field(default_factory=list)


class CriticVerdict(BaseModel):
    """Output of the critic agent in the draft/critic loop."""

    passed: bool
    tone_ok: bool = False
    accuracy_ok: bool = False
    policy_compliant: bool = False
    feedback: str = ""


class EvalMetrics(BaseModel):
    """Aggregated evaluation metrics."""

    total_tickets: int
    correct_routes: int
    routing_precision: float
    routing_recall: float
    avg_loop_count: float
    tool_call_accuracy: float
    tool_trajectory_scores: list[float] = Field(default_factory=list)
