"""Application-wide settings sourced from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Immutable settings loaded once at import time."""

    # Model
    model_name: str = field(
        default_factory=lambda: os.getenv("ADK_MODEL", "gemini-3.5-flash-lite")
    )

    # MCP server
    mcp_server_path: str = field(
        default_factory=lambda: os.getenv(
            "MCP_SERVER_PATH",
            "src/adk_cx_support_orchestrator/mcp_server/server.py",
        )
    )

    # Loop
    max_critic_iterations: int = field(
        default_factory=lambda: int(os.getenv("MAX_CRITIC_ITERATIONS", "3"))
    )

    # Confidence thresholds
    ambiguity_threshold: float = field(
        default_factory=lambda: float(os.getenv("AMBIGUITY_THRESHOLD", "0.6"))
    )

    # App identity
    app_name: str = "adk-cx-support-orchestrator"

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )


settings = Settings()
