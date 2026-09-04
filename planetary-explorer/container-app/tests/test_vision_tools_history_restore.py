"""Regression tests for raster sampling after chat-history restoration."""

import asyncio
import threading

import pytest

from agents import vision_tools
from agents.analyst_agent.session_context import AnalystSession, set_session
from agents.analyst_agent.tools import _build_request as build_analyst_request
from agents.analyst_agent import tools as analyst_tools
from agents.enhanced_vision_agent import EnhancedVisionAgent, VisionSession
from pipeline.dispatch import _build_request as build_pipeline_request
from agents.raster_sampling_agent.raster_sampling_agent import RasterSamplingAgent
from agents.raster_sampling_agent.raster_sampling_models import (
    RasterSamplingInput,
    RasterSamplingResult,
)
from pipeline.analyzers.comparison_analyzer import _sample_pins_inline
from pipeline.contracts import AnalysisRequest
from geoint.chat_vision_analyzer import _format_map_location


def test_given_western_longitude_when_formatting_vision_context_then_hemisphere_is_west() -> None:
    assert _format_map_location({
        "center_lat": 65.3,
        "center_lng": -126.85,
    }) == "65.3000°N, 126.8500°W"


def test_given_pro_request_when_pipeline_context_is_built_then_mode_and_tilejson_survive() -> None:
    # Arrange
    request_body = {
        "query": "sample the restored raster",
        "stac_mode": "pro",
        "tile_urls": [
            {
                "tilejson_url": "https://example.test/tilejson.json",
                "item_id": "private-item-1",
            }
        ],
    }

    # Act
    pipeline_request = build_pipeline_request(request_body)
    set_session(
        AnalystSession(
            question=pipeline_request.question,
            stac_mode=pipeline_request.stac_mode,
            tile_urls=list(pipeline_request.tile_urls),
        )
    )
    analyst_request = build_analyst_request()

    # Assert
    assert analyst_request.stac_mode == "pro"
    assert analyst_request.tile_urls == ["https://example.test/tilejson.json"]


def test_given_assetless_restored_item_when_sampling_then_rehydrates_stac_assets(
    monkeypatch,
) -> None:
    # Arrange
    fetched_identifiers: list[tuple[str, str]] = []

    def fetch_stac_item(collection: str, item_id: str) -> dict:
        fetched_identifiers.append((collection, item_id))
        return {
            "id": item_id,
            "collection": collection,
            "bbox": [-123.0, 47.0, -122.0, 48.0],
            "properties": {"datetime": "2026-08-26T00:00:00Z"},
            "assets": {
                "data": {
                    "href": "https://example.test/elevation.tif",
                    "type": "image/tiff",
                }
            },
        }

    monkeypatch.setattr(vision_tools, "_fetch_stac_item_sync", fetch_stac_item)
    monkeypatch.setattr(
        vision_tools,
        "_sample_cog_sync",
        lambda *_args, **_kwargs: {"value": 123.0, "crs": "EPSG:4326"},
    )
    vision_tools.set_session_context(
        map_bounds={"pin_lat": 47.6, "pin_lng": -122.3},
        stac_items=[
            {
                "id": "dem-item-1",
                "collection": "cop-dem-glo-30",
                "assets": {},
            }
        ],
        loaded_collections=["cop-dem-glo-30"],
    )

    # Act
    result = vision_tools.sample_raster_value("elevation")

    # Assert
    assert fetched_identifiers == [("cop-dem-glo-30", "dem-item-1")]
    assert "123.00 m" in result


