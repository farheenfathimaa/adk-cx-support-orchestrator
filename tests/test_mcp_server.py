"""Tests for the mock MCP server (no API key required)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SERVER_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "adk_cx_support_orchestrator"
    / "mcp_server"
    / "server.py"
)


def _call_server(requests: list[dict]) -> list[dict]:
    """Send JSON-RPC requests to the MCP server via stdio."""
    payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    proc = subprocess.run(
        [sys.executable, str(SERVER_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"Server exited with {proc.returncode}: {proc.stderr}"
    return [json.loads(line) for line in proc.stdout.strip().splitlines()]


def test_initialize() -> None:
    responses = _call_server(
        [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}]
    )
    assert responses[0]["id"] == 1
    assert responses[0]["result"]["serverInfo"]["name"] == "cx-knowledge-crm-server"
    assert "tools" in responses[0]["result"]["capabilities"]


def test_tools_list() -> None:
    responses = _call_server(
        [{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}]
    )
    names = {t["name"] for t in responses[0]["result"]["tools"]}
    assert names == {"knowledge_base_search", "get_customer_info"}


def test_knowledge_base_search() -> None:
    responses = _call_server(
        [
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "knowledge_base_search",
                    "arguments": {"query": "refund policy", "category": "refund"},
                },
            }
        ]
    )
    result = responses[0]["result"]
    text = result["content"][0]["text"]
    articles = json.loads(text)
    assert any(a["id"] == "refund_policy" for a in articles)


def test_get_customer_info() -> None:
    responses = _call_server(
        [
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_customer_info",
                    "arguments": {"customer_id": "CUST-001"},
                },
            }
        ]
    )
    text = responses[0]["result"]["content"][0]["text"]
    customer = json.loads(text)
    assert customer["customer_id"] == "CUST-001"
    assert customer["name"] == "Alice Johnson"


def test_unknown_customer_returns_error() -> None:
    responses = _call_server(
        [
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_customer_info",
                    "arguments": {"customer_id": "CUST-999"},
                },
            }
        ]
    )
    text = responses[0]["result"]["content"][0]["text"]
    assert "not found" in json.loads(text)["error"].lower()


def test_unknown_method() -> None:
    responses = _call_server(
        [{"jsonrpc": "2.0", "id": 6, "method": "bogus/method", "params": {}}]
    )
    assert responses[0]["error"]["code"] == -32601