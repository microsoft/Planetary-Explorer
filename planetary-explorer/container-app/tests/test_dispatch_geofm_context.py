"""GeoFM-relevant request normalization tests."""

import pytest

from pipeline.dispatch import (
    _build_request,
    _collection_ids_for_asset_inspection,
    _unloaded_collection_for_asset_inspection,
)
from pipeline.layer1_agents import _has_model_backed_geofm_evidence


def test_given_frontend_map_bounds_when_building_request_then_bbox_is_normalized() -> None:
    # Act
    request = _build_request(
        {
            "query": "Use PlanAura",
            "session_id": "session-1",
            "map_bounds": {
                "west": -111.35,
                "south": 56.70,
                "east": -111.34,
                "north": 56.71,
                "center_lat": 56.705,
                "center_lng": -111.345,
            },
        }
    )

    # Assert
    assert request.bbox == (-111.35, 56.70, -111.34, 56.71)


def test_given_loaded_collection_when_inspecting_assets_then_load_is_not_required() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect the hls2-s30 assets and fire bands at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
            "stac_items": [
                {
                    "id": "hls-scene",
                    "collection": "hls2-s30",
                    "assets": {"B04": {}, "B8A": {}, "B12": {}},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id is None


def test_given_collection_id_without_item_metadata_when_inspecting_then_reload_is_required() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect the hls2-s30 assets and fire bands at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_empty_item_assets_when_inspecting_then_reload_is_required() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect the hls2-s30 assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
            "stac_items": [
                {
                    "id": "restored-item",
                    "collection": "hls2-s30",
                    "assets": {},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_loaded_assets_from_other_catalog_when_inspecting_then_reload_is_required() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect the hls2-s30 assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
            "stac_mode": "pro",
            "stac_items": [
                {
                    "id": "public-item",
                    "collection": "hls2-s30",
                    "assets": {"B04": {}, "B8A": {}, "B12": {}},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(
        request,
        collection_ids=["hls2-s30"],
    )

    # Assert
    assert collection_id == "hls2-s30"


def test_given_pro_only_collection_when_inspecting_then_live_id_is_detected() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect tenant-fire assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "stac_mode": "pro",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(
        request,
        collection_ids=["tenant-fire"],
    )

    # Assert
    assert collection_id == "tenant-fire"


def test_given_pro_only_id_and_stale_current_collection_then_explicit_id_wins() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect tenant-fire assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
            "stac_mode": "pro",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(
        request,
        collection_ids=["hls2-s30", "tenant-fire"],
    )

    # Assert
    assert collection_id == "tenant-fire"


def test_given_current_collection_when_inspecting_its_assets_then_collection_is_inferred() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect its imagery assets and fire-composite bands at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "hls2-s30",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_foundation_change_without_collection_when_inspecting_then_hls_is_inferred() -> None:
    # Arrange
    request = _build_request(
        {
            "query": (
                "Inspect the available imagery assets and fire-composite bands "
                "for 2026-07-04 at the pinned location"
            ),
            "pin": {"lat": 50.268, "lng": -89.8572},
            "geoint_module": "foundation_change",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_foundation_change_and_stale_current_layer_then_hls_is_inferred() -> None:
    # Arrange
    request = _build_request(
        {
            "query": (
                "Inspect the available imagery assets and fire-composite bands "
                "for 2026-07-04 at the pinned location"
            ),
            "pin": {"lat": 50.268, "lng": -89.8572},
            "geoint_module": "foundation_change",
            "current_collection": "sentinel-2-l2a",
            "stac_items": [
                {
                    "id": "stale-scene",
                    "collection": "sentinel-2-l2a",
                    "assets": {"visual": {}},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_hls_s30_alias_and_stale_current_layer_then_explicit_alias_wins() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect HLS S30 assets and fire bands at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "sentinel-2-l2a",
            "stac_items": [
                {
                    "id": "stale-scene",
                    "collection": "sentinel-2-l2a",
                    "assets": {"visual": {}},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(
        request,
        collection_ids=["sentinel-2-l2a", "hls2-s30"],
    )

    # Assert
    assert collection_id == "hls2-s30"


def test_given_no_spatial_anchor_when_asking_about_collection_bands_then_load_is_not_required() -> None:
    # Arrange
    request = _build_request(
        {"query": "What bands and assets does hls2-s30 provide?"}
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id is None


def test_given_named_location_when_inspecting_unloaded_assets_then_load_is_required() -> None:
    # Arrange
    request = _build_request(
        {
            "query": "Inspect hls2-s30 assets and fire bands for Thunder Bay",
            "location_name": "Thunder Bay, Ontario",
        }
    )

    # Act
    collection_id = _unloaded_collection_for_asset_inspection(request)

    # Assert
    assert collection_id == "hls2-s30"


def test_given_pro_mode_when_building_inspection_request_then_mode_is_preserved() -> None:
    # Act
    request = _build_request(
        {
            "query": "Inspect hls2-s30 assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "stac_mode": "pro",
        }
    )

    # Assert
    assert request.stac_mode == "pro"


def test_given_default_pro_mode_when_request_omits_mode_then_pro_is_used(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setenv("DEFAULT_STAC_MODE", "pro")

    # Act
    request = _build_request(
        {
            "query": "Inspect tenant-fire assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
        }
    )

    # Assert
    assert request.stac_mode == "pro"


@pytest.mark.asyncio
async def test_given_pro_inspection_when_loading_inventory_then_canonical_and_private_ids_are_combined(
    monkeypatch,
) -> None:
    # Arrange
    import pc_tasks_config_loader
    import pro_stac_client

    async def get_pro_ids():
        return ["tenant-fire"]

    monkeypatch.setattr(
        pc_tasks_config_loader,
        "get_all_collection_ids",
        lambda: ["hls2-s30"],
    )
    monkeypatch.setattr(pro_stac_client, "get_pro_collection_ids", get_pro_ids)
    request = _build_request(
        {
            "query": "Inspect tenant-fire assets at this pin",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "stac_mode": "pro",
        }
    )

    # Act
    collection_ids = await _collection_ids_for_asset_inspection(request)

    # Assert
    assert collection_ids == ["hls2-s30", "tenant-fire"]


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_given_incomplete_geofm_result_when_attributing_then_planaura_is_not_claimed(
    status: str,
) -> None:
    # Act
    attributed = _has_model_backed_geofm_evidence(
        {
            "get_geofm_run": {
                "success": status != "failed",
                "structured": {"status": status},
            }
        }
    )

    # Assert
    assert attributed is False


def test_given_completed_geofm_result_when_attributing_then_planaura_is_claimed() -> None:
    # Act
    attributed = _has_model_backed_geofm_evidence(
        {
            "get_geofm_run": {
                "success": True,
                "structured": {"status": "complete"},
            }
        }
    )

    # Assert
    assert attributed is True


@pytest.mark.asyncio
async def test_given_foundation_change_module_when_dispatching_then_analysis_is_forced(
    monkeypatch,
) -> None:
    # Arrange
    import pipeline.dispatch as dispatch_module
    import pipeline.layer1_agents as layer1_module

    class UnexpectedRouter:
        async def route(self, **_kwargs):
            raise AssertionError("Foundation Change must bypass ActionRouter")

    class CapturingSpecialist:
        def __init__(self) -> None:
            self.decision = None

        async def run(self, decision, _request, _body):
            self.decision = decision
            return {"action": decision.action, "elapsed_ms": 0}

    specialist = CapturingSpecialist()

    class FakeAgents:
        def for_action(self, action):
            assert action == "ANALYZE"
            return specialist

    monkeypatch.setattr(
        dispatch_module,
        "build_default_pipeline",
        lambda: (UnexpectedRouter(), None, None, None),
    )
    monkeypatch.setattr(
        layer1_module,
        "build_layer1_agents",
        lambda **_kwargs: FakeAgents(),
    )

    # Act
    result = await dispatch_module.run_pipeline_v2(
        {
            "query": "Load HLS imagery and find contextual change",
            "session_id": "foundation-change-dispatch",
            "geoint_module": "foundation_change",
        }
    )

    # Assert
    assert result["action"] == "ANALYZE"
    assert specialist.decision.reasoning == "foundation_change_module"


@pytest.mark.asyncio
async def test_given_unloaded_collection_asset_inspection_when_dispatching_then_load_is_forced(
    monkeypatch,
) -> None:
    # Arrange
    import pipeline.dispatch as dispatch_module
    import pipeline.layer1_agents as layer1_module

    class UnexpectedRouter:
        async def route(self, **_kwargs):
            raise AssertionError("Explicit unloaded collection inspection must bypass ActionRouter")

    class CapturingSpecialist:
        def __init__(self) -> None:
            self.decision = None

        async def run(self, decision, _request, _body):
            self.decision = decision
            return {"action": decision.action, "elapsed_ms": 0}

    specialist = CapturingSpecialist()

    class FakeAgents:
        def for_action(self, action):
            assert action == "LOAD"
            return specialist

    monkeypatch.setattr(
        dispatch_module,
        "build_default_pipeline",
        lambda: (UnexpectedRouter(), None, None, None),
    )
    monkeypatch.setattr(
        layer1_module,
        "build_layer1_agents",
        lambda **_kwargs: FakeAgents(),
    )

    # Act
    result = await dispatch_module.run_pipeline_v2(
        {
            "query": (
                "Inspect the available imagery assets and fire-composite bands "
                "for 2026-07-04 at the pinned location"
            ),
            "session_id": "foundation-change-unloaded-inspection",
            "geoint_module": "foundation_change",
            "clarifier_route": "contextual",
            "pin": {"lat": 50.268, "lng": -89.8572},
            "current_collection": "sentinel-2-l2a",
            "has_satellite_data": True,
            "stac_items": [
                {
                    "id": "stale-public-scene",
                    "collection": "sentinel-2-l2a",
                    "assets": {"visual": {}},
                    "_planetary_explorer_stac_mode": "public",
                }
            ],
        }
    )

    # Assert
    assert result["action"] == "LOAD"
    assert result["post_load_inspection"]["collection_id"] == "hls2-s30"
    assert specialist.decision.reasoning == "unloaded_collection_inspection"
    assert specialist.decision.stac_query == "hls2-s30"