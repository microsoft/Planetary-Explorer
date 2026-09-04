"""Tests for the intent-aware STAC ``renders`` preset picker.

These cover the Step-1 fix that solves the white-tile bug for thematic
queries against multi-band optical collections (e.g. "Sentinel-2 fire
images of California" picking the SWIR preset instead of the default
true-color preset). The picker is intentionally driven only by token
matches against preset key/title/description text plus a tiny generic
synonym map — there are no hardcoded ``(collection, keyword) -> preset``
tables to maintain.
"""

from __future__ import annotations

from hybrid_rendering_system import (
    EXPLICIT_RENDER_CONFIGS,
    HybridRenderingSystem,
    _SCENE_STRETCH_CACHE,
    _get_scene_percentile_stretches,
    is_scene_aware_fire_render,
    _pick_preset,
    _pick_preset_by_intent,
    _score_preset,
    _tokenize_query,
)


# A renders block shaped like Public PC ``sentinel-2-l2a`` (subset).
S2_RENDERS = {
    "natural-color": {
        "title": "Natural color",
        "description": "True-color RGB composite using bands B04, B03, B02.",
        "assets": ["B04", "B03", "B02"],
        "rescale": [[0, 4000], [0, 4000], [0, 4000]],
    },
    "swir": {
        "title": "False Color (SWIR / Fire & Burn Scars)",
        "description": "SWIR false-color B12/B11/B8A — highlights active fire and burn scars.",
        "assets": ["B12", "B11", "B8A"],
        "rescale": [[0, 6000], [0, 6000], [0, 4000]],
    },
    "ndvi": {
        "title": "Normalized Difference Vegetation Index",
        "description": "Vegetation greenness index from NIR and Red bands.",
        "assets": ["B08", "B04"],
        "expression": "(B08-B04)/(B08+B04)",
    },
    "agriculture": {
        "title": "Agriculture",
        "description": "Vegetation health composite using B11, B08, B02.",
        "assets": ["B11", "B08", "B02"],
    },
}


def test_landsat_l2_uses_supported_tile_scale():
    config = EXPLICIT_RENDER_CONFIGS["landsat-c2-l2"]

    assert config.tile_scale == 2


def test_modis_gpp_uses_catalog_asset_name():
    config = EXPLICIT_RENDER_CONFIGS["modis-17A2H-061"]

    assert config.assets == ["Gpp_500m"]
    assert config.colormap == "modis-17A2H|A2HGF"
    assert config.rescale is None


def test_fire_query_picks_swir_preset():
    key, preset, matched = _pick_preset_by_intent(S2_RENDERS, "Show Sentinel-2 fire images of California")
    assert key == "swir", f"expected swir preset for fire query, got {key!r}"
    assert preset["assets"] == ["B12", "B11", "B8A"]
    assert matched is True


def test_burn_scar_query_picks_swir_preset():
    key, _, matched = _pick_preset_by_intent(S2_RENDERS, "burned area Paradise CA")
    assert key == "swir"
    assert matched is True


def test_vegetation_query_picks_ndvi_or_agriculture():
    key, _, matched = _pick_preset_by_intent(S2_RENDERS, "vegetation index over the Amazon")
    # Both ndvi and agriculture match; ndvi scores higher on key+title.
    assert key in {"ndvi", "agriculture"}
    assert matched is True


def test_empty_query_falls_back_to_default_or_first():
    # No "default" key in this fixture -> first dict-valued key wins.
    key, _, matched = _pick_preset_by_intent(S2_RENDERS, "")
    assert key == "natural-color"
    assert matched is False


def test_none_query_falls_back_to_default_or_first():
    key, _, matched = _pick_preset_by_intent(S2_RENDERS, None)
    assert key == "natural-color"
    assert matched is False


def test_default_key_wins_when_present_and_no_signal():
    renders = {
        "default": {"title": "Default", "assets": ["visual"]},
        "swir": {"title": "SWIR", "assets": ["B12", "B11", "B8A"]},
    }
    key, _, matched = _pick_preset_by_intent(renders, "satellite data")
    assert key == "default"
    assert matched is False


def test_query_with_no_intent_signal_falls_back():
    # No preset has tokens matching "elevation"; tier-3 returns default-or-first.
    key, _, matched = _pick_preset_by_intent(S2_RENDERS, "elevation contours")
    assert key == "natural-color"
    assert matched is False


def test_pick_preset_legacy_default_or_first():
    # Backward-compat path used by callers that don't pass a query.
    key, _ = _pick_preset(S2_RENDERS)
    assert key == "natural-color"


def test_tokenizer_strips_stopwords_and_expands_synonyms():
    toks = _tokenize_query("Show me the fire images of California")
    assert "fire" in toks
    assert "swir" in toks  # synonym expansion
    assert "burn" in toks  # synonym expansion
    assert "show" not in toks  # stopword
    assert "the" not in toks


def test_score_weights_key_above_title_above_description():
    preset = {"title": "fire", "description": "fire fire fire"}
    # Key contains "fire" -> 3, title contains "fire" -> 2, desc has 3 "fire" -> 3.
    # _score_preset uses substring containment (not count) so desc adds only 1.
    s = _score_preset("fire-preset", preset, ["fire"])
    assert s == 3 + 2 + 1


def test_empty_renders_returns_none():
    key, preset, matched = _pick_preset_by_intent({}, "fire")
    assert key is None and preset is None
    assert matched is False


