"""
FastAPI dispatch helper for the v2 pipeline.

`run_pipeline_v2()` is a thin async function that:
  1. Builds an `AnalysisRequest` from the raw `/api/query` request body.
  2. Runs Layer 1 (ActionRouter).
  3. If the action is ANALYZE / LOAD_AND_ANALYZE, runs Layer 2 + the
     Orchestrator and returns a `SynthesizedResponse`-shaped dict.
  4. Otherwise hands back a small dict the FastAPI layer can interpret to
     drive NAVIGATE / LOAD using the legacy code paths (until Stage 4).

Returning a dict (not a JSONResponse) lets the caller wrap it however the
existing endpoint shape requires.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from .bootstrap import build_default_pipeline
from .contracts import AnalysisRequest
from .action_router import is_explicit_web_request

logger = logging.getLogger(__name__)

_COLLECTION_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bhls[\s_-]+s30\b", re.IGNORECASE), "hls2-s30"),
    (re.compile(r"\bhls[\s_-]+l30\b", re.IGNORECASE), "hls2-l30"),
)


def _unloaded_collection_for_asset_inspection(
    request: AnalysisRequest,
    collection_ids: list[str] | None = None,
) -> str | None:
    """Return an explicitly named collection that must be loaded first."""
    query = request.question.casefold()
    if not re.search(r"\b(?:assets?|bands?)\b", query):
        return None
    if not (request.pin or request.bbox or request.location_name):
        return None

    if collection_ids is None:
        try:
            from pc_tasks_config_loader import get_all_collection_ids

            collection_ids = get_all_collection_ids()
        except Exception:
            logger.exception("[PIPELINE-V2] collection catalog lookup failed")
            return None

    loaded_with_metadata = {
        str(meta.get("id") or meta.get("collection")).casefold()
        for meta in request.loaded_collections_meta
        if (meta.get("id") or meta.get("collection"))
        and meta.get("asset_keys")
        and str(meta.get("stac_mode") or "").casefold()
        == request.stac_mode.casefold()
    }
    mentioned_collections: list[str] = []
    available_collections = {
        collection_id.casefold(): collection_id for collection_id in collection_ids
    }
    for alias_pattern, canonical_id in _COLLECTION_ALIASES:
        collection_id = available_collections.get(canonical_id)
        if alias_pattern.search(query) and collection_id:
            mentioned_collections.append(collection_id)
    for collection_id in sorted(collection_ids, key=len, reverse=True):
        normalized = collection_id.casefold()
        if re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            query,
        ) and collection_id not in mentioned_collections:
            mentioned_collections.append(collection_id)

    if not mentioned_collections:
        current_collections = list(dict.fromkeys(request.loaded_collections))
        if request.geoint_module == "foundation_change":
            mentioned_collections = ["hls2-s30"]
        elif len(current_collections) == 1:
            mentioned_collections = current_collections

    for collection_id in mentioned_collections:
        if collection_id.casefold() not in loaded_with_metadata:
            return collection_id
    return None


async def _collection_ids_for_asset_inspection(
    request: AnalysisRequest,
) -> list[str] | None:
    """Return live collection IDs when the request targets MPC Pro."""
    query = request.question.casefold()
    if (
        request.stac_mode != "pro"
        or not re.search(r"\b(?:assets?|bands?)\b", query)
        or not (request.pin or request.bbox or request.location_name)
    ):
        return None
    try:
        from pc_tasks_config_loader import get_all_collection_ids
        from pro_stac_client import get_pro_collection_ids

        canonical_ids = get_all_collection_ids()
        pro_ids = await get_pro_collection_ids()
        return list(dict.fromkeys([*canonical_ids, *pro_ids]))
    except Exception:
        logger.exception("[PIPELINE-V2] Pro collection inventory lookup failed")
        return None


def _extract_collection_meta(stac_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build compact per-collection metadata from raw STAC item dicts.

    The Layer 2 router uses asset/band keys + gsd to disambiguate optical RGB
    (vision) from single-band thermal/SST/elevation (raster_sampling/terrain)
    from cubes (netcdf_computation). One entry per unique collection_id.
    """
    by_collection: dict[str, dict[str, Any]] = {}
    for item in stac_items:
        if not isinstance(item, dict):
            continue
        cid = item.get("collection") or item.get("collection_id")
        if not cid:
            continue
        meta = by_collection.setdefault(
            cid,
            {
                "id": cid,
                "title": (item.get("properties") or {}).get("title")
                or (item.get("properties") or {}).get("description"),
                "asset_keys": [],
                "band_names": [],
                "gsd": None,
                "eo_cloud_cover": None,
                "stac_mode": item.get("stac_mode")
                or item.get("_planetary_explorer_stac_mode"),
            },
        )
        assets = item.get("assets") or {}
        if isinstance(assets, dict):
            for k in assets.keys():
                if k not in meta["asset_keys"]:
                    meta["asset_keys"].append(k)
            for asset in assets.values():
                if not isinstance(asset, dict):
                    continue
                eo_bands = asset.get("eo:bands") or []
                if isinstance(eo_bands, list):
                    for b in eo_bands:
                        name = b.get("name") if isinstance(b, dict) else None
                        if name and name not in meta["band_names"]:
                            meta["band_names"].append(name)
        props = item.get("properties") or {}
        if isinstance(props, dict):
            if meta["gsd"] is None and props.get("gsd") is not None:
                meta["gsd"] = props["gsd"]
            if meta["eo_cloud_cover"] is None and props.get("eo:cloud_cover") is not None:
                meta["eo_cloud_cover"] = props["eo:cloud_cover"]
    return list(by_collection.values())


