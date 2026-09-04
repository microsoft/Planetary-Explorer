"""Dedicated GEOINT agent retries do not replay tool-bearing runs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _Messages:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **_kwargs) -> None:
        self.calls += 1


class _Runs:
    def __init__(self) -> None:
        self.calls = 0

    async def create_and_process(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            id="failed-run",
            status="failed",
            last_error="HTTP 429 Too Many Requests",
        )


class _RunSteps:
    def list(self, **_kwargs):
        async def steps():
            yield SimpleNamespace(
                step_details=SimpleNamespace(tool_calls=[object()]),
            )

        return steps()


class _FailFirstMessages:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **_kwargs) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("HTTP 429 Too Many Requests")


class _TerminalRuns:
    def __init__(self) -> None:
        self.calls = 0

    async def create_and_process(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            id="terminal-run",
            status="failed",
            last_error="Invalid request",
        )


class _EmptyRunSteps:
    def list(self, **_kwargs):
        async def steps():
            if False:
                yield None

        return steps()


def _client():
    return SimpleNamespace(
        messages=_Messages(),
        runs=_Runs(),
        run_steps=_RunSteps(),
    )


def _pre_dispatch_client():
    return SimpleNamespace(
        messages=_FailFirstMessages(),
        runs=_TerminalRuns(),
        run_steps=_EmptyRunSteps(),
    )


def _wire_retry_agent(monkeypatch, agent, client, session) -> None:
    import geoint.agent_retry as retry_module

    async def ensure_initialized() -> None:
        agent._initialized = True
        agent._agent_id = "agent-id"
        agent._agents_client = client

    async def get_session(*_args, **_kwargs):
        return session

    monkeypatch.setattr(retry_module, "agent_retry_delay_seconds", lambda _attempt: 0)
    monkeypatch.setattr(agent, "_ensure_initialized", ensure_initialized)
    monkeypatch.setattr(agent, "_get_or_create_session", get_session)
    agent._initialized = True
    agent._agent_id = "agent-id"
    agent._agents_client = client


async def _run_weather_pre_dispatch_retry(monkeypatch, client) -> None:
    from geoint.extreme_weather_agent import (
        ExtremeWeatherAgent,
        ExtremeWeatherAgentSession,
        _reverse_geocode_cache,
    )

    agent = ExtremeWeatherAgent()
    session = ExtremeWeatherAgentSession(
        "weather-session", 45.5, -73.5, "weather-thread"
    )
    agent.sessions[session.session_id] = session
    _reverse_geocode_cache["45.5000:-73.5000"] = "Montreal"
    _wire_retry_agent(monkeypatch, agent, client, session)

    await agent.chat(session.session_id, "Compare climate scenarios.", 45.5, -73.5)


async def _run_mobility_pre_dispatch_retry(monkeypatch, client) -> None:
    from geoint.mobility_agent import GeointMobilityAgent, MobilityAgentSession
    from semantic_translator import geocoding_plugin

    async def geocode(*_args):
        return '{"name":"Whitehorse","region":"Yukon","country":"Canada"}'

    monkeypatch.setattr(geocoding_plugin, "azure_maps_reverse_geocode", geocode)
    agent = GeointMobilityAgent()
    session = MobilityAgentSession(
        "mobility-session", 60.72, -135.05, "mobility-thread"
    )
    agent.sessions[session.session_id] = session
    _wire_retry_agent(monkeypatch, agent, client, session)

    await agent.analyze_mobility(
        60.72,
        -135.05,
        user_context="Assess the route.",
        include_vision_analysis=False,
        session_id=session.session_id,
        latitude_b=60.75,
        longitude_b=-135.01,
    )


async def _run_terrain_pre_dispatch_retry(monkeypatch, client) -> None:
    from geoint.terrain_agent import TerrainAgent, TerrainAgentSession
    from semantic_translator import geocoding_plugin

    async def geocode(*_args):
        return '{"name":"Calgary","region":"Alberta","country":"Canada"}'

    monkeypatch.setattr(geocoding_plugin, "azure_maps_reverse_geocode", geocode)
    agent = TerrainAgent()
    session = TerrainAgentSession("terrain-session", 51.05, -114.07, "terrain-thread")
    agent.sessions[session.session_id] = session
    _wire_retry_agent(monkeypatch, agent, client, session)

    await agent.chat(session.session_id, "Assess terrain.", 51.05, -114.07)


async def _run_building_pre_dispatch_retry(monkeypatch, client) -> None:
    from geoint.building_damage_agent import (
        BuildingDamageAgent,
        BuildingDamageSession,
    )

    agent = BuildingDamageAgent()
    session = BuildingDamageSession(
        "building-session", 52.87, -118.08, "building-thread"
    )
    agent.sessions[session.session_id] = session
    _wire_retry_agent(monkeypatch, agent, client, session)

    await agent._run_agent(
        session,
        session.session_id,
        "Assess building damage.",
        52.87,
        -118.08,
        5.0,
    )


@pytest.mark.parametrize(
    "runner",
    [
        _run_weather_pre_dispatch_retry,
        _run_mobility_pre_dispatch_retry,
        _run_terrain_pre_dispatch_retry,
        _run_building_pre_dispatch_retry,
    ],
    ids=["weather", "mobility", "terrain", "building-damage"],
)
@pytest.mark.asyncio
async def test_given_transient_pre_dispatch_failure_when_running_then_one_run_is_dispatched(
    monkeypatch,
    runner,
) -> None:
    # Arrange
    client = _pre_dispatch_client()

    # Act
    await runner(monkeypatch, client)

    # Assert
    assert client.messages.calls == 2
    assert client.runs.calls == 1


@pytest.mark.asyncio
async def test_given_tool_bearing_failed_weather_run_then_it_is_not_retried() -> None:
    from geoint.extreme_weather_agent import (
        ExtremeWeatherAgent,
        ExtremeWeatherAgentSession,
        _reverse_geocode_cache,
    )

    agent = ExtremeWeatherAgent()
    agent._initialized = True
    agent._agent_id = "weather-agent"
    agent._agents_client = _client()
    agent.sessions["weather-session"] = ExtremeWeatherAgentSession(
        "weather-session", 45.5, -73.5, "weather-thread"
    )
    _reverse_geocode_cache["45.5000:-73.5000"] = "Montreal"

    result = await agent.chat(
        "weather-session",
        "Compare climate scenarios.",
        45.5,
        -73.5,
    )

    assert result["error"] == "HTTP 429 Too Many Requests"
    assert agent._agents_client.runs.calls == 1
    assert agent._agents_client.messages.calls == 1


@pytest.mark.asyncio
async def test_given_tool_bearing_failed_mobility_run_then_it_is_not_retried(
    monkeypatch,
) -> None:
    from geoint.mobility_agent import GeointMobilityAgent, MobilityAgentSession
    from semantic_translator import geocoding_plugin

    async def geocode(*_args):
        return '{"name":"Whitehorse","region":"Yukon","country":"Canada"}'

    monkeypatch.setattr(geocoding_plugin, "azure_maps_reverse_geocode", geocode)
    agent = GeointMobilityAgent()
    agent._initialized = True
    agent._agent_id = "mobility-agent"
    agent._agents_client = _client()
    agent.sessions["mobility-session"] = MobilityAgentSession(
        "mobility-session", 60.72, -135.05, "mobility-thread"
    )

    result = await agent.analyze_mobility(
        60.72,
        -135.05,
        user_context="Assess the route.",
        include_vision_analysis=False,
        session_id="mobility-session",
        latitude_b=60.75,
        longitude_b=-135.01,
    )

    assert result["error"] == "HTTP 429 Too Many Requests"
    assert agent._agents_client.runs.calls == 1
    assert agent._agents_client.messages.calls == 1
