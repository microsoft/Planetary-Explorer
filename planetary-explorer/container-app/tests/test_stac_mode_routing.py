"""Unit tests for STAC Public/Pro mode routing helpers.

Covers:
  - _apply_stac_mode_override: precedence (body > env > "public").
  - _resolve_stac_endpoint: planetary_computer_pro lookup, fallback when
    MPC_PRO_STAC_URL is unset, and unchanged behavior for public labels.
  - The LoadAgent prompt template renders Pro guard rails when stac_mode='pro'.
"""

from __future__ import annotations

import importlib

import pytest


# ---------------------------------------------------------------------------
# helpers to load fastapi_app's helpers without booting FastAPI
# ---------------------------------------------------------------------------

def _import_helpers(monkeypatch):
    """Import the two helpers from fastapi_app without triggering its
    full Azure-dependent startup. We pull them out of the module's
    namespace; if fastapi_app fails to import we skip the test.
    """
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://stub")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "stub")
    try:
        fastapi_app = importlib.import_module("fastapi_app")
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"fastapi_app import failed in test env: {exc}")
    return fastapi_app._apply_stac_mode_override, fastapi_app._resolve_stac_endpoint


# ---------------------------------------------------------------------------
# _apply_stac_mode_override
# ---------------------------------------------------------------------------

def test_apply_stac_mode_body_wins_over_env(monkeypatch):
    apply, _ = _import_helpers(monkeypatch)
    monkeypatch.setenv("DEFAULT_STAC_MODE", "pro")
    # body says public -> public, ignore env
    assert apply("planetary_computer", {"stac_mode": "public"}) == "planetary_computer"


def test_apply_stac_mode_env_fallback_pro(monkeypatch):
    apply, _ = _import_helpers(monkeypatch)
    monkeypatch.setenv("DEFAULT_STAC_MODE", "pro")
    assert apply("planetary_computer", {}) == "planetary_computer_pro"
    assert apply("veda", None) == "planetary_computer_pro"


def test_apply_stac_mode_defaults_to_public_when_unset(monkeypatch):
    apply, _ = _import_helpers(monkeypatch)
    monkeypatch.delenv("DEFAULT_STAC_MODE", raising=False)
    assert apply("planetary_computer", {}) == "planetary_computer"
    assert apply("veda", {}) == "veda"


def test_apply_stac_mode_body_pro_forces_pro(monkeypatch):
    apply, _ = _import_helpers(monkeypatch)
    monkeypatch.delenv("DEFAULT_STAC_MODE", raising=False)
    assert apply("veda", {"stac_mode": "pro"}) == "planetary_computer_pro"


# ---------------------------------------------------------------------------
# _resolve_stac_endpoint
# ---------------------------------------------------------------------------

def test_resolve_pro_endpoint_uses_env(monkeypatch):
    _, resolve = _import_helpers(monkeypatch)
    monkeypatch.setenv(
        "MPC_PRO_STAC_URL",
        "https://x.geocatalog.spatio.azure.com/stac",
    )
    url, label, is_pro = resolve("planetary_computer_pro")
    assert is_pro is True
    assert label == "planetary_computer_pro"
    assert url == "https://x.geocatalog.spatio.azure.com/stac/search"


def test_resolve_pro_refuses_silent_fallback_when_env_missing(monkeypatch):
    """When Pro is requested but ``MPC_PRO_STAC_URL`` is unset, the resolver
    must NOT silently fall back to public PC -- the user explicitly toggled
    Pro and returning Public results would misrepresent the data source.
    Instead, it returns the sentinel label ``planetary_computer_pro_unconfigured``
    with ``is_pro=True`` and an empty url, which causes
    ``execute_direct_stac_search`` to short-circuit with a clear error.
    """
    _, resolve = _import_helpers(monkeypatch)
    for var in ("MPC_PRO_STAC_URL", "PC_DATA_API_URL", "STAC_API_URL"):
        monkeypatch.delenv(var, raising=False)
    url, label, is_pro = resolve("planetary_computer_pro")
    assert is_pro is True
    assert label == "planetary_computer_pro_unconfigured"
    assert url == ""


def test_resolve_public_unchanged(monkeypatch):
    _, resolve = _import_helpers(monkeypatch)
    url, label, is_pro = resolve("planetary_computer")
    assert is_pro is False
    assert label == "planetary_computer"


def test_pro_remap_returns_one_best_match_per_requested_collection(monkeypatch):
    # Arrange
    _import_helpers(monkeypatch)
    fastapi_app = importlib.import_module("fastapi_app")

    # Act
    remapped = fastapi_app._remap_collections_for_pro(
        ["hls2-s30"],
        [
            {"id": "archive-hls2-s30-copy"},
            {"id": "hls2-s30-prod"},
        ],
    )

    # Assert
    assert remapped == ["hls2-s30-prod"]


