"""Project-specific exception hierarchy."""


class CXOrchestratorError(Exception):
    """Base exception for the orchestrator."""


class ClassificationError(CXOrchestratorError):
    """Raised when the intake agent cannot classify a ticket."""


class RoutingError(CXOrchestratorError):
    """Raised when no specialist claims sufficient confidence."""


class MCPConnectionError(CXOrchestratorError):
    """Raised when the MCP server is unreachable."""


class LoopLimitExceededError(CXOrchestratorError):
    """Raised when the draft/critic loop hits max iterations without approval."""

    def __init__(self, iterations: int, last_feedback: str = "") -> None:
        self.iterations = iterations
        self.last_feedback = last_feedback
        super().__init__(
            f"Loop limit exceeded after {iterations} iterations. "
            f"Last critic feedback: {last_feedback!r}"
        )