def test_given_pro_mosaic_when_pin_is_in_second_tile_then_uses_pro_item(
    monkeypatch,
) -> None:
    # Arrange
    import pro_stac_client

    monkeypatch.setenv("MPC_PRO_ASSET_HOSTS", "account.blob.core.windows.net")
    fetched_identifiers: list[tuple[str, str]] = []
    sampled_urls: list[str] = []

    def fetch_pro_item(collection: str, item_id: str) -> dict:
        fetched_identifiers.append((collection, item_id))
        is_second = item_id == "private-item-2"
        return {
            "id": item_id,
            "collection": collection,
            "bbox": [-122.0, 47.0, -121.0, 48.0] if is_second else [-123.0, 47.0, -122.0, 48.0],
            "properties": {"datetime": "2026-08-26T00:00:00Z"},
            "assets": {
                "data": {
                        "href": (
                            "https://account.blob.core.windows.net/private/"
                            f"{item_id}.tif"
                        ),
                    "type": "image/tiff",
                }
            },
        }

    def sample_cog(url: str, *_args, **_kwargs) -> dict:
        sampled_urls.append(url)
        return {"value": 222.0, "crs": "EPSG:4326"}

    monkeypatch.setattr(pro_stac_client, "pro_get_item_sync", fetch_pro_item)
    monkeypatch.setattr(
        pro_stac_client,
        "pro_get_collection_sas_sync",
        lambda _collection: "sv=1&sig=pro-secret",
    )
    monkeypatch.setattr(
        vision_tools,
        "_fetch_stac_item_sync",
        lambda *_args: pytest.fail("Public MPC must not serve Pro history."),
    )
    monkeypatch.setattr(vision_tools, "_sample_cog_sync", sample_cog)
    vision_tools.set_session_context(
        map_bounds={"pin_lat": 47.5, "pin_lng": -121.5},
        stac_items=[
            {"id": "private-item-1", "collection": "private-dem", "assets": {}},
            {"id": "private-item-2", "collection": "private-dem", "assets": {}},
        ],
        loaded_collections=["private-dem"],
        stac_mode="pro",
    )

    # Act
    result = vision_tools.sample_raster_value("elevation")

    # Assert
    assert fetched_identifiers == [
        ("private-dem", "private-item-1"),
        ("private-dem", "private-item-2"),
    ]
    assert sampled_urls[0].endswith("private-item-2.tif?sv=1&sig=pro-secret")
    assert "222.00 m" in result


def test_given_many_restored_items_when_rehydrating_then_candidates_are_bounded_and_parallel(
    monkeypatch,
) -> None:
    # Arrange
    barrier = threading.Barrier(5)
    fetched_ids: list[str] = []

    def fetch_item(_collection: str, item_id: str) -> dict:
        fetched_ids.append(item_id)
        barrier.wait(timeout=2)
        return {"id": item_id, "collection": "cop-dem", "assets": {"data": {"href": item_id}}}

    items = [
        {
            "id": f"item-{index}",
            "collection": "cop-dem",
            "bbox": [index, 0, index + 0.9, 1],
            "assets": {},
        }
        for index in range(20)
    ]
    monkeypatch.setattr(vision_tools, "_fetch_stac_item_sync", fetch_item)

    # Act
    hydrated = vision_tools._rehydrate_stac_items_for_sampling(
        items,
        [],
        latitude=0.5,
        longitude=19.5,
    )

    # Assert
    assert len(fetched_ids) == 5
    assert hydrated[0]["id"] == "item-19"
    assert hydrated[0]["assets"]["data"]["href"] == "item-19"


def test_given_assetful_mosaic_when_rehydrating_then_all_items_are_preserved(
    monkeypatch,
) -> None:
    # Arrange
    items = [
        {
            "id": f"item-{index}",
            "collection": "cop-dem",
            "bbox": [index, 0, index + 0.9, 1],
            "assets": {
                "data": {
                    "href": f"https://example.test/item-{index}.tif",
                    "type": "image/tiff",
                }
            },
        }
        for index in range(8)
    ]
    monkeypatch.setattr(
        vision_tools,
        "_fetch_stac_item_sync",
        lambda *_args: pytest.fail("Assetful items must not be refetched."),
    )

    # Act
    hydrated = vision_tools._rehydrate_stac_items_for_sampling(
        items,
        ["https://tiles.example/fallback.json"] * 8,
        latitude=0.5,
        longitude=7.5,
    )

    # Assert
    assert [item["id"] for item in hydrated] == [f"item-{index}" for index in range(8)]
    assert hydrated[7]["assets"]["data"]["href"].endswith("item-7.tif")


def test_given_pro_mode_when_searching_fallback_then_public_catalog_is_not_called(
    monkeypatch,
) -> None:
    # Arrange
    import httpx
    import pro_stac_client

    body = {"collections": ["private-dem"], "bbox": [-122, 47, -121, 48]}
    monkeypatch.setattr(
        pro_stac_client,
        "pro_search_sync",
        lambda search_body: [{"id": "private-item", "search": search_body}],
    )
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_args, **_kwargs: pytest.fail("Public MPC must not receive Pro fallback searches."),
    )

    # Act
    features = vision_tools._search_stac_items_sync(body, "pro")

    # Assert
    assert features == [{"id": "private-item", "search": body}]


