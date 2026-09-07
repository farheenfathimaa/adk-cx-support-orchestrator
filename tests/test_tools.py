"""Tests for the KB/CRM FunctionTools (no API key required)."""

from __future__ import annotations

import json

from adk_cx_support_orchestrator.tools.crm_tools import (
    knowledge_base_search,
    get_customer_info,
)


def test_kb_search_by_category() -> None:
    result = json.loads(knowledge_base_search("password reset", category="technical"))
    assert any(a["id"] == "technical_password_reset" for a in result)


def test_kb_search_fallback_returns_something() -> None:
    result = json.loads(knowledge_base_search("zzzzz-no-match-zzzz"))
    assert len(result) > 0


def test_crm_lookup_known_customer() -> None:
    customer = json.loads(get_customer_info("CUST-001"))
    assert customer["customer_id"] == "CUST-001"
    assert customer["plan"] == "Pro"


def test_crm_lookup_unknown_customer() -> None:
    error = json.loads(get_customer_info("CUST-999"))
    assert "not found" in error["error"].lower()