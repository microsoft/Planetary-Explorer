"""Shared retry policy for transient Microsoft Agent Service failures."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_MARKERS = (
    "404",
    "429",
    "deploymentnotfound",
    "failed to resolve model",
    "internalservererror",
    "invalid_engine_error",
    "quota",
    "rate limit",
    "rate_limit_exceeded",
    "resource not found",
    "server_error",
    "something went wrong",
    "too many requests",
    "unable to get resource",
)


def is_retryable_agent_error(error: Any) -> bool:
    """Return whether an Agent Service error is transient and retryable."""
    normalized = str(error).casefold()
    return any(marker in normalized for marker in _TRANSIENT_ERROR_MARKERS)


def agent_retry_delay_seconds(attempt: int) -> int:
    """Return a bounded delay before a one-based retry attempt."""
    return min(30, 10 * (3 ** max(0, attempt - 1)))


async def agent_run_has_dispatched_tools(
    agents_client: Any,
    thread_id: str,
    run_id: str,
) -> bool:
    """Return true unless run-step evidence proves no tool was dispatched."""
    try:
        run_steps = agents_client.run_steps.list(
            thread_id=thread_id,
            run_id=run_id,
        )
        async for step in run_steps:
            details = getattr(step, "step_details", None)
            if getattr(details, "tool_calls", None):
                return True
        return False
    except Exception as error:
        logger.warning(
            "Could not inspect Agent Service run steps for thread=%s run=%s; "
            "suppressing automatic retry: %s",
            thread_id,
            run_id,
            error,
        )
        return True