def _build_request(body: dict[str, Any]) -> AnalysisRequest:
    pin = body.get("pin") or {}
    pin_tuple = None
    if isinstance(pin, dict) and pin.get("lat") is not None and pin.get("lng") is not None:
        pin_tuple = (float(pin["lat"]), float(pin["lng"]))

    # Multi-pin comparison support. Accepts `pins: [{lat,lng}, ...]` or
    # `pins: [[lat,lng], ...]`. Falls back to single `pin` if `pins` absent.
    pins_raw = body.get("pins") or []
    pins_list: list[tuple[float, float]] = []
    if isinstance(pins_raw, list):
        for entry in pins_raw:
            try:
                if isinstance(entry, dict):
                    pins_list.append((float(entry["lat"]), float(entry["lng"])))
                elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    pins_list.append((float(entry[0]), float(entry[1])))
            except (TypeError, ValueError, KeyError):
                continue
    if not pins_list and pin_tuple:
        pins_list = [pin_tuple]

    bbox = body.get("bbox") or body.get("map_bounds")
    bbox_tuple = None
    if isinstance(bbox, dict):
        try:
            bbox_tuple = (
                float(bbox["west"]),
                float(bbox["south"]),
                float(bbox["east"]),
                float(bbox["north"]),
            )
        except (KeyError, TypeError, ValueError):
            bbox_tuple = None
    elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            bbox_tuple = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
        except (TypeError, ValueError):
            bbox_tuple = None

    time_range_raw = body.get("time_range") or body.get("date_range")
    time_range_tuple: tuple[str, str] | None = None
    if isinstance(time_range_raw, (list, tuple)) and len(time_range_raw) == 2:
        try:
            time_range_tuple = (str(time_range_raw[0]), str(time_range_raw[1]))
        except Exception:  # noqa: BLE001
            time_range_tuple = None

    screenshot_b64 = body.get("screenshot_base64") or body.get("imagery_base64")
    history = body.get("conversation_history") or body.get("messages") or []

    loaded = body.get("loaded_collections") or []
    if isinstance(loaded, str):
        loaded = [loaded]
    # Frontend sends `current_collection` (singular). Treat it as a loaded
    # collection too â€” without this, L2 clarifier sees empty loaded list
    # even after the user just loaded a STAC dataset.
    current_collection = body.get("current_collection") or body.get("collection")
    if isinstance(current_collection, str) and current_collection.strip():
        if current_collection not in loaded:
            loaded.append(current_collection)
    elif isinstance(current_collection, list):
        for c in current_collection:
            if isinstance(c, str) and c.strip() and c not in loaded:
                loaded.append(c)

    stac_items = body.get("stac_items") or []
    if not isinstance(stac_items, list):
        stac_items = []
    tile_urls_raw = body.get("tile_urls") or []
    if isinstance(tile_urls_raw, str):
        tile_urls_raw = [tile_urls_raw]
    elif not isinstance(tile_urls_raw, list):
        tile_urls_raw = []
    # Frontend ships tile_urls as objects {url, collection, ...}. Normalise
    # to a flat list of URL strings â€” the analyzers only need the URLs.
    tile_urls: list[str] = []
    for entry in tile_urls_raw:
        if isinstance(entry, str):
            tile_urls.append(entry)
        elif isinstance(entry, dict):
            url = (
                entry.get("url")
                or entry.get("href")
                or entry.get("tile_url")
                or entry.get("tilejson_url")
            )
            if isinstance(url, str) and url.strip():
                tile_urls.append(url)

    collections_meta = _extract_collection_meta(stac_items)

    # Per-request UI toggles. Defaults match the UI defaults so omitted
    # fields behave the same as the UI's "fresh load" state.
    _stac_mode_raw = body.get("stac_mode") or os.getenv("DEFAULT_STAC_MODE")
    _stac_mode = (_stac_mode_raw or "public").lower()
    if _stac_mode not in ("public", "pro"):
        _stac_mode = "public"

    geoint_module_raw = body.get("geoint_module")
    geoint_module = (
        geoint_module_raw.strip()
        if isinstance(geoint_module_raw, str) and geoint_module_raw.strip()
        else None
    )
    analysis_type_raw = body.get("analysis_type")
    analysis_type = (
        analysis_type_raw
        if analysis_type_raw in {"raster", "screenshot"}
        else None
    )

    return AnalysisRequest(
        question=(body.get("query") or body.get("user_query") or "").strip(),
        session_id=str(
            body.get("session_id") or body.get("conversation_id") or "anon"
        ),
        authenticated_user_id=body.get("_authenticated_user_id"),
        bbox=bbox_tuple,
        location_name=body.get("location_name"),
        pin=pin_tuple,
        pins=pins_list,
        time_range=time_range_tuple,
        loaded_collections=list(loaded),
        loaded_collections_meta=collections_meta,
        has_screenshot=bool(screenshot_b64),
        screenshot_url=body.get("imagery_url") or body.get("screenshot_url"),
        screenshot_b64=screenshot_b64,
        history=list(history) if isinstance(history, list) else [],
        stac_items=list(stac_items),
        tile_urls=list(tile_urls),
        hint="foundation_change" if geoint_module == "foundation_change" else None,
        analysis_type=analysis_type,
        geoint_module=geoint_module,
        model=body.get("model"),
        reasoning_effort=str(body.get("reasoning_effort") or "none"),
        stac_mode=_stac_mode,
    )



