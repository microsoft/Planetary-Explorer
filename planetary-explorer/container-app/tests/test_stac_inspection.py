"""Tests for deterministic post-load STAC asset inspection."""

import pytest

from pipeline.stac_inspection import (
    apply_collection_inspection_overrides,
    build_collection_asset_inspection_summary,
)


def test_given_pin_when_applying_inspection_overrides_then_collection_and_aoi_are_pinned() -> (
    None
):
    # Arrange
    translated = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [-118.67, 33.7, -118.16, 34.34],
        "datetime": "2026-07-04",
        "location_name": "la",
    }

    # Act
    overridden = apply_collection_inspection_overrides(
        stac_params=translated,
        collection_id="hls2-s30",
        pin={"lat": 50.268, "lng": -89.8572},
    )

    # Assert
    assert overridden["collections"] == ["hls2-s30"]
    assert overridden["datetime"] == "2026-07-04"
    assert overridden["location_name"] == "Pinned location (50.2680, -89.8572)"
    assert overridden["bbox"] == pytest.approx(
        [-89.9706, 50.1955, -89.7438, 50.3405],
        abs=0.0001,
    )
    assert translated["collections"] == ["sentinel-2-l2a"]


def test_given_hls_scene_when_building_asset_inspection_then_reports_actual_fire_bands() -> (
    None
):
    # Arrange
    features = [
        {
            "id": "HLS.S30.T16UEA.2026185T170901.v2.0",
            "collection": "hls2-s30",
            "properties": {"datetime": "2026-07-04T17:09:44Z"},
            "assets": {
                "B02": {"href": "https://example.test/B02.tif"},
                "B04": {"href": "https://example.test/B04.tif"},
                "B8A": {"href": "https://example.test/B8A.tif"},
                "B12": {"href": "https://example.test/B12.tif"},
                "Fmask": {"href": "https://example.test/Fmask.tif"},
            },
        }
    ]

    # Act
    summary = build_collection_asset_inspection_summary(
        features=features,
        collection_id="hls2-s30",
        render_assets=["B12", "B8A", "B04"],
        render_summary="Displaying 1 HLS image.",
        stac_mode="public",
    )

    # Assert
    assert "`B12` (SWIR2) / `B8A` (narrow NIR) / `B04` (red)" in summary
    assert "HLS.S30.T16UEA.2026185T170901.v2.0" in summary
    assert "2026-07-04" in summary
    assert "`Fmask`" in summary
    assert "Public Planetary Computer" in summary


def test_given_other_collection_items_when_building_inspection_then_ignores_their_assets() -> (
    None
):
    # Arrange
    features = [
        {
            "id": "requested-scene",
            "collection": "hls2-s30",
            "properties": {},
            "assets": {"B04": {}, "B8A": {}, "B12": {}},
        },
        {
            "id": "other-scene",
            "collection": "other-collection",
            "properties": {},
            "assets": {"secret": {}},
        },
    ]

    # Act
    summary = build_collection_asset_inspection_summary(
        features=features,
        collection_id="hls2-s30",
        render_assets=None,
        render_summary="Displaying imagery.",
        stac_mode="pro",
    )

    # Assert
    assert "Available recipe" in summary
    assert "`secret`" not in summary
    assert "MPC Pro" in summary


def test_given_pro_remapped_collection_when_building_inspection_then_resolved_assets_are_reported() -> (
    None
):
    # Arrange
    features = [
        {
            "id": "tenant-fire-scene",
            "collection": "tenant-hls-fire",
            "properties": {"datetime": "2026-07-04T17:09:44Z"},
            "assets": {"B04": {}, "B8A": {}, "B12": {}, "Fmask": {}},
        }
    ]

    # Act
    summary = build_collection_asset_inspection_summary(
        features=features,
        collection_id="hls2-s30",
        render_assets=["B12", "B8A", "B04"],
        render_summary="Displaying tenant imagery.",
        stac_mode="pro",
    )

    # Assert
    assert "**Available assets**" in summary
    assert "`tenant-hls-fire` (requested as `hls2-s30`)" in summary
    assert "`B12` (SWIR2) / `B8A` (narrow NIR) / `B04` (red)" in summary