def test_given_pro_temporal_query_then_returned_assets_are_sas_authorized(
    monkeypatch,
) -> None:
    # Arrange
    raw_feature = {
        "id": "private-item",
        "collection": "private-dem",
        "assets": {
            "data": {
                "href": "https://account.blob.core.windows.net/private/item.tif"
            }
        },
    }
    prepared_features: list[tuple[str, str]] = []
    monkeypatch.setattr(
        vision_tools,
        "_search_stac_items_sync",
        lambda _body, mode: [raw_feature] if mode == "pro" else [],
    )

    def prepare_item(feature: dict, mode: str) -> dict:
        prepared_features.append((feature["id"], mode))
        return {
            **feature,
            "assets": {
                "data": {"href": f"{feature['assets']['data']['href']}?sv=1&sig=secret"}
            },
        }

    monkeypatch.setattr(vision_tools, "_prepare_stac_item_for_sampling", prepare_item)
    vision_tools.set_session_context(stac_mode="pro")

    # Act
    result = vision_tools._execute_stac_query_sync(
        "private-dem",
        [-122, 47, -121, 48],
        "2025-01-01/2026-01-01",
    )

    # Assert
    assert prepared_features == [("private-item", "pro")]
    assert result["features"][0]["assets"]["data"]["href"].endswith("sig=secret")


def test_given_pro_vision_temporal_compare_then_loaded_private_collection_is_queried(
    monkeypatch,
) -> None:
    # Arrange
    queried_collections: list[str] = []
    monkeypatch.setattr(
        vision_tools,
        "_resolve_location_to_bbox_sync",
        lambda _location: [-122, 47, -121, 48],
    )

    def execute_query(collection: str, _bbox: list[float], _datetime: str, limit: int = 5) -> dict:
        queried_collections.append(collection)
        return {"features": []}

    monkeypatch.setattr(vision_tools, "_execute_stac_query_sync", execute_query)
    vision_tools.set_session_context(
        loaded_collections=["private-dem"],
        stac_mode="pro",
    )

    # Act
    result = vision_tools.compare_temporal("Seattle", "2024", "2025", "surface reflectance")

    # Assert
    assert queried_collections == ["private-dem", "private-dem"]
    assert "No imagery found" in result


@pytest.mark.asyncio
async def test_given_pro_analyst_temporal_compare_then_nested_samples_keep_pro_mode(
    monkeypatch,
) -> None:
    # Arrange
    sampled_modes: list[str] = []

    class _FakeAnalyzer:
        def can_run(self, _request) -> bool:
            return True

        async def analyze(self, request) -> object:
            sampled_modes.append(request.stac_mode)
            return type("Result", (), {
                "model_dump": lambda self: {
                    "success": True,
                    "structured": {"value": 1.0},
                }
            })()

    import pipeline.analyzers.raster_sampling_analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "RasterSamplingAnalyzer", _FakeAnalyzer)
    set_session(AnalystSession(
        session_id="analyst-temporal",
        pin=(47.5, -122.0),
        loaded_collections=["private-dem"],
        stac_mode="pro",
    ))

    # Act
    result = await analyst_tools.compare_temporal("private-dem", "2024", "2025")

    # Assert
    assert sampled_modes == ["pro", "pro"]
    assert result["success"] is True


@pytest.mark.asyncio
async def test_given_raster_request_when_run_then_sampling_executes_off_event_loop(
    monkeypatch,
) -> None:
    # Arrange
    event_loop_thread = threading.get_ident()
    sample_threads: list[int] = []

    def sample_raster_value(*, data_type: str) -> str:
        sample_threads.append(threading.get_ident())
        return f"**Elevation (cop-dem):**\n- Value: **123.00 m**\n{data_type}"

    monkeypatch.setattr(vision_tools, "sample_raster_value", sample_raster_value)
    payload = RasterSamplingInput(
        question="What is the elevation?",
        pin=(47.5, -122.0),
        loaded_collections=["cop-dem"],
        data_type="elevation",
    )

    # Act
    result = await RasterSamplingAgent().run(payload)

    # Assert
    assert result.success is True
    assert sample_threads and sample_threads[0] != event_loop_thread
    assert result.structured["value"] == 123.0
    assert result.structured["unit"] == "m"


@pytest.mark.asyncio
async def test_given_comparison_without_grounding_then_structured_agent_samples_are_used(
    monkeypatch,
) -> None:
    # Arrange
    import agents.raster_sampling_agent as raster_sampling_package

    class _FakeAgent:
        async def run(self, payload: RasterSamplingInput) -> RasterSamplingResult:
            return RasterSamplingResult(
                success=True,
                answer="sampled",
                pin=payload.pin,
                structured={
                    "value": payload.pin[0],
                    "metric": "Elevation",
                    "unit": "m",
                },
            )

    monkeypatch.setattr(
        raster_sampling_package,
        "get_raster_sampling_agent",
        lambda: _FakeAgent(),
    )
    request = AnalysisRequest(
        question="Compare the pins",
        session_id="comparison-session",
        pins=[(10.0, 20.0), (30.0, 40.0)],
        loaded_collections=["cop-dem-glo-30"],
    )

    # Act
    samples, metric, unit = await _sample_pins_inline(request)

    # Assert
    assert [sample["value"] for sample in samples] == [10.0, 30.0]
    assert metric == "Elevation"
    assert unit == "m"


