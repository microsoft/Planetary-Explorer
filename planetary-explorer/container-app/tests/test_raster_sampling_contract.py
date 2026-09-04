"""Raster sampling intent and success-contract tests."""

from __future__ import annotations

import pytest

from agents.raster_sampling_agent.raster_sampling_agent import (
    RasterSamplingAgent,
    _parse_numeric_samples,
    _parse_sample_provenance,
    _parse_sampled_scenes,
)
from agents.raster_sampling_agent.raster_sampling_models import RasterSamplingInput
from agents.vision_tools import (
    _asset_scale_offset,
    _prepare_stac_item_for_sampling,
    _rehydrate_stac_items_for_sampling,
)
from pipeline.analyzers.raster_sampling_analyzer import _infer_raster_data_type


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Sample the exact elevation in metres at this pin.", "elevation"),
        ("Sample NDVI and EVI at this field.", "vegetation"),
        ("What are the MaxFRP and FireMask values?", "fire"),
        ("What is gross primary productivity here?", "gpp"),
        ("What are VV and VH backscatter values?", "sar"),
        ("Sample green, near-infrared, and SWIR reflectance.", "reflectance"),
        ("Sample the NDSI snow cover value.", "snow"),
    ],
)
def test_given_explicit_metric_when_inferring_then_data_type_is_deterministic(
    question,
    expected,
) -> None:
    assert _infer_raster_data_type(question) == expected


@pytest.mark.asyncio
async def test_given_warning_only_sample_when_running_then_result_is_failure(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setattr(
        "agents.vision_tools.sample_raster_value",
        lambda data_type: "Sampling returned no values for the requested point.",
    )
    monkeypatch.setattr(
        "agents.vision_tools.set_session_context", lambda **_kwargs: None
    )
    payload = RasterSamplingInput(
        question="Sample elevation.",
        pin=(51.18, -115.57),
        loaded_collections=["cop-dem-glo-30"],
        data_type="elevation",
    )

    # Act
    result = await RasterSamplingAgent().run(payload)

    # Assert
    assert result.success is False
    assert result.error == "Sampling returned no numeric value."


@pytest.mark.asyncio
async def test_given_provenance_output_when_running_then_evidence_is_structured(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "agents.vision_tools.sample_raster_value",
        lambda data_type: (
            "**Elevation (cop-dem-glo-30):**\n"
            "- Value: **123.00 m**\n"
            "- Item: dem-scene\n"
            "- Date: 2021-04-22\n"
            f"- Type: {data_type}"
        ),
    )
    monkeypatch.setattr(
        "agents.vision_tools.set_session_context", lambda **_kwargs: None
    )
    payload = RasterSamplingInput(
        question="Sample elevation.",
        pin=(51.18, -115.57),
        loaded_collections=["cop-dem-glo-30"],
        data_type="elevation",
    )

    result = await RasterSamplingAgent().run(payload)

    assert result.success is True
    assert result.structured["sampled_item_ids"] == ["dem-scene"]
    assert result.structured["sampled_dates"] == ["2021-04-22"]


def test_given_multiband_output_when_parsing_then_metrics_remain_aligned() -> None:
    text = """
**Surface Reflectance (B03) (sentinel-2-l2a):**
- Raw: 1000.00 scaled
- Converted: **0.10 reflectance**

**Surface Reflectance (B11) (sentinel-2-l2a):**
- Raw: 2000.00 scaled
- Converted: **0.20 reflectance**
"""

    assert _parse_numeric_samples(text) == [
        {
            "metric": "Surface Reflectance (B03) (sentinel-2-l2a)",
            "value": 0.1,
            "unit": "reflectance",
        },
        {
            "metric": "Surface Reflectance (B11) (sentinel-2-l2a)",
            "value": 0.2,
            "unit": "reflectance",
        },
    ]


def test_given_sample_output_when_parsing_then_scene_provenance_is_preserved() -> None:
    text = """
**Elevation (cop-dem-glo-30):**
- Value: **123.00 m**
- Item: Copernicus_DSM_COG_10_N51_00_W116_00_DEM
- Date: 2021-04-22
"""

    assert _parse_sample_provenance(text) == (
        ["Copernicus_DSM_COG_10_N51_00_W116_00_DEM"],
        ["2021-04-22"],
    )


def test_given_split_item_and_date_blocks_when_parsing_then_they_are_not_joined() -> (
    None
):
    text = """
**First sample:**
- Value: **1.00 raw**
- Item: expected-scene
**Second sample:**
- Value: **2.00 raw**
- Date: 2026-06-15
"""

    assert _parse_sampled_scenes(text) == [
        {"item_id": "expected-scene", "date": ""},
    ]
    assert _parse_sample_provenance(text) == (["expected-scene"], [""])


def test_given_static_sample_without_date_when_parsing_then_item_is_preserved() -> None:
    text = """
**Elevation (cop-dem-glo-30):**
- Value: **123.00 m**
- Item: Copernicus_DSM_COG_10_N51_00_W116_00_DEM
"""

    assert _parse_sampled_scenes(text) == [
        {
            "item_id": "Copernicus_DSM_COG_10_N51_00_W116_00_DEM",
            "date": "",
        }
    ]


def test_given_public_item_and_pro_toggle_when_preparing_then_public_signer_is_used(
    monkeypatch,
) -> None:
    signed_modes = []
    monkeypatch.setattr(
        "planetary_computer.sign",
        lambda item: signed_modes.append("public") or item,
    )
    monkeypatch.setattr(
        "pro_stac_client.pro_sign_item_assets_sync",
        lambda item: signed_modes.append("pro") or item,
    )

    _prepare_stac_item_for_sampling(
        {"id": "public-scene", "stac_mode": "public"},
        "pro",
    )

    assert signed_modes == ["public"]


def test_given_public_id_only_item_and_pro_toggle_when_rehydrating_then_public_catalog_is_used(
    monkeypatch,
) -> None:
    fetched_modes = []
    monkeypatch.setattr(
        "agents.vision_tools._fetch_stac_item_sync",
        lambda collection, item_id: (
            fetched_modes.append("public")
            or {
                "id": item_id,
                "collection": collection,
                "assets": {"data": {"href": "https://example.test/dem.tif"}},
            }
        ),
    )
    monkeypatch.setattr(
        "agents.vision_tools._fetch_pro_stac_item_sync",
        lambda *_args: fetched_modes.append("pro") or None,
    )
    monkeypatch.setattr("planetary_computer.sign", lambda item: item)

    items = _rehydrate_stac_items_for_sampling(
        [
            {
                "id": "public-scene",
                "collection": "cop-dem-glo-30",
                "stac_mode": "public",
            }
        ],
        [],
        stac_mode="pro",
    )

    assert fetched_modes == ["public"]
    assert items[0]["stac_mode"] == "public"
    assert items[0]["assets"]


def test_given_landsat_asset_when_scaling_then_collection_two_offset_is_used() -> None:
    assert _asset_scale_offset({}, "landsat-c2-l2") == (0.0000275, -0.2)
    assert _asset_scale_offset(
        {"raster:bands": [{"scale": 0.5, "offset": 2}]},
        "landsat-c2-l2",
    ) == (0.5, 2.0)
