"""Extreme Weather endpoint fast-path contracts."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest


class _JsonRequest:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def json(self) -> dict:
        return self.payload


@pytest.mark.asyncio
async def test_given_scenario_comparison_when_formatting_then_shared_aoai_client_is_used(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.extreme_weather_tools as tools_module
    import pipeline._aoai as aoai_module

    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="formatted"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    factory_calls = []
    monkeypatch.setattr(
        aoai_module,
        "get_aoai_client",
        lambda: factory_calls.append(True) or fake_client,
    )
    monkeypatch.setattr(
        tools_module,
        "compare_climate_scenarios",
        lambda *_args: json.dumps(
            {
                "complete": True,
                "comparison": {
                    "tasmax": {
                        "ssp245": {"value": 1},
                        "ssp585": {"value": 2},
                    },
                    "pr": {
                        "ssp245": {"value": 3},
                        "ssp585": {"value": 4},
                    },
                },
            }
        ),
    )
    monkeypatch.setattr(
        agent_module,
        "_reverse_geocode_cache",
        {
            "45.5019:-73.5674": "Montreal, Quebec, Canada",
        },
    )
    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: SimpleNamespace(),
    )

    # Act
    result = await fastapi_app.geoint_extreme_weather_analysis(
        _JsonRequest(
            {
                "latitude": 45.5019,
                "longitude": -73.5674,
                "user_query": (
                    "What are the projected temperature and precipitation trends for "
                    "Montreal during 2026 under SSP245 and SSP585?"
                ),
            }
        )
    )

    # Assert
    assert factory_calls == [True]
    assert result["status"] == "success"
    assert result["result"]["analysis"] == "formatted"
    assert result["result"]["tool_calls"][0]["tool"] == "compare_climate_scenarios"


@pytest.mark.asyncio
async def test_given_monthly_precipitation_when_analyzing_then_all_months_are_returned(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.netcdf_computation_tools as tools_module

    periods = [
        {"period": month, "mean": float(index), "unit": "mm/day"}
        for index, month in enumerate(
            [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            start=1,
        )
    ]
    monkeypatch.setattr(
        tools_module,
        "sample_timeseries",
        lambda *_args: json.dumps(
            {
                "variable_name": "Precipitation",
                "periods": periods,
            }
        ),
    )
    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: SimpleNamespace(),
    )

    # Act
    result = await fastapi_app.geoint_extreme_weather_analysis(
        _JsonRequest(
            {
                "latitude": 43.6532,
                "longitude": -79.3832,
                "user_query": "Show monthly projected precipitation for Toronto in 2026 and identify the wettest month.",
            }
        )
    )

    # Assert
    assert result["status"] == "success"
    tool_call = result["result"]["tool_calls"][0]
    assert tool_call["tool"] == "sample_timeseries"
    assert len(tool_call["result"]["periods"]) == 12
    assert "December" not in result["result"]["analysis"]
    assert "Dec at 12.0 mm/day" in result["result"]["analysis"]


@pytest.mark.parametrize(
    "query",
    [
        "Show monthly temperature and precipitation for Toronto in 2026.",
        "Show monthly precipitation for Toronto under SSP245 and SSP585.",
    ],
)
@pytest.mark.asyncio
async def test_given_multidimensional_monthly_request_when_analyzing_then_it_is_rejected(
    monkeypatch,
    query,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module

    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: SimpleNamespace(),
    )

    # Act and Assert
    with pytest.raises(fastapi_app.HTTPException) as error:
        await fastapi_app.geoint_extreme_weather_analysis(
            _JsonRequest(
                {
                    "latitude": 43.6532,
                    "longitude": -79.3832,
                    "user_query": query,
                }
            )
        )

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_given_monthly_2018_request_when_analyzing_then_requested_year_is_used(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.netcdf_computation_tools as tools_module

    calls = []
    periods = [
        {"period": str(month), "mean": float(month), "unit": "mm/day"}
        for month in range(1, 13)
    ]
    monkeypatch.setattr(
        tools_module,
        "sample_timeseries",
        lambda *args: (
            calls.append(args)
            or json.dumps(
                {
                    "variable_name": "Precipitation",
                    "periods": periods,
                }
            )
        ),
    )
    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: SimpleNamespace(),
    )

    # Act
    result = await fastapi_app.geoint_extreme_weather_analysis(
        _JsonRequest(
            {
                "latitude": 43.6532,
                "longitude": -79.3832,
                "user_query": "Show monthly precipitation for Toronto in 2018.",
            }
        )
    )

    # Assert
    assert calls[0][4] == 2018
    assert "2018" in result["result"]["analysis"]


@pytest.mark.asyncio
async def test_given_partial_comparison_when_analyzing_then_agent_is_not_replayed(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.extreme_weather_tools as tools_module

    class UnexpectedAgent:
        async def chat(self, **_kwargs):
            raise AssertionError("Partial direct comparison must not replay tools")

    monkeypatch.setattr(
        tools_module,
        "compare_climate_scenarios",
        lambda *_args: json.dumps({"complete": False, "comparison": {}}),
    )
    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: UnexpectedAgent(),
    )

    # Act and assert
    with pytest.raises(fastapi_app.HTTPException) as error:
        await fastapi_app.geoint_extreme_weather_analysis(
            _JsonRequest(
                {
                    "latitude": 45.5019,
                    "longitude": -73.5674,
                    "user_query": "Compare SSP245 and SSP585 temperature and precipitation.",
                }
            )
        )

    assert error.value.status_code == 504


@pytest.mark.asyncio
async def test_given_busy_comparison_when_analyzing_then_safe_retry_contract_is_returned(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.extreme_weather_tools as tools_module

    monkeypatch.setattr(
        tools_module,
        "compare_climate_scenarios",
        lambda *_args: json.dumps(
            {
                "error": "Another climate comparison is still running.",
                "retryable": True,
            }
        ),
    )
    monkeypatch.setattr(
        agent_module,
        "get_extreme_weather_agent",
        lambda: SimpleNamespace(),
    )

    # Act
    response = await fastapi_app.geoint_extreme_weather_analysis(
        _JsonRequest(
            {
                "latitude": 45.5019,
                "longitude": -73.5674,
                "user_query": "Compare SSP245 and SSP585 climate scenarios.",
            }
        )
    )

    # Assert
    assert response.status_code == 429
    assert json.loads(response.body) == {
        "error": "Another climate comparison is still running.",
        "retry": {"safe": True, "stage": "pre_dispatch"},
    }


@pytest.mark.asyncio
async def test_given_first_turn_comparison_when_analyzing_then_overview_is_not_selected(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.extreme_weather_agent as agent_module
    import geoint.extreme_weather_tools as tools_module
    import pipeline._aoai as aoai_module

    calls = []
    monkeypatch.setattr(
        tools_module,
        "get_climate_overview",
        lambda *_args: pytest.fail("comparison must not route to overview"),
    )
    monkeypatch.setattr(
        tools_module,
        "compare_climate_scenarios",
        lambda *_args: (
            calls.append("comparison")
            or json.dumps(
                {
                    "complete": True,
                    "comparison": {
                        "tasmax": {"ssp245": {"value": 1}, "ssp585": {"value": 2}},
                        "pr": {"ssp245": {"value": 3}, "ssp585": {"value": 4}},
                    },
                }
            )
        ),
    )
    monkeypatch.setattr(agent_module, "_reverse_geocode_cache", {})
    monkeypatch.setattr(
        agent_module, "get_extreme_weather_agent", lambda: SimpleNamespace()
    )

    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="comparison"))]
            )

    monkeypatch.setattr(
        aoai_module,
        "get_aoai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions())),
    )

    # Act
    result = await fastapi_app.geoint_extreme_weather_analysis(
        _JsonRequest(
            {
                "latitude": 45.5019,
                "longitude": -73.5674,
                "user_query": "Compare climate projection scenarios SSP245 and SSP585.",
            }
        )
    )

    # Assert
    assert calls == ["comparison"]
    assert result["result"]["tool_calls"][0]["tool"] == "compare_climate_scenarios"


def test_given_timed_comparison_when_called_again_then_no_more_work_is_queued(
    monkeypatch,
) -> None:
    # Arrange
    import geoint.extreme_weather_tools as tools_module

    admission = threading.BoundedSemaphore(1)
    release = threading.Event()
    sample_calls = []
    monkeypatch.setattr(tools_module, "_comparison_admission", admission)
    monkeypatch.setattr(tools_module, "_COMPARISON_FUTURE_TIMEOUT", 0.01)
    monkeypatch.setattr(
        tools_module,
        "_search_cmip6_items",
        lambda *_args, **_kwargs: [
            {
                "id": "model.scenario.year",
                "assets": {
                    "tasmax": {"href": "tasmax.nc"},
                    "pr": {"href": "pr.nc"},
                },
            }
        ],
    )

    def blocked_sample(href, *_args, **_kwargs):
        sample_calls.append(href)
        release.wait(timeout=1)
        return {"display_value": 1.0, "display_mean": 1.0, "display_unit": "unit"}

    monkeypatch.setattr(tools_module, "_sample_netcdf", blocked_sample)

    # Act
    first = json.loads(tools_module.compare_climate_scenarios(45.5, -73.5, 2026))
    second = json.loads(tools_module.compare_climate_scenarios(45.5, -73.5, 2026))

    # Assert
    assert first["complete"] is False
    assert second["retryable"] is True
    assert len(sample_calls) == 4
    release.set()
    assert admission.acquire(timeout=1)
    admission.release()


def test_given_timed_values_read_when_called_again_then_no_more_work_is_queued(
    monkeypatch,
) -> None:
    # Arrange
    import geoint.extreme_weather_tools as tools_module

    pool = ThreadPoolExecutor(max_workers=1)
    admission = threading.BoundedSemaphore(1)
    release = threading.Event()
    calls = []
    monkeypatch.setattr(tools_module, "_values_pool", pool)
    monkeypatch.setattr(tools_module, "_values_admission", admission)

    def blocked_read():
        calls.append("first")
        release.wait(timeout=1)
        return 1

    # Act and assert
    try:
        with pytest.raises(TimeoutError):
            tools_module._run_values_read(blocked_read, 0.01)
        with pytest.raises(TimeoutError, match="capacity"):
            tools_module._run_values_read(lambda: calls.append("second"), 0.01)
        assert calls == ["first"]
        release.set()
        assert admission.acquire(timeout=1)
        admission.release()
    finally:
        release.set()
        pool.shutdown(wait=True, cancel_futures=True)
