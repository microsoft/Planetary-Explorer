"""Tests for the shared Agent Service retry policy."""

from __future__ import annotations

import pytest

from geoint.agent_retry import (
    agent_retry_delay_seconds,
    agent_run_has_dispatched_tools,
    is_retryable_agent_error,
)


@pytest.mark.parametrize(
    "error",
    [
        {"code": "rate_limit_exceeded", "message": "Requests exceeded rate limit"},
        "HTTP 429 Too Many Requests",
        "DeploymentNotFound",
        "server_error",
    ],
)
def test_given_transient_agent_error_when_classifying_then_retryable(error) -> None:
    assert is_retryable_agent_error(error) is True


def test_given_validation_error_when_classifying_then_not_retryable() -> None:
    assert is_retryable_agent_error("Invalid latitude") is False


def test_given_retry_attempts_when_delaying_then_backoff_is_bounded() -> None:
    assert [agent_retry_delay_seconds(attempt) for attempt in (1, 2, 3)] == [10, 30, 30]


@pytest.mark.asyncio
async def test_given_tool_step_when_checking_failed_run_then_dispatch_is_detected() -> (
    None
):
    class RunSteps:
        def list(self, **_kwargs):
            async def steps():
                yield type(
                    "Step",
                    (),
                    {"step_details": type("Details", (), {"tool_calls": [object()]})()},
                )()

            return steps()

    client = type("Client", (), {"run_steps": RunSteps()})()

    assert await agent_run_has_dispatched_tools(client, "thread", "run") is True


@pytest.mark.asyncio
async def test_given_unreadable_steps_when_checking_failed_run_then_dispatch_is_ambiguous() -> (
    None
):
    class RunSteps:
        def list(self, **_kwargs):
            raise RuntimeError("transport failed")

    client = type("Client", (), {"run_steps": RunSteps()})()

    assert await agent_run_has_dispatched_tools(client, "thread", "run") is True


@pytest.mark.asyncio
async def test_given_empty_steps_when_checking_failed_run_then_retry_is_safe() -> None:
    class RunSteps:
        def list(self, **_kwargs):
            async def steps():
                if False:
                    yield None

            return steps()

    client = type("Client", (), {"run_steps": RunSteps()})()

    assert await agent_run_has_dispatched_tools(client, "thread", "run") is False
