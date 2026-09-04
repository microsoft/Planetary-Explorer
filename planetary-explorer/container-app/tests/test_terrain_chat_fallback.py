"""Terrain chat fallback contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _JsonRequest:
    async def json(self) -> dict:
        return {
            "session_id": "terrain-fallback",
            "message": "Summarize the terrain.",
            "latitude": 51.0447,
            "longitude": -114.0719,
            "radius_km": 5.0,
        }


@pytest.mark.asyncio
async def test_given_agent_failure_when_chatting_then_shared_client_synthesizes_tools(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.terrain_agent as agent_module
    import geoint.terrain_tools as tools_module
    import pipeline._aoai as aoai_module

    class FailingAgent:
        async def chat(self, **_kwargs):
            raise RuntimeError("agent unavailable")

    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="synthesized"))
                ]
            )

    factory_calls = []
    monkeypatch.setattr(agent_module, "get_terrain_agent", lambda: FailingAgent())
    monkeypatch.setattr(tools_module, "get_elevation_analysis", lambda *_args: "100 m")
    monkeypatch.setattr(tools_module, "get_slope_analysis", lambda *_args: "5 degrees")
    monkeypatch.setattr(tools_module, "find_flat_areas", lambda *_args: "flat")
    monkeypatch.setattr(tools_module, "analyze_flood_risk", lambda *_args: "low")
    monkeypatch.setattr(
        aoai_module,
        "get_aoai_client",
        lambda: (
            factory_calls.append(True)
            or SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
        ),
    )

    # Act
    result = await fastapi_app.geoint_terrain_chat(_JsonRequest())

    # Assert
    assert factory_calls == [True]
    assert result["status"] == "success"
    assert result["response"] == "synthesized"
    assert result["tool_calls"] == ["elevation", "slope", "flat_areas", "flood_risk"]
