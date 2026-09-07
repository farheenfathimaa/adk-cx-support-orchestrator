"""Tests for deterministic orchestration helpers (no API key required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "src")
)

from adk_cx_support_orchestrator.agents.orchestrator import _extract_json
from adk_cx_support_orchestrator.core.types import TicketCategory, RoutingResult, SpecialistScore


def test_extract_json_from_plain_object() -> None:
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_markdown_fences() -> None:
    raw = "Here is the result:\n```json\n{\"category\": \"billing\", \"confidence\": 0.9}\n```"
    assert _extract_json(raw) == {"category": "billing", "confidence": 0.9}


def test_extract_json_with_surrounding_text() -> None:
    raw = 'Reasoning paragraph before. {"passed": true, "feedback": "ok"} Some text after.'
    assert _extract_json(raw)["passed"] is True


def test_extract_json_no_json_found() -> None:
    with pytest.raises(Exception):
        _extract_json("no json here at all")


def test_routing_result_model() -> None:
    scores = [
        SpecialistScore(category=TicketCategory.BILLING, confidence=0.4, reasoning="low"),
        SpecialistScore(category=TicketCategory.TECHNICAL, confidence=0.9, reasoning="high"),
    ]
    result = RoutingResult(
        category=TicketCategory.TECHNICAL,
        confidence=0.9,
        specialist_scores=scores,
    )
    assert result.category == TicketCategory.TECHNICAL
    assert len(result.specialist_scores) == 2


def test_specialist_score_bounds() -> None:
    with pytest.raises(Exception):
        SpecialistScore(category=TicketCategory.BILLING, confidence=1.5)