#!/usr/bin/env python3
"""Mock MCP (Model Context Protocol) server for Knowledge Base + CRM.

Runs as a stdio subprocess consumed by ADK's McpToolset.
Implements JSON-RPC 2.0 over stdin/stdout.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp_server")

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

KNOWLEDGE_BASE: dict[str, dict[str, str]] = {
    "billing_change_plan": {
        "id": "billing_change_plan",
        "category": "billing",
        "title": "Changing Your Subscription Plan",
        "content": (
            "To change your plan, go to Settings > Subscription > Change Plan. "
            "Upgrades take effect immediately with prorated billing. "
            "Downgrades take effect at the start of your next billing cycle. "
            "If you experience issues, contact billing-support@example.com."
        ),
    },
    "billing_payment_failed": {
        "id": "billing_payment_failed",
        "category": "billing",
        "title": "Payment Failed – What To Do",
        "content": (
            "If your payment failed, please: 1) Verify your card details are "
            "correct, 2) Check your card hasn't expired, 3) Ensure sufficient "
            "funds. You can update your payment method at Settings > Billing > "
            "Payment Methods. After 3 failed attempts your account may be "
            "suspended."
        ),
    },
    "technical_password_reset": {
        "id": "technical_password_reset",
        "category": "technical",
        "title": "Password Reset Instructions",
        "content": (
            "To reset your password: click 'Forgot Password' on the login page, "
            "enter your registered email, and follow the link in the reset "
            "email. The link expires in 24 hours. If you don't receive the "
            "email, check your spam folder or contact support."
        ),
    },
    "technical_api_rate_limit": {
        "id": "technical_api_rate_limit",
        "category": "technical",
        "title": "API Rate Limiting",
        "content": (
            "Free-tier accounts are limited to 100 requests/minute. Pro plans "
            "allow 1,000 req/min. If you're hitting limits, implement "
            "exponential backoff or upgrade your plan. Rate-limit headers are "
            "included in every API response (X-RateLimit-Remaining)."
        ),
    },
    "technical_connection_issues": {
        "id": "technical_connection_issues",
        "category": "technical",
        "title": "Troubleshooting Connection Issues",
        "content": (
            "If you're experiencing connection problems: 1) Check your internet "
            "connection, 2) Try clearing browser cache, 3) Disable VPN/proxy, "
            "4) Try a different browser. If the issue persists, check our "
            "status page at status.example.com."
        ),
    },
    "refund_policy": {
        "id": "refund_policy",
        "category": "refund",
        "title": "Refund Policy",
        "content": (
            "We offer full refunds within 30 days of purchase. Between 30-90 "
            "days, a prorated refund may be issued at our discretion. After 90 "
            "days, no refunds are available. Refunds are processed to the "
            "original payment method within 5-10 business days."
        ),
    },
    "refund_process": {
        "id": "refund_process",
        "category": "refund",
        "title": "How to Request a Refund",
        "content": (
            "To request a refund: 1) Go to Settings > Billing > Transaction "
            "History, 2) Select the transaction, 3) Click 'Request Refund', "
            "4) Provide a reason. You can also email refunds@example.com with "
            "your order number."
        ),
    },
    "general_account_deletion": {
        "id": "general_account_deletion",
        "category": "general",
        "title": "Account Deletion",
        "content": (
            "To delete your account, go to Settings > Account > Delete Account. "
            "This action is irreversible. All data will be permanently removed "
            "within 30 days. Active subscriptions will be cancelled and any "
            "remaining balance will be refunded."
        ),
    },
    "general_contact_support": {
        "id": "general_contact_support",
        "category": "general",
        "title": "Contacting Support",
        "content": (
            "You can reach our support team via: email (support@example.com), "
            "live chat (Mon-Fri 9am-6pm EST), or phone (1-800-555-0123). "
            "Average response time is under 4 hours for email and under 2 "
            "minutes for live chat."
        ),
    },
    "general_features": {
        "id": "general_features",
        "category": "general",
        "title": "Product Features Overview",
        "content": (
            "Our platform offers: real-time analytics dashboard, automated "
            "reporting, team collaboration tools, API access (Pro+), custom "
            "integrations, and 24/7 priority support (Enterprise). See our "
            "features page for a detailed comparison."
        ),
    },
}

CRM_DATABASE: dict[str, dict[str, Any]] = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "Alice Johnson",
        "plan": "Pro",
        "status": "active",
        "orders": [
            {
                "order_id": "ORD-1001",
                "date": "2026-01-15",
                "amount": 299.99,
                "status": "delivered",
                "item": "Enterprise Widget",
            },
            {
                "order_id": "ORD-1042",
                "date": "2026-03-20",
                "amount": 49.99,
                "status": "delivered",
                "item": "Widget Pro License",
            },
        ],
        "recent_tickets": 1,
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Bob Martinez",
        "plan": "Free",
        "status": "active",
        "orders": [
            {
                "order_id": "ORD-1099",
                "date": "2026-02-01",
                "amount": 0.0,
                "status": "active",
                "item": "Free Trial",
            },
        ],
        "recent_tickets": 0,
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Carol Chen",
        "plan": "Enterprise",
        "status": "active",
        "orders": [
            {
                "order_id": "ORD-1055",
                "date": "2025-12-10",
                "amount": 1499.99,
                "status": "delivered",
                "item": "Enterprise Suite Annual",
            },
            {
                "order_id": "ORD-1078",
                "date": "2026-04-01",
                "amount": 199.99,
                "status": "processing",
                "item": "Additional Storage 500GB",
            },
        ],
        "recent_tickets": 3,
    },
    "CUST-004": {
        "customer_id": "CUST-004",
        "name": "David Kim",
        "plan": "Pro",
        "status": "suspended",
        "orders": [
            {
                "order_id": "ORD-1012",
                "date": "2026-01-05",
                "amount": 299.99,
                "status": "refunded",
                "item": "Pro Annual Plan",
            },
        ],
        "recent_tickets": 5,
    },
}

# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------


def _handle_initialize(_params: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "cx-knowledge-crm-server", "version": "1.0.0"},
    }


def _handle_tools_list(_params: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": "knowledge_base_search",
                "description": (
                    "Search the customer support knowledge base for FAQ articles "
                    "and policy documents. Returns matching articles with their "
                    "content."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query describing the customer's issue "
                                "(e.g. 'refund policy', 'password reset')"
                            ),
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Optional category filter: billing, technical, "
                                "refund, general"
                            ),
                            "enum": [
                                "billing",
                                "technical",
                                "refund",
                                "general",
                            ],
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_customer_info",
                "description": (
                    "Retrieve customer profile and order history from the CRM. "
                    "Returns customer details, subscription status, and recent "
                    "orders."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {
                            "type": "string",
                            "description": "The customer ID (e.g. CUST-001)",
                        }
                    },
                    "required": ["customer_id"],
                },
            },
        ]
    }


def _kb_search(args: dict[str, Any]) -> str:
    query = args.get("query", "").lower()
    category_filter = args.get("category")

    results: list[dict[str, str]] = []
    for article in KNOWLEDGE_BASE.values():
        if category_filter and article["category"] != category_filter:
            continue
        searchable = f"{article['title']} {article['content']}".lower()
        if any(word in searchable for word in query.split()):
            results.append(article)

    if not results:
        # Fallback: return all articles in the category or the top 3
        if category_filter:
            results = [
                a
                for a in KNOWLEDGE_BASE.values()
                if a["category"] == category_filter
            ]
        else:
            results = list(KNOWLEDGE_BASE.values())[:3]

    return json.dumps(results, indent=2)


def _get_customer(args: dict[str, Any]) -> str:
    cid = args.get("customer_id", "")
    customer = CRM_DATABASE.get(cid)
    if customer is None:
        return json.dumps(
            {"error": f"Customer {cid!r} not found in CRM."}, indent=2
        )
    return json.dumps(customer, indent=2)


def _handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "knowledge_base_search":
        result_text = _kb_search(args)
    elif name == "get_customer_info":
        result_text = _get_customer(args)
    else:
        return {
            "content": [
                {"type": "text", "text": f"Unknown tool: {name!r}"}
            ],
            "isError": True,
        }

    return {"content": [{"type": "text", "text": result_text}]}


HANDLERS: dict[str, Any] = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("MCP server starting on stdin/stdout")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            logger.error("Invalid JSON: %s", line[:200])
            continue

        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        handler = HANDLERS.get(method)
        if handler is None:
            response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        else:
            try:
                result = handler(params)
                response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            except Exception as exc:
                logger.exception("Handler error for %s", method)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(exc)},
                }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
