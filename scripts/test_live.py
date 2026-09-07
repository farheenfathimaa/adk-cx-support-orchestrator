#!/usr/bin/env python3
"""Live end-to-end test for the CX support orchestrator.

Runs sample tickets through the FULL agent pipeline using the real Gemini
model. Requires a valid GOOGLE_API_KEY in .env.

NOTE: Free-tier API keys are rate-limited (~5-15 req/min). Space your runs
out, or use the paid tier for large batches.

Usage:
    python scripts/test_live.py                       # run 3 sample tickets
    python scripts/test_live.py billing ambiguous     # run specific sample(s)
    python scripts/test_live.py --all                 # run all sample tickets
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from adk_cx_support_orchestrator.agent import root_agent


SAMPLE_TICKETS: dict[str, str] = {
    "billing": (
        "I was charged twice for my subscription this month. "
        "My account is CUST-001. Can you refund the extra charge?"
    ),
    "technical": (
        "I can't log in — I keep getting an 'invalid credentials' error. "
        "I've tried resetting my password but the email never arrives."
    ),
    "refund": (
        "I purchased a Pro plan 2 weeks ago but it doesn't meet my needs. "
        "I want a full refund."
    ),
    "general": "What features are included in the Enterprise plan?",
    "ambiguous": (
        "Your product stopped working and I want my money back."
    ),
    "edge": "asdfghjkl",
}


def _load_api_key() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        sys.exit("ERROR: GOOGLE_API_KEY not found. Set it or add it to .env")
    return key


async def run_ticket(runner: Runner, session_id: str, text: str) -> tuple[str, float]:
    user_msg = types.Content(role="user", parts=[types.Part(text=text)])
    result = ""
    start = time.monotonic()
    async for event in runner.run_async(
        user_id="test_user", session_id=session_id, new_message=user_msg
    ):
        if event.content and event.content.parts:
            if event.content.parts[0].text:
                result = event.content.parts[0].text
    elapsed = time.monotonic() - start
    return result, elapsed


def main() -> None:
    os.environ["GOOGLE_API_KEY"] = _load_api_key()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickets", nargs="*", help="Sample names to run (default: billing technical ambiguous)")
    parser.add_argument("--all", action="store_true", help="Run every sample ticket")
    args = parser.parse_args()

    if args.all:
        tickets = dict(SAMPLE_TICKETS)
    elif args.tickets:
        tickets = {k: SAMPLE_TICKETS[k] for k in args.tickets if k in SAMPLE_TICKETS}
    else:
        tickets = {k: SAMPLE_TICKETS[k] for k in ("billing", "technical", "ambiguous")}

    if not tickets:
        sys.exit(f"No matching samples. Available: {list(SAMPLE_TICKETS)}")

    async def _main() -> None:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=root_agent,
            app_name="cx-support-live-test",
            session_service=session_service,
        )

        print("\n" + "=" * 70)
        print("  CX Support Orchestrator — Live Test")
        print("=" * 70)

        for i, (name, text) in enumerate(tickets.items()):
            print(f"\n[{i + 1}/{len(tickets)}] Ticket: {name.upper()}")
            print(f"  Input : {text[:80]}{'...' if len(text) > 80 else ''}")

            session_id = f"live-{name}-{int(time.time())}"
            await session_service.create_session(
                app_name="cx-support-live-test",
                user_id="test_user",
                session_id=session_id,
            )

            try:
                response, elapsed = await run_ticket(runner, session_id, text)
                print(f"  Time  : {elapsed:.1f}s")
                print(f"  Output:\n{response}\n")
            except Exception as exc:
                print(f"  FAILED: {type(exc).__name__}: {exc}")
                # Free-tier rate limits — wait a bit before the next ticket
                print("  (rate-limited? waiting 60s before next ticket...)")
                await asyncio.sleep(60)

        print("=" * 70)

    asyncio.run(_main())


if __name__ == "__main__":
    main()