def test_pro_remap_token_tie_is_independent_of_inventory_order(monkeypatch):
    # Arrange
    _import_helpers(monkeypatch)
    fastapi_app = importlib.import_module("fastapi_app")
    inventory = [
        {"id": "tenant-z", "title": "HLS S30 archive"},
        {"id": "tenant-a", "title": "HLS S30 primary"},
    ]

    # Act
    forward = fastapi_app._remap_collections_for_pro(["hls2-s30"], inventory)
    reverse = fastapi_app._remap_collections_for_pro(
        ["hls2-s30"],
        list(reversed(inventory)),
    )

    # Assert
    assert forward == reverse == ["tenant-a"]


def test_v2_locked_load_owns_legacy_router_bridge(monkeypatch):
    # Arrange
    _import_helpers(monkeypatch)
    fastapi_app = importlib.import_module("fastapi_app")

    # Act
    action = fastapi_app._router_action_for_v2_load(
        {
            "_v2_load_turn": True,
            "_v2_post_load_inspection": {"collection_id": "tenant-fire"},
            "has_satellite_data": True,
        }
    )

    # Assert
    assert action == {
        "action_type": "stac_search",
        "needs_stac_search": True,
        "needs_vision_analysis": False,
        "use_current_location": True,
        "collection_hint": "tenant-fire",
        "routing_reason": "v2_load_authoritative",
    }


# ---------------------------------------------------------------------------
# LoadAgent prompt template renders Pro guard rails
# ---------------------------------------------------------------------------

def test_load_agent_prompt_includes_pro_block():
    from prompts.load_agent_prompt import LOAD_AGENT_USER_PROMPT_TEMPLATE

    rendered = LOAD_AGENT_USER_PROMPT_TEMPLATE.format(
        query="show tenant aerial imagery over Jasper, Alberta in 2026",
        has_rendered_map=False,
        loaded_collections="",
        has_bbox=False,
        bbox=None,
        has_time_range=False,
        time_range=None,
        has_pin=False,
        pin_lat_lng="null",
        location_name="Jasper, Alberta, Canada",
        layer1_stac_query="null",
        layer1_reasoning="null",
        stac_mode="pro",
        available_pro_collections="canada-aerial-2026",
        catalog_matches="canada-aerial-2026",
        prior_query="null",
        prior_clarification_question="null",
        prior_clarification_options="",
        prior_collection_candidates="",
        clarification_round=0,
        prior_clarification_history="(none)",
    )
    assert "stac_mode=pro" in rendered
    assert "available_pro_collections=[canada-aerial-2026]" in rendered
    # Critical anti-pattern guard: prompt must steer LLM away from
    # public PC collection ids when in Pro mode.
    assert "pro mode" in rendered.lower()


def test_load_agent_system_prompt_forbids_loading_prefix_on_clarify():
    from prompts.load_agent_prompt import LOAD_AGENT_SYSTEM_PROMPT

    # The "fix 2-4" regression: clarify path must NOT say "Loading ..."
    # because the map is unchanged. The prompt's bad-example block calls
    # out the verbatim Grand Canyon failure mode.
    lower = LOAD_AGENT_SYSTEM_PROMPT.lower()
    assert "loading imagery for grand canyon" in lower or "rendering tiles now" in lower
    # And the explicit forbid is present
    assert "must not say" in lower or "must not start" in lower


@pytest.mark.asyncio
async def test_locked_collection_skips_v2_selector(monkeypatch):
    # Arrange
    monkeypatch.setenv("COLLECTION_SELECTOR", "v2")
    monkeypatch.delenv("MPC_PRO_STAC_URL", raising=False)
    fastapi_app = importlib.import_module("fastapi_app")

    async def unexpected_selector(*_args, **_kwargs):
        raise AssertionError("Locked inspection collection must bypass selector")

    import collection_selector

    monkeypatch.setattr(collection_selector, "select_collection", unexpected_selector)

    # Act
    result = await fastapi_app.execute_direct_stac_search(
        {"collections": ["wrong-collection"]},
        "planetary_computer_pro",
        original_query="Inspect tenant-fire assets at this pin",
        locked_collection="tenant-fire",
    )

    # Assert
    assert result["stac_mode"] == "pro"
    assert "not configured" in result["error"]


@pytest.mark.asyncio
async def test_alternative_queries_preserve_locked_collection(monkeypatch):
    # Arrange
    fastapi_app = importlib.import_module("fastapi_app")
    calls = []

    async def capture_search(stac_query, _endpoint, **kwargs):
        calls.append((dict(stac_query), kwargs.get("locked_collection")))
        return {"success": True, "results": {"features": []}}

    monkeypatch.setattr(
        fastapi_app,
        "execute_direct_stac_search",
        capture_search,
    )

    # Act
    result = await fastapi_app.try_alternative_queries(
        "Inspect sentinel-2-l2a assets at this pin",
        {
            "collections": ["sentinel-2-l2a"],
            "datetime": "2026-07-04T00:00:00Z/2026-07-04T23:59:59Z",
        },
        {},
        None,
        "planetary_computer",
        [-89.97, 50.19, -89.74, 50.34],
        locked_collection="sentinel-2-l2a",
    )

    # Assert
    assert result["success"] is False
    assert calls
    assert all(lock == "sentinel-2-l2a" for _query, lock in calls)
    assert all(
        query["collections"] == ["sentinel-2-l2a"]
        for query, _lock in calls
    )
