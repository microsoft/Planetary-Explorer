"""Concurrency test for AnalystAgent._get_or_create_agent_for_model --
locks in the race-condition fix from PR #31/#41 review.

Previously a single mutable self._agent_id / self._current_model pair was
shared across all concurrent requests: if user A selected gpt-5 and user B
selected gpt-4o-mini at nearly the same time, the model-switch code could
swap the shared agent_id out from under user A's in-flight run. The fix
replaced that with a per-model cache (self._agents_by_model) and resolves
agent_id to a value local to each call.

These tests avoid any dependency on the real azure-ai-agents SDK by
monkeypatching the two points where AnalystAgent would otherwise reach out
to Azure: ``_ensure_initialized`` (skipped -- we seed the initialized
state directly) and ``_create_agent_capped`` (stubbed to return a fake
agent object with a deterministic, call-counted id).

Uses plain ``asyncio.run()`` inside sync test functions rather than
pytest-asyncio (not a dependency of this project; no other test in this
suite uses async tests), so no new test dependency is introduced.
"""

from __future__ import annotations

import asyncio

from agents.analyst_agent.analyst_agent import AnalystAgent


class _FakeAgent:
    def __init__(self, agent_id: str):
        self.id = agent_id


class _FakeAgentsClient:
    """Stand-in for azure.ai.agents.aio.AgentsClient -- only
    enable_auto_function_calls is touched by _get_or_create_agent_for_model
    on a cache miss, before it delegates to the (also stubbed)
    _create_agent_capped.
    """

    def enable_auto_function_calls(self, toolset):
        pass


def _make_agent(create_delay: float = 0.0):
    """Build an AnalystAgent with Azure calls stubbed out.

    ``_create_agent_capped`` returns a fake agent id derived from the
    model name plus a call counter, and optionally sleeps for
    ``create_delay`` seconds before returning -- used to force two
    concurrent calls for *different* models to genuinely overlap in time,
    which is what would have triggered the original race.
    """
    agent = AnalystAgent()
    agent._initialized = True
    agent._default_model = "gpt-4o"
    agent._agents_client = _FakeAgentsClient()

    call_count = {"n": 0}

    async def _fake_create_agent_capped(model, instructions, toolset):
        call_count["n"] += 1
        if create_delay:
            await asyncio.sleep(create_delay)
        return _FakeAgent(f"agent-for-{model}-call{call_count['n']}")

    agent._create_agent_capped = _fake_create_agent_capped  # type: ignore[method-assign]

    return agent, call_count


def test_concurrent_requests_different_models_get_distinct_agent_ids():
    agent, _ = _make_agent(create_delay=0.05)

    async def _run():
        # Simulate user A (gpt-5) and user B (gpt-4o-mini) racing each other.
        return await asyncio.gather(
            agent._get_or_create_agent_for_model("gpt-5"),
            agent._get_or_create_agent_for_model("gpt-4o-mini"),
        )

    agent_id_a, agent_id_b = asyncio.run(_run())

    assert agent_id_a != agent_id_b
    assert "gpt-5" in agent_id_a
    assert "gpt-4o-mini" in agent_id_b
    # Both models should now be independently cached.
    assert agent._agents_by_model["gpt-5"] == agent_id_a
    assert agent._agents_by_model["gpt-4o-mini"] == agent_id_b


def test_concurrent_requests_same_model_create_agent_once():
    agent, call_count = _make_agent(create_delay=0.05)

    async def _run():
        # Several concurrent requests for the SAME model should not each
        # create their own Agent Service agent definition (the leak this
        # fix also resolved as a side effect) -- the double-checked lock
        # in _get_or_create_agent_for_model should collapse them to one
        # creation.
        return await asyncio.gather(
            *[agent._get_or_create_agent_for_model("gpt-5") for _ in range(5)]
        )

    results = asyncio.run(_run())

    assert len(set(results)) == 1
    assert call_count["n"] == 1


def test_no_model_falls_back_to_default_model():
    agent, _ = _make_agent()
    agent_id = asyncio.run(agent._get_or_create_agent_for_model(None))
    assert "gpt-4o" in agent_id  # agent._default_model set in _make_agent


def test_sequential_model_switch_does_not_recreate_agent():
    agent, call_count = _make_agent()

    async def _run():
        first = await agent._get_or_create_agent_for_model("gpt-5")
        second = await agent._get_or_create_agent_for_model("gpt-4o-mini")
        back_to_first = await agent._get_or_create_agent_for_model("gpt-5")
        return first, second, back_to_first

    first, second, back_to_first = asyncio.run(_run())

    assert back_to_first == first  # cache hit, not a fresh creation
    assert call_count["n"] == 2  # only 2 distinct models ever created