@pytest.mark.asyncio
async def test_given_concurrent_sampling_contexts_then_request_data_remains_isolated(
    monkeypatch,
) -> None:
    # Arrange
    barrier = threading.Barrier(2)

    def inspect_context(*, data_type: str) -> str:
        context = vision_tools._get_session_context()
        barrier.wait(timeout=2)
        return "|".join([
            str(context["map_bounds"]["pin_lat"]),
            context["stac_items"][0]["id"],
            context["stac_mode"],
            data_type,
        ])

    monkeypatch.setattr(vision_tools, "sample_raster_value", inspect_context)
    raster_payload = RasterSamplingInput(
        question="sample public raster",
        pin=(47.1, -122.1),
        stac_items=[{"id": "public-item", "collection": "public-dem"}],
        loaded_collections=["public-dem"],
        stac_mode="public",
        data_type="elevation",
    )

    async def run_direct_vision_context() -> str:
        vision_tools.set_session_context(
            map_bounds={"pin_lat": 40.2, "pin_lng": -74.2},
            stac_items=[{"id": "private-item", "collection": "private-dem"}],
            loaded_collections=["private-dem"],
            stac_mode="pro",
        )
        return await asyncio.to_thread(vision_tools.sample_raster_value, data_type="auto")

    # Act
    raster_result, direct_result = await asyncio.gather(
        RasterSamplingAgent().run(raster_payload),
        run_direct_vision_context(),
    )

    # Assert
    assert raster_result.answer == "47.1|public-item|public|elevation"
    assert direct_result == "40.2|private-item|pro|auto"


@pytest.mark.asyncio
async def test_given_concurrent_worker_tools_then_traces_remain_request_local() -> None:
    # Arrange
    async def record_trace(tool_name: str) -> list[dict]:
        vision_tools.clear_tool_calls()
        await asyncio.to_thread(vision_tools._log_tool_call, tool_name, {"owner": tool_name})
        return vision_tools.get_tool_calls()

    # Act
    first, second = await asyncio.gather(record_trace("first"), record_trace("second"))

    # Assert
    assert [entry["tool"] for entry in first] == ["first"]
    assert [entry["tool"] for entry in second] == ["second"]


@pytest.mark.asyncio
async def test_given_pro_enhanced_vision_when_sampling_then_mode_is_isolated_and_off_thread(
    monkeypatch,
) -> None:
    # Arrange
    event_loop_thread = threading.get_ident()
    sampled_contexts: list[tuple[str, int]] = []
    agent = EnhancedVisionAgent()
    session = VisionSession(session_id="vision-session")

    async def no_initialize() -> None:
        return None

    async def get_session(_session_id: str) -> VisionSession:
        return session

    async def format_sample(**_kwargs) -> dict:
        return {"response": "formatted sample"}

    def sample_raster_value(*, data_type: str) -> str:
        sampled_contexts.append((
            vision_tools._get_session_context()["stac_mode"],
            threading.get_ident(),
        ))
        return f"**Elevation:** {data_type} 10.00 m"

    monkeypatch.setattr(agent, "_ensure_initialized", no_initialize)
    monkeypatch.setattr(agent, "_get_or_create_session", get_session)
    monkeypatch.setattr(agent, "_fallback_direct_openai", format_sample)
    monkeypatch.setattr(vision_tools, "sample_raster_value", sample_raster_value)

    # Act
    result = await agent.analyze(
        user_query="What is the elevation at this point?",
        session_id="vision-session",
        map_bounds={"pin_lat": 47.5, "pin_lng": -122.0},
        collections=["private-cop-dem-glo-30"],
        stac_items=[
            {
                "id": "private-item",
                "collection": "private-cop-dem-glo-30",
                "assets": {"data": {"href": "https://example.test/private.tif"}},
            }
        ],
        stac_mode="pro",
    )

    # Assert
    assert result["response"] == "formatted sample"
    assert len(sampled_contexts) == 1
    assert sampled_contexts[0][0] == "pro"
    assert sampled_contexts[0][1] != event_loop_thread