"""Point-AOI coverage tests for STAC tile selection."""

from tile_selector import TileSelector


def _hls_feature(
    item_id: str,
    *,
    cloud_cover: float,
    polygon: list[list[float]],
) -> dict:
    return {
        "id": item_id,
        "collection": "hls2-s30",
        "bbox": [-90.24, 49.48, -88.63, 50.52],
        "geometry": {"type": "Polygon", "coordinates": [polygon]},
        "properties": {
            "datetime": "2026-07-04T17:09:44Z",
            "eo:cloud_cover": cloud_cover,
        },
    }


def test_given_small_aoi_when_ranking_same_grid_scenes_then_covering_geometry_wins() -> (
    None
):
    # Arrange
    query_bbox = [-89.9706, 50.1955, -89.7438, 50.3405]
    misses_pin = _hls_feature(
        "HLS.S30.T15UYR.noncovering.v2.0",
        cloud_cover=0,
        polygon=[
            [-90.2, 49.5],
            [-90.0, 49.5],
            [-90.0, 50.5],
            [-90.2, 50.5],
            [-90.2, 49.5],
        ],
    )
    covers_pin = _hls_feature(
        "HLS.S30.T15UYR.covering.v2.0",
        cloud_cover=100,
        polygon=[
            [-90.0, 50.1],
            [-89.7, 50.1],
            [-89.7, 50.4],
            [-90.0, 50.4],
            [-90.0, 50.1],
        ],
    )

    # Act
    selected = TileSelector.select_best_tiles(
        [misses_pin, covers_pin],
        query_bbox=query_bbox,
        collections=["hls2-s30"],
        max_tiles=2,
        query="Inspect fire-composite bands at the pinned location",
    )

    # Assert
    assert selected[0]["id"] == covers_pin["id"]


def test_given_pro_style_results_when_prioritizing_then_covering_geometry_is_first() -> (
    None
):
    # Arrange
    query_bbox = [-89.9706, 50.1955, -89.7438, 50.3405]
    misses_pin = _hls_feature(
        "tenant-fire.noncovering",
        cloud_cover=0,
        polygon=[
            [-90.2, 49.5],
            [-90.0, 49.5],
            [-90.0, 50.5],
            [-90.2, 50.5],
            [-90.2, 49.5],
        ],
    )
    covers_pin = _hls_feature(
        "tenant-fire.covering",
        cloud_cover=100,
        polygon=[
            [-90.0, 50.1],
            [-89.7, 50.1],
            [-89.7, 50.4],
            [-90.0, 50.4],
            [-90.0, 50.1],
        ],
    )

    # Act
    ordered = TileSelector.prioritize_center_covering_features(
        [misses_pin, covers_pin],
        query_bbox,
    )

    # Assert
    assert ordered[0]["id"] == covers_pin["id"]


def test_given_newer_noncovering_date_when_selecting_then_covering_date_is_retained() -> (
    None
):
    # Arrange
    query_bbox = [-89.9706, 50.1955, -89.7438, 50.3405]
    misses_pin = _hls_feature(
        "HLS.S30.T15UYR.newer-noncovering.v2.0",
        cloud_cover=0,
        polygon=[
            [-90.2, 49.5],
            [-90.0, 49.5],
            [-90.0, 50.5],
            [-90.2, 50.5],
            [-90.2, 49.5],
        ],
    )
    misses_pin["properties"]["datetime"] = "2026-07-05T17:09:44Z"
    covers_pin = _hls_feature(
        "HLS.S30.T15UYR.older-covering.v2.0",
        cloud_cover=100,
        polygon=[
            [-90.0, 50.1],
            [-89.7, 50.1],
            [-89.7, 50.4],
            [-90.0, 50.4],
            [-90.0, 50.1],
        ],
    )

    # Act
    selected = TileSelector.select_best_tiles(
        [misses_pin, covers_pin],
        query_bbox=query_bbox,
        collections=["hls2-s30"],
        max_tiles=2,
        query="Inspect fire-composite bands at the pinned location",
    )

    # Assert
    assert [feature["id"] for feature in selected] == [covers_pin["id"]]


def test_given_large_aoi_when_ranking_then_center_geometry_does_not_override_overlap() -> (
    None
):
    # Arrange
    feature = _hls_feature(
        "HLS.S30.T15UYR.regional.v2.0",
        cloud_cover=0,
        polygon=[
            [-90.2, 49.5],
            [-90.0, 49.5],
            [-90.0, 50.5],
            [-90.2, 50.5],
            [-90.2, 49.5],
        ],
    )

    # Act
    scores = TileSelector._score_tile(
        feature,
        [-91.0, 49.0, -88.0, 51.0],
        ["hls2-s30"],
        TileSelector._determine_scoring_weights(None),
    )

    # Assert
    assert scores["coverage"] > 0
