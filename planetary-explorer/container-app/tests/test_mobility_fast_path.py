"""Two-point Mobility endpoint fast-path contracts."""

from __future__ import annotations

import json

import pytest


class _JsonRequest:
    async def json(self) -> dict:
        return {
            "latitude": 60.7212,
            "longitude": -135.0568,
            "latitude_b": 60.7562,
            "longitude_b": -135.0068,
            "user_query": "Assess the emergency-supply route.",
        }


class _PartialDestinationRequest:
    def __init__(self, destination: dict) -> None:
        self.destination = destination

    async def json(self) -> dict:
        return {
            "latitude": 60.7212,
            "longitude": -135.0568,
            **self.destination,
        }


@pytest.mark.parametrize(
    "destination",
    [
        {"latitude_b": 60.7562},
        {"longitude_b": -135.0068},
    ],
)
@pytest.mark.asyncio
async def test_given_partial_destination_when_analyzing_then_request_is_rejected(
    destination,
) -> None:
    # Arrange
    import fastapi_app

    # Act and Assert
    with pytest.raises(fastapi_app.HTTPException) as error:
        await fastapi_app.geoint_mobility_analysis(
            _PartialDestinationRequest(destination)
        )

    assert error.value.status_code == 400
    assert "must be provided together" in error.value.detail


