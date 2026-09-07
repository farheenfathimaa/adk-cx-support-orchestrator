"""Mock CRM and Knowledge-Base tools for direct (non-MCP) invocation.

These are plain Python functions that ADK auto-converts into FunctionTools
via their docstrings and type annotations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline mock data (mirrors the MCP server for consistency)
# ---------------------------------------------------------------------------

_KNOWLEDGE_BASE: dict[str, dict[str, str]] = {
    "billing_change_plan": {
        "id": "billing_change_plan",
        "category": "billing",
        "title": "Changing Your Subscription Plan",
        "content": (
            "To change your plan, go to Settings > Subscription > Change Plan. "
            "Upgrades take effect immediately with prorated billing. "
            "Downgrades take effect at the start of your next billing cycle."
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
            "Payment Methods."
        ),
    },
    "technical_password_reset": {
        "id": "technical_password_reset",
        "category": "technical",
        "title": "Password Reset Instructions",
        "content": (
            "To reset your password: click 'Forgot Password' on the login page, "
            "enter your registered email, and follow the link in the reset "
            "email. The link expires in 24 hours."
        ),
    },
    "technical_api_rate_limit": {
        "id": "technical_api_rate_limit",
        "category": "technical",
        "title": "API Rate Limiting",
        "content": (
            "Free-tier accounts are limited to 100 requests/minute. Pro plans "
            "allow 1,000 req/min. Implement exponential backoff or upgrade."
        ),
    },
    "technical_connection_issues": {
        "id": "technical_connection_issues",
        "category": "technical",
        "title": "Troubleshooting Connection Issues",
        "content": (
            "Try: 1) Check internet, 2) Clear browser cache, 3) Disable VPN, "
            "4) Try different browser. Check status.example.com."
        ),
    },
    "refund_policy": {
        "id": "refund_policy",
        "category": "refund",
        "title": "Refund Policy",
        "content": (
            "Full refunds within 30 days. Prorated 30-90 days at discretion. "
            "No refunds after 90 days. Processed in 5-10 business days."
        ),
    },
    "refund_process": {
        "id": "refund_process",
        "category": "refund",
        "title": "How to Request a Refund",
        "content": (
            "Go to Settings > Billing > Transaction History, select the "
            "transaction, click 'Request Refund', provide a reason."
        ),
    },
    "general_account_deletion": {
        "id": "general_account_deletion",
        "category": "general",
        "title": "Account Deletion",
        "content": (
            "Go to Settings > Account > Delete Account. Irreversible. Data "
            "removed within 30 days. Active subscriptions cancelled."
        ),
    },
    "general_contact_support": {
        "id": "general_contact_support",
        "category": "general",
        "title": "Contacting Support",
        "content": (
            "Email: support@example.com. Live chat Mon-Fri 9am-6pm EST. "
            "Phone: 1-800-555-0123."
        ),
    },
    "general_features": {
        "id": "general_features",
        "category": "general",
        "title": "Product Features Overview",
        "content": (
            "Real-time analytics, automated reporting, team collaboration, "
            "API access (Pro+), custom integrations, 24/7 support (Enterprise)."
        ),
    },
}

_CRM_DATABASE: dict[str, dict[str, Any]] = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "Alice Johnson",
        "plan": "Pro",
        "status": "active",
        "orders": [
            {"order_id": "ORD-1001", "date": "2026-01-15", "amount": 299.99, "status": "delivered"},
            {"order_id": "ORD-1042", "date": "2026-03-20", "amount": 49.99, "status": "delivered"},
        ],
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Bob Martinez",
        "plan": "Free",
        "status": "active",
        "orders": [
            {"order_id": "ORD-1099", "date": "2026-02-01", "amount": 0.0, "status": "active"},
        ],
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Carol Chen",
        "plan": "Enterprise",
        "status": "active",
        "orders": [
            {"order_id": "ORD-1055", "date": "2025-12-10", "amount": 1499.99, "status": "delivered"},
            {"order_id": "ORD-1078", "date": "2026-04-01", "amount": 199.99, "status": "processing"},
        ],
    },
    "CUST-004": {
        "customer_id": "CUST-004",
        "name": "David Kim",
        "plan": "Pro",
        "status": "suspended",
        "orders": [
            {"order_id": "ORD-1012", "date": "2026-01-05", "amount": 299.99, "status": "refunded"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Tool functions (consumed by ADK as FunctionTools)
# ---------------------------------------------------------------------------


def knowledge_base_search(query: str, category: str = "") -> str:
    """Search the customer support knowledge base for FAQ articles.

    Args:
        query: Natural-language search query describing the issue.
        category: Optional category filter (billing, technical, refund, general).

    Returns:
        JSON string of matching articles with id, title, and content.
    """
    logger.info("KB search: query=%r category=%r", query, category)
    query_lower = query.lower()
    results: list[dict[str, str]] = []

    for article in _KNOWLEDGE_BASE.values():
        if category and article["category"] != category:
            continue
        searchable = f"{article['title']} {article['content']}".lower()
        if any(word in searchable for word in query_lower.split()):
            results.append(article)

    if not results:
        if category:
            results = [a for a in _KNOWLEDGE_BASE.values() if a["category"] == category][:3]
        else:
            results = list(_KNOWLEDGE_BASE.values())[:3]

    return json.dumps(results, indent=2)


def get_customer_info(customer_id: str) -> str:
    """Retrieve customer profile and order history from the CRM.

    Args:
        customer_id: The customer identifier (e.g. CUST-001).

    Returns:
        JSON string with customer details, plan, status, and orders.
    """
    logger.info("CRM lookup: customer_id=%r", customer_id)
    customer = _CRM_DATABASE.get(customer_id)
    if customer is None:
        return json.dumps({"error": f"Customer {customer_id!r} not found."})
    return json.dumps(customer, indent=2)