def test_hls_s30_fire_query_uses_explicit_false_colour_profile(monkeypatch):
    monkeypatch.setattr(
        "hybrid_rendering_system.fetch_renders_config",
        lambda *args, **kwargs: None,
    )

    config = HybridRenderingSystem.get_render_config(
        "hls2-s30",
        "Show HLS S30 fire imagery near Thunder Bay",
    )

    assert config.assets == ["B12", "B8A", "B04"]
    assert "explicit-intent" in config.notes
    assert is_scene_aware_fire_render(config) is True


def test_hls_s30_query_without_fire_intent_keeps_natural_colour(monkeypatch):
    monkeypatch.setattr(
        "hybrid_rendering_system.fetch_renders_config",
        lambda *args, **kwargs: None,
    )

    config = HybridRenderingSystem.get_render_config(
        "hls2-s30",
        "Show HLS S30 imagery near Thunder Bay",
    )

    assert config.assets == ["B04", "B03", "B02"]
    assert "explicit-intent" not in config.notes
    assert is_scene_aware_fire_render(config) is False


def test_hls_s30_pro_query_does_not_claim_public_scene_statistics(monkeypatch):
    monkeypatch.setattr(
        "hybrid_rendering_system.fetch_renders_config",
        lambda *args, **kwargs: None,
    )

    config = HybridRenderingSystem.get_render_config(
        "hls2-s30",
        "Show wildfire imagery",
        is_pro=True,
    )

    assert config.assets == ["B04", "B03", "B02"]
    assert is_scene_aware_fire_render(config) is False


def test_fire_tile_url_uses_one_scene_stretch_per_asset(monkeypatch):
    monkeypatch.setattr(
        "hybrid_rendering_system.fetch_renders_config",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "hybrid_rendering_system._get_scene_percentile_stretches",
        lambda *args: ((3.0, 3486.0), (0.0, 4950.0), (0.0, 3320.0)),
    )

    url = HybridRenderingSystem.build_titiler_tilejson_url(
        "HLS.S30.T15UYR.2026185T165839.v2.0",
        "hls2-s30",
        query_context="Show fire false-colour HLS S30 imagery",
    )

    assert "assets=B12&assets=B8A&assets=B04" in url
    assert url.count("rescale=") == 3
    assert "rescale=3,3486&rescale=0,4950&rescale=0,3320" in url
    assert "rescale=0.0,5000.0" not in url


def test_scene_stretch_is_cached(monkeypatch):
    class StatisticsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "B12_b1": {"percentile_2": 3, "percentile_98": 3486},
                "B8A_b1": {"percentile_2": -3, "percentile_98": 4950},
                "B04_b1": {"percentile_2": -72, "percentile_98": 3320},
            }

    calls = []

    def get_statistics(*args, **kwargs):
        calls.append((args, kwargs))
        return StatisticsResponse()

    _SCENE_STRETCH_CACHE.clear()
    monkeypatch.setattr("hybrid_rendering_system.requests.get", get_statistics)

    first = _get_scene_percentile_stretches(
        "hls2-s30",
        "HLS.S30.TEST",
        ("B12", "B8A", "B04"),
    )
    second = _get_scene_percentile_stretches(
        "hls2-s30",
        "HLS.S30.TEST",
        ("B12", "B8A", "B04"),
    )

    assert first == ((3.0, 3486.0), (0.0, 4950.0), (0.0, 3320.0))
    assert second == first
    assert len(calls) == 1


def test_scene_stretch_cache_evicts_oldest_entry(monkeypatch):
    class StatisticsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "B12_b1": {"percentile_2": 3, "percentile_98": 3486},
                "B8A_b1": {"percentile_2": 0, "percentile_98": 4950},
                "B04_b1": {"percentile_2": 0, "percentile_98": 3320},
            }

    _SCENE_STRETCH_CACHE.clear()
    monkeypatch.setattr(
        "hybrid_rendering_system._SCENE_STRETCH_CACHE_MAX_ENTRIES",
        2,
    )
    monkeypatch.setattr(
        "hybrid_rendering_system.requests.get",
        lambda *args, **kwargs: StatisticsResponse(),
    )

    for item_id in ("HLS.S30.ONE", "HLS.S30.TWO", "HLS.S30.THREE"):
        _get_scene_percentile_stretches(
            "hls2-s30",
            item_id,
            ("B12", "B8A", "B04"),
        )

    assert len(_SCENE_STRETCH_CACHE) == 2
    assert not any(key[1] == "HLS.S30.ONE" for key in _SCENE_STRETCH_CACHE)


def test_invalid_scene_statistics_keep_static_fire_fallback(monkeypatch):
    class InvalidStatisticsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "B12_b1": {"percentile_2": 10, "percentile_98": 20},
                "B8A_b1": {"percentile_2": 0, "percentile_98": 4950},
                "B04_b1": {"percentile_2": 0, "percentile_98": 3320},
            }

    _SCENE_STRETCH_CACHE.clear()
    monkeypatch.setattr(
        "hybrid_rendering_system.fetch_renders_config",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "hybrid_rendering_system.requests.get",
        lambda *args, **kwargs: InvalidStatisticsResponse(),
    )

    url = HybridRenderingSystem.build_titiler_tilejson_url(
        "HLS.S30.INVALID",
        "hls2-s30",
        query_context="Show wildfire imagery",
    )

    assert "assets=B12&assets=B8A&assets=B04" in url
    assert url.count("rescale=") == 1
    assert "rescale=0.0,5000.0" in url