async def run_pipeline_v2(body: dict[str, Any]) -> dict[str, Any]:
    """Execute the v2 pipeline end-to-end. Always returns a dict.

    Layer 1 is implemented as a multi-agent set (one classifier + four
    specialists) in :mod:`pipeline.layer1_agents`:

      * :class:`NavigateAgent`        -> NAVIGATE         (geocode + bbox)
      * :class:`LoadSpecialistAgent`  -> LOAD             (slot fill via LoadAgent)
      * :class:`AnalyzeAgent`         -> ANALYZE          (clarifier + router + orchestrator)
      * :class:`LoadAndAnalyzeAgent`  -> LOAD_AND_ANALYZE (Load then Analyze, closes G4)

    Each specialist is a real Microsoft Agent Framework ``Executor``
    (when ``agent_framework`` is installed) and exposes the same
    ``run(decision, request, body) -> dict`` interface, so this dispatch
    function just picks the right one based on
    :attr:`ActionDecision.action` and returns its dict.

    The Layer-1 ClarifierAgent (front door) runs in ``fastapi_app.py``
    BEFORE this function and may already have decided the action. When
    that's the case the body carries ``clarifier_route`` and we
    synthesize an :class:`ActionDecision` deterministically instead of
    calling the ActionRouter LLM (saves one round-trip).
    """
    from .contracts import ActionDecision
    from .layer1_agents import build_layer1_agents

    started = time.time()
    action_router, _analysis_router, _orchestrator, _registry = build_default_pipeline()
    agents = build_layer1_agents(
        analysis_router=None,
        orchestrator=None,
        registry=None,
    )

    request = _build_request(body)
    logger.info(
        "[PIPELINE-V2] question=%r pin=%s bbox=%s loaded=%s screenshot=%s",
        request.question[:100],
        request.pin,
        request.bbox,
        request.loaded_collections,
        bool(request.screenshot_b64),
    )

    # Map a clarifier-provided target_route to an ActionDecision so we don't
    # double-classify. The clarifier's vocabulary is the legacy 5-route one;
    # collapse it into v2's 4-action enum.
    _route_to_action = {
        "navigate_to": "NAVIGATE",
        "stac_search": "LOAD",
        "vision_analysis": "ANALYZE",
        "contextual": "ANALYZE",
        "hybrid": "LOAD_AND_ANALYZE",
    }
    clarifier_route = (body.get("clarifier_route") or "").strip().lower() or None
    inspection_collection_ids = await _collection_ids_for_asset_inspection(
        request
    )
    inspection_collection = _unloaded_collection_for_asset_inspection(
        request,
        collection_ids=inspection_collection_ids,
    )
    # LOAD-clarification resume: when this turn is the user's reply to a
    # prior LoadAgent clarification (body carries _pending_load_clarification
    # hydrated by fastapi_app), the user's message is typically a short
    # phrase ("yes", "proceed", "both", "2021") that ActionRouter would
    # misclassify as ANALYZE. Force the LOAD action so LoadSpecialistAgent
    # gets a chance to resolve the clarification against prior context.
    _pending_load = body.get("_pending_load_clarification") if isinstance(body, dict) else None
    if isinstance(_pending_load, dict) and _pending_load.get("question") and not clarifier_route:
        # Only force LOAD when the user's reply looks like an answer to
        # the prior clarification (short acceptance / option pick / a
        # year). For longer messages, let ActionRouter classify normally
        # so topic changes ("actually show me Sentinel-2 over Tokyo",
        # "what's the temperature at my pin") aren't misrouted.
        _q = (request.question or "").strip().lower()
        _accept_patterns = (
            "yes", "yeah", "yep", "yup", "ok", "okay", "sure",
            "proceed", "go", "go ahead", "do it", "continue",
            "both", "either", "all", "all of them", "either one",
            "first", "second", "third", "the first", "the second",
            "1", "2", "3", "#1", "#2", "#3",
            "categorical", "continuous", "rdnbr", "dnbr",
            # Scope answers (statewide / regional / countywide / etc.)
            # When LoadAgent asks "statewide map or specific fire focus?",
            # the user's one-word reply must be treated as a clarification
            # answer, not a brand-new ANALYZE query.
            "statewide", "state-wide", "state wide",
            "countywide", "county-wide", "county wide",
            "nationwide", "nation-wide", "nation wide",
            "regional", "local", "global",
            "entire", "whole", "full", "everything",
        )
        _looks_like_acceptance = (
            len(_q.split()) <= 6
            and (
                _q in _accept_patterns
                or any(_q.startswith(p + " ") or _q.startswith(p + ",") for p in _accept_patterns)
                or _q.startswith("yes")
                or _q.startswith("no, ")  # "no, the second one"
                or _q.replace(" ", "").isdigit()  # year reply
                or any(_q == opt.strip().lower() for opt in (_pending_load.get("options") or []))
            )
        )
        if _looks_like_acceptance:
            clarifier_route = "stac_search"
            logger.info(
                "[PIPELINE-V2] L1 pending_load_clarification + acceptance-shaped "
                "reply (%r) -> forcing LOAD (prior_query=%r)",
                _q[:60],
                (_pending_load.get("prior_query") or "")[:80],
            )
        else:
            logger.info(
                "[PIPELINE-V2] L1 pending_load_clarification present but reply "
                "(%r) doesn't look like acceptance -> normal ActionRouter "
                "classification (likely topic change)",
                _q[:60],
            )
    decision: ActionDecision
    if inspection_collection:
        decision = ActionDecision(
            action="LOAD",
            location=request.location_name,
            use_current_location=not bool(request.location_name),
            stac_query=inspection_collection,
            analysis_question=request.question,
            reasoning="unloaded_collection_inspection",
            confidence=1.0,
        )
        logger.info(
            "[PIPELINE-V2] unloaded collection %s asset inspection -> LOAD "
            "(overrode module=%r, clarifier_route=%r)",
            inspection_collection,
            request.geoint_module,
            clarifier_route,
        )
    elif request.geoint_module == "foundation_change":
        decision = ActionDecision(
            action="ANALYZE",
            analysis_question=request.question,
            reasoning="foundation_change_module",
            confidence=1.0,
        )
        logger.info(
            "[PIPELINE-V2] foundation_change module -> ANALYZE "
            "(skipped clarifier route and ActionRouter)"
        )
    elif is_explicit_web_request(request.question):
        decision = ActionDecision(
            action="ANALYZE",
            analysis_question=request.question,
            reasoning="explicit_web_search",
            confidence=1.0,
        )
        logger.info(
            "[PIPELINE-V2] explicit web search -> ANALYZE "
            "(overrode clarifier route %r)",
            clarifier_route,
        )
    elif clarifier_route in _route_to_action:
        decision = ActionDecision(
            action=_route_to_action[clarifier_route],  # type: ignore[arg-type]
            location=body.get("location_name"),
            use_current_location=False,
            stac_query=body.get("stac_query"),
            analysis_question=request.question,
            reasoning=f"clarifier_passthrough:{clarifier_route}",
            confidence=0.99,
        )
        logger.info(
            "[PIPELINE-V2] L1 clarifier_route=%s -> action=%s (skipped ActionRouter LLM)",
            clarifier_route,
            decision.action,
        )
    else:
        decision = await action_router.route(
            query=request.question,
            loaded_collections=request.loaded_collections,
            has_pin=bool(request.pin),
            has_screenshot=bool(request.screenshot_b64 or request.has_screenshot),
        )
        logger.info(
            "[PIPELINE-V2] L1 action=%s conf=%.2f reason=%r",
            decision.action,
            decision.confidence,
            decision.reasoning[:160],
        )

    specialist = agents.for_action(decision.action)
    logger.info(
        "[PIPELINE-V2] -> specialist=%s",
        getattr(specialist, "id", specialist.__class__.__name__),
    )
    result = await specialist.run(decision, request, body)
    if inspection_collection and result.get("action") == "LOAD":
        result["post_load_inspection"] = {
            "collection_id": inspection_collection,
            "question": request.question,
        }
    # elapsed_ms reflects the whole pipeline; specialists may set their own.
    result.setdefault("elapsed_ms", 0)
    result["elapsed_ms"] = max(result["elapsed_ms"], int((time.time() - started) * 1000))
    return result