@pytest.mark.asyncio
async def test_given_two_points_when_analyzing_then_direct_traverse_is_returned(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.mobility_tools as tools_module

    calls = []
    monkeypatch.setattr(
        tools_module,
        "analyze_two_point_traverse",
        lambda *args: (
            calls.append(args)
            or json.dumps(
                {
                    "complete": True,
                    "coverage": {
                        "origin_sources": ["cop-dem-glo-30"],
                        "destination_sources": ["cop-dem-glo-30"],
                        "waypoints_with_data": 1,
                        "waypoints_expected": 1,
                    },
                    "route": {"distance_km": 4.5, "bearing_degrees": 35.0},
                    "road_route": {
                        "road_route_available": False,
                        "reason": "No road route",
                    },
                    "corridor": {"overall_status": "SLOW-GO", "waypoints_sampled": 1},
                    "origin": {"data_sources": ["cop-dem-glo-30", "jrc-gsw"]},
                    "destination": {"data_sources": ["cop-dem-glo-30"]},
                }
            )
        ),
    )

    # Act
    result = await fastapi_app.geoint_mobility_analysis(_JsonRequest())

    # Assert
    assert calls == [(60.7212, -135.0568, 60.7562, -135.0068)]
    tool_call = result["result"]["tool_calls"][0]
    assert tool_call["tool"] == "analyze_two_point_traverse"
    assert tool_call["result"]["corridor"]["overall_status"] == "SLOW-GO"
    assert "planning aid" in result["result"]["response"]


@pytest.mark.asyncio
async def test_given_incomplete_traverse_when_analyzing_then_endpoint_rejects_it(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.mobility_tools as tools_module

    monkeypatch.setattr(
        tools_module,
        "analyze_two_point_traverse",
        lambda *_args: json.dumps(
            {
                "complete": False,
                "route": {"distance_km": 4.5},
                "corridor": {"overall_status": "GO", "waypoints_sampled": 0},
                "origin": {"data_sources": []},
                "destination": {"data_sources": []},
            }
        ),
    )

    # Act and assert
    with pytest.raises(fastapi_app.HTTPException) as error:
        await fastapi_app.geoint_mobility_analysis(_JsonRequest())

    assert error.value.status_code == 503
    assert "complete geospatial coverage" in error.value.detail


@pytest.mark.asyncio
async def test_given_busy_traverse_when_analyzing_then_safe_retry_contract_is_returned(
    monkeypatch,
) -> None:
    # Arrange
    import fastapi_app
    import geoint.mobility_tools as tools_module

    monkeypatch.setattr(
        tools_module,
        "analyze_two_point_traverse",
        lambda *_args: json.dumps(
            {
                "error": "Another mobility analysis is still running.",
                "retryable": True,
            }
        ),
    )

    # Act
    response = await fastapi_app.geoint_mobility_analysis(_JsonRequest())

    # Assert
    assert response.status_code == 429
    assert json.loads(response.body) == {
        "error": "Another mobility analysis is still running.",
        "retry": {"safe": True, "stage": "pre_dispatch"},
    }


def test_given_empty_prefetch_when_sampling_corridor_then_search_is_not_repeated(
    monkeypatch,
) -> None:
    # Arrange
    import geoint.mobility_tools as tools_module

    monkeypatch.setattr(
        tools_module,
        "_query_stac_collection_sync",
        lambda *_args, **_kwargs: pytest.fail("prefetch miss must not fan out"),
    )

    # Act
    result = tools_module._sample_corridor_point(
        60.73,
        -135.04,
        {"cop-dem-glo-30": [], "esa-worldcover": []},
    )
    transect = tools_module._build_elevation_transect(
        60.72,
        -135.05,
        60.75,
        -135.01,
        num_samples=3,
        prefetched_dem_items=[],
    )

    # Assert
    assert result["status"] == "GO"
    assert len(transect["profile"]) == 3
    assert all(sample["elevation_m"] is None for sample in transect["profile"])


def test_given_slow_supplementary_tasks_when_traversing_then_internal_deadline_returns(
    monkeypatch,
) -> None:
    # Arrange
    import geoint.mobility_tools as tools_module

    monkeypatch.setenv("MOBILITY_TRAVERSE_DEADLINE_SECONDS", "0.1")
    monkeypatch.setattr(
        tools_module,
        "_prefetch_corridor_stac_items",
        lambda *_args, **_kwargs: {
            collection: []
            for collection in (
                "jrc-gsw",
                "sentinel-1-rtc",
                "sentinel-2-l2a",
                "cop-dem-glo-30",
                "modis-14A1-061",
                "esa-worldcover",
            )
        },
    )
    release = __import__("threading").Event()

    def blocked(*_args, **_kwargs):
        release.wait(timeout=1)
        return {}

    monkeypatch.setattr(tools_module, "_analyze_all_directions_sync", blocked)
    monkeypatch.setattr(tools_module, "_build_elevation_transect", blocked)
    monkeypatch.setattr(tools_module, "_sample_corridor_point", blocked)

    # Act
    started = __import__("time").monotonic()
    result = json.loads(
        tools_module.analyze_two_point_traverse(60.72, -135.05, 60.75, -135.01)
    )
    elapsed = __import__("time").monotonic() - started

    # Assert
    assert elapsed < 0.5
    assert result["complete"] is False
    second = json.loads(
        tools_module.analyze_two_point_traverse(60.72, -135.05, 60.75, -135.01)
    )
    assert second["retryable"] is True
    release.set()
    assert tools_module._traverse_admission.acquire(timeout=1)
    tools_module._traverse_admission.release()


def test_given_known_noncovering_item_when_filtering_then_it_is_not_sampled() -> None:
    # Arrange
    import geoint.mobility_tools as tools_module

    distant = type("Item", (), {"bbox": [-10, -10, -9, -9]})()
    unknown = type("Item", (), {"bbox": None})()

    # Act and assert
    assert tools_module._items_covering_point([distant], 60.72, -135.05) == []
    assert tools_module._items_covering_point([distant, unknown], 60.72, -135.05) == [
        unknown
    ]


def test_given_empty_data_when_traversing_then_result_is_not_complete(
    monkeypatch,
) -> None:
    # Arrange
    import geoint.mobility_tools as tools_module

    monkeypatch.setattr(
        tools_module,
        "_prefetch_corridor_stac_items",
        lambda *_args, **_kwargs: {
            collection: []
            for collection in (
                "jrc-gsw",
                "sentinel-1-rtc",
                "sentinel-2-l2a",
                "cop-dem-glo-30",
                "modis-14A1-061",
                "esa-worldcover",
            )
        },
    )

    # Act
    result = json.loads(
        tools_module.analyze_two_point_traverse(60.72, -135.05, 60.75, -135.01)
    )

    # Assert
    assert result["complete"] is False
    assert result["coverage"]["origin_sources"] == []
