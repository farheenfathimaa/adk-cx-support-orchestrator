"""Root agent definition — the ADK entry point.

ADK discovers ``root_agent`` in this module when you run ``adk web`` or
``adk deploy``.  The agent composes the full CX support orchestrator
pipeline with optional MCP tool integration.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from google.adk.agents import Agent

from adk_cx_support_orchestrator.agents.orchestrator import orchestrator_agent
from adk_cx_support_orchestrator.core.config import settings

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("adk_cx_support_orchestrator")

# ---------------------------------------------------------------------------
# Optional: MCP toolset for knowledge-base / CRM
# ---------------------------------------------------------------------------

_mcp_tools: list = []

try:
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams

    server_path = Path(settings.mcp_server_path)
    if server_path.exists():
        _mcp_tools = [
            McpToolset(
                connection_params=StdioConnectionParams(
                    command=sys.executable,
                    args=[str(server_path.resolve())],
                ),
            )
        ]
        logger.info("MCP toolset connected via %s", server_path)
    else:
        logger.warning("MCP server not found at %s — falling back to FunctionTools", server_path)
except ImportError:
    logger.info("google-adk MCP extensions not installed — using FunctionTools only")

# ---------------------------------------------------------------------------
# Root agent
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="CXSupportTriageAgent",
    model=settings.model_name,
    description=(
        "Multi-agent customer-support triage system. Classifies tickets, "
        "fans out to specialist sub-agents for ambiguous cases, refines "
        "draft responses through a critic loop, and produces grounded, "
        "policy-compliant replies."
    ),
    instruction="""\
You are the entry point for a customer-support triage system. A user (or
upstream system) will submit a support ticket as plain text. Your job is to
delegate to the internal orchestration pipeline which will:

1. Extract key facts and classify the ticket (billing / technical / refund /
   general).
2. If the classification is ambiguous, fan out to specialist sub-agents that
   independently score confidence and pick the best match.
3. Draft a reply grounded in knowledge-base articles and CRM data.
4. Critique the draft against tone, accuracy, and policy rubrics — looping
   until it passes or the iteration limit is reached.
5. Return the final response.

Always pass the user's message through to the pipeline. Do NOT answer
directly — the sub-agents handle everything.
""",
    tools=_mcp_tools,
    sub_agents=[orchestrator_agent],
)
