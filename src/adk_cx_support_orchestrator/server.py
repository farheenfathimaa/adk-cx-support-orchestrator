"""FastAPI server for Cloud Run deployment.

Wraps the ADK root_agent with an ASGI application that Cloud Run / uvicorn
can serve.
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("server")

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
except ImportError:
    logger.error(
        "FastAPI / uvicorn not installed. "
        "Run: pip install fastapi uvicorn"
    )
    sys.exit(1)

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import the root_agent (ADK convention)
from adk_cx_support_orchestrator.agent import root_agent  # noqa: F401

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CX Support Orchestrator",
    description="Multi-agent customer-support triage built with Google ADK.",
    version="0.1.0",
)

_session_service = InMemorySessionService()
_runner = Runner(
    agent=root_agent,
    app_name="cx-support-orchestrator",
    session_service=_session_service,
)


@app.get("/health")
async def health() -> JSONResponse:
    """Cloud Run health check endpoint."""
    return JSONResponse({"status": "healthy"})


@app.post("/triage")
async def triage(payload: dict) -> JSONResponse:
    """Triage a support ticket.

    Request body:
        { "ticket_id": "...", "text": "...", "customer_id": "..." }
    """
    import asyncio

    ticket_text = payload.get("text", "")
    customer_id = payload.get("customer_id", "")
    ticket_id = payload.get("ticket_id", "unknown")

    if not ticket_text:
        return JSONResponse({"error": "Missing 'text' field"}, status_code=400)

    user_id = customer_id or "anonymous"
    session_id = f"triage-{ticket_id}"

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=ticket_text)],
    )

    final_response = ""
    try:
        async for event in _runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content and event.content.parts:
                final_response = event.content.parts[0].text
    except Exception as exc:
        logger.exception("Triage failed for ticket %s", ticket_id)
        return JSONResponse(
            {"error": f"Triage failed: {exc!s}"}, status_code=500
        )

    return JSONResponse(
        {
            "ticket_id": ticket_id,
            "response": final_response,
        }
    )


def main() -> None:
    """Entry point for local development."""
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
