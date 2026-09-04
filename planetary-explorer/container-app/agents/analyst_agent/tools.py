"""Tool functions for AnalystAgent.

Each tool wraps an existing Analyzer (or underlying agent) without
rewriting its internals. Tools read session context from the
ContextVar (set by AnalystAgent before the agent run), rebuild the
appropriate AnalysisRequest, call analyzer.analyze(), and return a
JSON-serializable dict.

All tools are async. Naming follows the catalog in REQ-ARCH-1.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .session_context import get_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _geofm_owner_proof(
    action: str,
    owner: str,
    resource: Any,
) -> Dict[str, Any]:
    key = (os.getenv("GEOFM_OWNER_SIGNING_KEY") or "").encode("utf-8")
    if len(key) < 32:
        raise RuntimeError("GeoFM owner signing is not configured.")
    expires_at = int(time.time()) + 120
    nonce = secrets.token_hex(16)
    payload = json.dumps(
        [action, owner, _canonical_geofm_resource(resource), expires_at, nonce],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "owner_signature": hmac.new(key, payload, hashlib.sha256).hexdigest(),
        "owner_signature_expires_at": expires_at,
        "owner_signature_nonce": nonce,
    }


def _canonical_geofm_resource(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            child_key: _canonical_geofm_resource(child, key=child_key)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [_canonical_geofm_resource(child) for child in value]
    if key == "run_id" and isinstance(value, str):
        return str(UUID(value))
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return format(float(value), ".17g")
    return value


def _build_request(question_override: Optional[str] = None, hint: Optional[str] = None):
    """Rebuild an AnalysisRequest from the ContextVar snapshot."""
    from pipeline.contracts import AnalysisRequest

    s = get_session()
    return AnalysisRequest(
        question=question_override or s.question,
        session_id=s.session_id,
        pin=s.pin,
        pins=list(s.pins),
        bbox=s.bbox,
        location_name=s.location_name,
        time_range=s.time_range,
        loaded_collections=list(s.loaded_collections),
        loaded_collections_meta=list(s.loaded_collections_meta),
        has_screenshot=s.has_screenshot,
        screenshot_url=s.screenshot_url,
        screenshot_b64=s.screenshot_b64,
        rendered_layers=[],
        stac_items=list(s.stac_items),
        tile_urls=list(s.tile_urls),
        history=list(s.history),
        grounding=[],  # AnalystAgent owns chaining via tool sequence, not grounding field
        hint=hint or s.hint,
        stac_mode=s.stac_mode,
    )


def _result_to_dict(result) -> Dict[str, Any]:
    """Convert an AnalyzerResult to a tool-return dict (JSON-safe)."""
    try:
        d = result.model_dump()
    except AttributeError:
        d = dict(result) if isinstance(result, dict) else {"answer": str(result)}
    # Trim screenshots / large blobs from sources if any
    return {
        "analyzer": d.get("analyzer"),
        "success": d.get("success", True),
        "answer": d.get("answer", ""),
        "structured": d.get("structured", {}),
        "sources": d.get("sources", []),
        "confidence": d.get("confidence", 0.0),
        "error": d.get("error"),
        "elapsed_ms": d.get("elapsed_ms", 0),
    }


def _record_evidence(tool_name: str, payload: Dict[str, Any]) -> None:
    s = get_session()
    s.evidence.append({"tool": tool_name, "payload": payload})


# ---------------------------------------------------------------------------
# KNOWLEDGE TOOLS
# ---------------------------------------------------------------------------


async def search_graphrag(query: str, mode: str = "auto") -> Dict[str, Any]:
    """Search the indexed corpus (papers, methodology, docs) via GraphRAG.

    Args:
        query: The user's question, rephrased for retrieval if helpful.
        mode: One of "vector", "cypher", "sql", "auto". Use "auto" unless
              you have a specific reason.
    """
    # Per-request toggle: when the UI has disabled GraphRAG, short-circuit
    # so the agent never spends a sidecar round-trip. The evidence record
    # is omitted intentionally — a "skip" should not show up as a source.
    from .session_context import get_session
    if not get_session().use_graphrag:
        logger.info("[ANALYST] search_graphrag skipped — disabled by request flag")
        return {
            "success": False,
            "skipped": True,
            "reason": "graphrag_disabled_by_user",
            "answer": "",
            "sources": [],
        }

    from pipeline.analyzers.graphrag_analyzer import GraphRAGAnalyzer

    started = time.time()
    try:
        analyzer = GraphRAGAnalyzer()
        req = _build_request(question_override=query, hint=mode if mode != "auto" else None)
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("search_graphrag", out)
        return out
    except Exception as e:
        logger.exception("search_graphrag failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


async def general_earth_qa(question: str) -> Dict[str, Any]:
    """Conceptual Earth-science fallback when no spatial tool fits.

    Use this for definitional or "what is X" questions when no map
    context disambiguates.
    """
    from pipeline.analyzers.llm_only_analyzer import LLMOnlyAnalyzer

    started = time.time()
    try:
        analyzer = LLMOnlyAnalyzer()
        req = _build_request(question_override=question)
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("general_earth_qa", out)
        return out
    except Exception as e:
        logger.exception("general_earth_qa failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


async def search_web(
    query: str,
    search_context_size: str = "medium",
) -> Dict[str, Any]:
    """Search the current public web through Microsoft Foundry Web Search."""
    from mcp_runtime.traced_client import TracedMcpClient

    if search_context_size not in {"low", "medium", "high"}:
        return {
            "success": False,
            "error": "search_context_size must be low, medium, or high",
        }
    client = TracedMcpClient.from_web_search(turn_id=get_session().session_id)
    if client is None:
        return {
            "success": False,
            "skipped": True,
            "error": "Azure Web Search is not enabled in this environment.",
        }
    try:
        result = await client.call(
            "web_search",
            {"query": query, "search_context_size": search_context_size},
        )
        structured = result if isinstance(result, dict) else {"answer": str(result)}
        sources = [
            {
                "title": str(citation.get("title") or "Web source"),
                "uri": citation.get("url"),
                "kind": "web",
            }
            for citation in structured.get("citations", [])
            if isinstance(citation, dict) and citation.get("url")
        ]
        cited_urls = {source["uri"] for source in sources}
        for source_url in structured.get("source_urls", []) or []:
            if isinstance(source_url, str) and source_url and source_url not in cited_urls:
                sources.append(
                    {
                        "title": "Web source",
                        "uri": source_url,
                        "kind": "web",
                    }
                )
                cited_urls.add(source_url)
        answer = structured.get("answer") or ""
        if not answer or not sources:
            out = {
                "success": False,
                "error": "Azure Web Search returned no grounded answer with a usable source.",
            }
        else:
            out = {
                "success": True,
                "answer": answer,
                "structured": structured,
                "sources": sources,
            }
    except Exception as error:
        logger.exception("search_web failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("search_web", out)
    return out


async def get_current_datetime(timezone: str = "UTC") -> Dict[str, Any]:
    """Get the current date and time from the web-search MCP host clock."""
    from mcp_runtime.traced_client import TracedMcpClient

    client = TracedMcpClient.from_web_search(turn_id=get_session().session_id)
    if client is None:
        return {
            "success": False,
            "skipped": True,
            "error": "The current-date MCP service is not enabled.",
        }
    try:
        result = await client.call("get_current_datetime", {"timezone": timezone})
        structured = result if isinstance(result, dict) else {"iso8601": str(result)}
        date_value = str(structured.get("date") or "")
        timezone_value = str(structured.get("timezone") or timezone)
        out = {
            "success": True,
            "answer": f"The current date is {date_value} ({timezone_value}).",
            "structured": structured,
            "sources": [
                {
                    "title": "MCP host system clock",
                    "uri": None,
                    "kind": "calculation",
                }
            ],
        }
    except Exception as error:
        logger.exception("get_current_datetime failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("get_current_datetime", out)
    return out


# ---------------------------------------------------------------------------
# VISION / MAP TOOLS
# ---------------------------------------------------------------------------


async def describe_map_screenshot(question: str) -> Dict[str, Any]:
    """Run GPT-5 Vision over the user's current map screenshot.

    Best for "what's visible", "describe this area", land cover, urban
    structure, vegetation patterns. Requires a screenshot or a loaded
    raster (one of the two will be auto-derived from session context).
    """
    from pipeline.analyzers.vision_analyzer import VisionAnalyzer

    started = time.time()
    try:
        analyzer = VisionAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "vision tool needs a loaded raster or a screenshot",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("describe_map_screenshot", out)
        return out
    except Exception as e:
        logger.exception("describe_map_screenshot failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


# ---------------------------------------------------------------------------
# RASTER VALUE TOOLS
# ---------------------------------------------------------------------------


async def sample_raster_value(question: str) -> Dict[str, Any]:
    """Sample the actual pixel value from the loaded raster at the pinned location.

    Requires a pin AND a loaded raster collection. Use for "what is the
    SST/elevation/NDVI here", "what value at this point", etc.
    """
    from pipeline.analyzers.raster_sampling_analyzer import RasterSamplingAnalyzer

    started = time.time()
    try:
        analyzer = RasterSamplingAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "sample_raster_value needs a pin and a loaded raster",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("sample_raster_value", out)
        return out
    except Exception as e:
        logger.exception("sample_raster_value failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


async def get_collection_metadata(collection_id: str) -> Dict[str, Any]:
    """Look up asset type / domain / sample STAC scenes for a collection.

    Use this before sampling if you're unsure whether a collection is
    a COG raster vs NetCDF time series, or whether scenes exist for a
    given location. (REQ-ANALYZE-3 collection-awareness.)
    """
    s = get_session()
    # Try to find the collection in the loaded meta first
    for meta in s.loaded_collections_meta:
        if meta.get("id") == collection_id or meta.get("collection") == collection_id:
            out = {
                "success": True,
                "collection_id": collection_id,
                "metadata": meta,
                "loaded_in_session": True,
            }
            _record_evidence("get_collection_metadata", out)
            return out
    out = {
        "success": True,
        "collection_id": collection_id,
        "metadata": None,
        "loaded_in_session": False,
        "note": "Collection not currently loaded. Frontend would need to LOAD it first.",
    }
    _record_evidence("get_collection_metadata", out)
    return out


# ---------------------------------------------------------------------------
# TERRAIN / MOBILITY TOOLS
# ---------------------------------------------------------------------------


async def get_terrain_stats(question: str) -> Dict[str, Any]:
    """Elevation, slope, aspect, flat-area analysis from Copernicus DEM.

    Requires a pin. Use for landing-zone, site-suitability, slope-based
    questions.
    """
    from pipeline.analyzers.terrain_analyzer import TerrainAnalyzer

    started = time.time()
    try:
        analyzer = TerrainAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "get_terrain_stats needs a pin",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("get_terrain_stats", out)
        return out
    except Exception as e:
        logger.exception("get_terrain_stats failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


async def get_mobility_path(question: str) -> Dict[str, Any]:
    """GO / SLOW-GO / NO-GO trafficability classification from terrain + land cover.

    Requires a pin. Use for "can I drive across", "best route",
    trafficability, off-road mobility.
    """
    from pipeline.analyzers.mobility_analyzer import MobilityAnalyzer

    started = time.time()
    try:
        analyzer = MobilityAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "get_mobility_path needs a pin",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("get_mobility_path", out)
        return out
    except Exception as e:
        logger.exception("get_mobility_path failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


# ---------------------------------------------------------------------------
# CLIMATE TOOLS
# ---------------------------------------------------------------------------


async def get_extreme_weather_projection(question: str) -> Dict[str, Any]:
    """Future climate projections from NASA NEX-GDDP-CMIP6.

    Requires a pin. Covers SSP2-4.5 vs SSP5-8.5 scenarios, temperature
    / precipitation / wind / humidity by future year.
    """
    from pipeline.analyzers.extreme_weather_analyzer import ExtremeWeatherAnalyzer

    started = time.time()
    try:
        analyzer = ExtremeWeatherAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "get_extreme_weather_projection needs a pin",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("get_extreme_weather_projection", out)
        return out
    except Exception as e:
        logger.exception("get_extreme_weather_projection failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


async def compute_netcdf_trend(question: str) -> Dict[str, Any]:
    """Quantitative point-sampling + time-series anomaly / linear trend over NetCDF.

    Requires a pin. Use for "trend over time", "anomaly relative to
    baseline", "rolling mean" questions.
    """
    from pipeline.analyzers.netcdf_computation_analyzer import NetcdfComputationAnalyzer

    started = time.time()
    try:
        analyzer = NetcdfComputationAnalyzer()
        req = _build_request(question_override=question)
        if not analyzer.can_run(req):
            return {
                "success": False,
                "error": "compute_netcdf_trend needs a pin",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        result = await analyzer.analyze(req)
        out = _result_to_dict(result)
        _record_evidence("compute_netcdf_trend", out)
        return out
    except Exception as e:
        logger.exception("compute_netcdf_trend failed")
        return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - started) * 1000)}


# ---------------------------------------------------------------------------
# TEMPORAL COMPARISON TOOL (closes G9)
# ---------------------------------------------------------------------------


async def compare_temporal(
    collection: str,
    t1: str,
    t2: str,
    metric: str = "auto",
) -> Dict[str, Any]:
    """Compare the same location + collection across two distinct time windows.

    This implements REQ-COMPARE-1 / closes G9. The tool:
      1. Confirms the user has a pin (or bbox) and a single collection target.
        2. For NBR, searches Public Planetary Computer near each requested
            epoch and computes a cloud-masked extent summary from signed COGs.
            Other metrics continue through the generic raster sampler.
      3. Returns a structured diff: {t1_value, t2_value, delta,
         percent_change, narrative}.

    Args:
        collection: The MPC collection id to compare (must match what's
                    loaded or what get_collection_metadata returned).
        t1: ISO date or year for the "before" window (e.g. "2015-06" or "2015").
        t2: ISO date or year for the "after" window.
        metric: Metric to compare. Use "nbr" for Normalized Burn Ratio.
    """
    from pipeline.analyzers.raster_sampling_analyzer import RasterSamplingAnalyzer

    started = time.time()
    s = get_session()

    if not s.pin and not s.bbox:
        return {
            "success": False,
            "needs_clarification": True,
            "missing_slot": "location",
            "error": "compare_temporal needs a pin or bbox to anchor both samples.",
        }

    requested_metric = metric.strip().lower()
    question_lower = s.question.lower()
    if requested_metric == "auto" and (
        "nbr" in question_lower or "normalized burn ratio" in question_lower
    ):
        requested_metric = "nbr"

    if requested_metric in {"nbr", "dnbr", "normalized burn ratio"}:
        import asyncio

        from agents.raster_sampling_agent.spectral_indices import (
            SpectralIndexSample,
            sample_temporal_nbr,
        )

        if s.bbox:
            sampling_bbox = s.bbox
            spatial_support = "valid cloud-masked pixels in the requested extent"
        else:
            from pyproj import Geod

            latitude, longitude = s.pin  # type: ignore[misc]
            geod = Geod(ellps="WGS84")
            west = geod.fwd(longitude, latitude, 270, 30)[0]
            east = geod.fwd(longitude, latitude, 90, 30)[0]
            south = geod.fwd(longitude, latitude, 180, 30)[1]
            north = geod.fwd(longitude, latitude, 0, 30)[1]
            sampling_bbox = (west, south, east, north)
            spatial_support = "valid cloud-masked pixels in a 60 m window around the pin"

        async def _sample_nbr(when: str) -> SpectralIndexSample:
            return await asyncio.to_thread(
                sample_temporal_nbr,
                collection,
                when,
                bbox=sampling_bbox,
            )

        sampled = await asyncio.gather(
            _sample_nbr(t1),
            _sample_nbr(t2),
            return_exceptions=True,
        )
        errors = [value for value in sampled if isinstance(value, BaseException)]
        if errors:
            out = {
                "success": False,
                "collection": collection,
                "metric": "nbr",
                "t1": t1,
                "t2": t2,
                "error": "; ".join(str(error) for error in errors),
                "narrative": (
                    "Could not retrieve valid NBR rasters for both epochs. "
                    + "; ".join(str(error) for error in errors)
                ),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
            _record_evidence("compare_temporal", out)
            return out

        before = sampled[0]
        after = sampled[1]
        assert isinstance(before, SpectralIndexSample)
        assert isinstance(after, SpectralIndexSample)
        delta = after.value - before.value
        percent_change = (delta / before.value * 100.0) if before.value != 0 else None
        dnbr = before.value - after.value
        before_date = before.acquisition_datetime[:10]
        after_date = after.acquisition_datetime[:10]
        narrative = (
            f"Mean NBR over {spatial_support} was {before.value:.4f} on {before_date} "
            f"(requested {t1}) and {after.value:.4f} on {after_date} "
            f"(requested {t2}). NBR change (after - before) is {delta:+.4f}; "
            f"standard dNBR (before - after) is {dnbr:+.4f}"
            + (
                f", and relative NBR change is {percent_change:+.1f}%."
                if percent_change is not None
                else ". Relative change is undefined because baseline NBR is zero."
            )
        )
        out = {
            "success": True,
            "collection": collection,
            "metric": "nbr",
            "summary_statistic": "mean",
            "spatial_support": spatial_support,
            "bbox": list(sampling_bbox),
            "t1": t1,
            "t2": t2,
            "t1_value": before.value,
            "t2_value": after.value,
            "delta": delta,
            "dnbr": dnbr,
            "percent_change": percent_change,
            "t1_sample": before.to_dict(),
            "t2_sample": after.to_dict(),
            "narrative": narrative,
            "sources": [
                {"title": before.item_id, "uri": before.item_url, "kind": "raster"},
                {"title": after.item_id, "uri": after.item_url, "kind": "raster"},
            ],
            "elapsed_ms": int((time.time() - started) * 1000),
        }
        _record_evidence("compare_temporal", out)
        return out

    # Sample at each epoch using the analyzer + a time-range hint.
    analyzer = RasterSamplingAnalyzer()

    async def _sample(epoch_label: str, when: str) -> Dict[str, Any]:
        from pipeline.contracts import AnalysisRequest

        req = AnalysisRequest(
            question=f"sample the value at the pin for {epoch_label} ({when})",
            session_id=s.session_id,
            pin=s.pin,
            pins=list(s.pins),
            bbox=s.bbox,
            location_name=s.location_name,
            time_range=(when, when),
            loaded_collections=[collection] if collection else list(s.loaded_collections),
            loaded_collections_meta=list(s.loaded_collections_meta),
            has_screenshot=False,
            screenshot_url=None,
            screenshot_b64=None,
            rendered_layers=[],
            stac_items=list(s.stac_items),
            tile_urls=list(s.tile_urls),
            history=[],
            grounding=[],
            hint=f"temporal_compare epoch={epoch_label} when={when}",
            stac_mode=s.stac_mode,
        )
        if not analyzer.can_run(req):
            return {"success": False, "error": f"raster_sampling can't run for {epoch_label}"}
        r = await analyzer.analyze(req)
        return _result_to_dict(r)

    r1 = await _sample("t1", t1)
    r2 = await _sample("t2", t2)

    def _value(r: Dict[str, Any]) -> Optional[float]:
        struct = r.get("structured") or {}
        v = struct.get("value")
        if isinstance(v, (int, float)):
            return float(v)
        return None

    v1 = _value(r1)
    v2 = _value(r2)
    delta = None
    pct = None
    if v1 is not None and v2 is not None:
        delta = v2 - v1
        pct = (delta / v1 * 100.0) if v1 != 0 else None

    narrative = ""
    if v1 is not None and v2 is not None:
        narrative = (
            f"At {s.location_name or 'the pinned location'}, "
            f"{collection} measured {v1:.3f} at {t1} and {v2:.3f} at {t2} "
            f"(delta = {delta:+.3f}"
            + (f", {pct:+.1f}%" if pct is not None else "")
            + ")."
        )
    else:
        narrative = (
            f"Could not extract numeric values for both epochs. "
            f"t1 result: {r1.get('error') or 'ok'}; t2 result: {r2.get('error') or 'ok'}."
        )

    out = {
        "success": v1 is not None and v2 is not None,
        "collection": collection,
        "t1": t1,
        "t2": t2,
        "t1_value": v1,
        "t2_value": v2,
        "delta": delta,
        "percent_change": pct,
        "narrative": narrative,
        "raw_t1": r1,
        "raw_t2": r2,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
    _record_evidence("compare_temporal", out)
    return out


# ---------------------------------------------------------------------------
# GEOSPATIAL FOUNDATION MODEL TOOLS
# ---------------------------------------------------------------------------


def _parse_stac_datetime(item: Dict[str, Any]) -> datetime:
    properties = item.get("properties") or {}
    raw = properties.get("datetime") or properties.get("start_datetime") or ""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=UTC)


def _select_geofm_pair(
    before_item_id: Optional[str],
    after_item_id: Optional[str],
) -> tuple[str, str]:
    session = get_session()
    supported = {"hls2-s30", "hls2-l30"}
    candidates = [
        item
        for item in session.stac_items
        if isinstance(item, dict)
        and item.get("id")
        and (item.get("collection") or item.get("collection_id")) in supported
    ]
    by_id = {str(item["id"]): item for item in candidates}
    if before_item_id or after_item_id:
        if not before_item_id or not after_item_id:
            raise ValueError("Provide both before_item_id and after_item_id, or neither.")
        if before_item_id not in by_id or after_item_id not in by_id:
            raise ValueError("Both GeoFM source items must be loaded HLS items in this map session.")
        first = by_id[before_item_id]
        second = by_id[after_item_id]
        if (first.get("collection") or first.get("collection_id")) != (
            second.get("collection") or second.get("collection_id")
        ):
            raise ValueError("GeoFM source items must come from the same HLS collection.")
        first_datetime = _parse_stac_datetime(first)
        second_datetime = _parse_stac_datetime(second)
        missing_datetime = datetime.min.replace(tzinfo=UTC)
        if first_datetime == missing_datetime or second_datetime == missing_datetime:
            raise ValueError("Both GeoFM source items must include an acquisition datetime.")
        if first_datetime == second_datetime:
            raise ValueError("GeoFM source items must represent distinct acquisition times.")
        if first_datetime > second_datetime:
            return after_item_id, before_item_id
        return before_item_id, after_item_id

    collection_order = [
        collection
        for collection in session.loaded_collections
        if collection in supported
    ] + sorted(supported)
    for collection in dict.fromkeys(collection_order):
        same_collection = [
            item
            for item in candidates
            if (item.get("collection") or item.get("collection_id")) == collection
        ]
        if len(same_collection) < 2:
            continue
        ordered = sorted(same_collection, key=_parse_stac_datetime)
        return str(ordered[0]["id"]), str(ordered[-1]["id"])
    raise ValueError("Load at least two HLS scenes from the same collection before using GeoFM.")


def _geofm_aoi() -> Dict[str, Any]:
    from pyproj import Geod

    session = get_session()
    geod = Geod(ellps="WGS84")
    if session.bbox:
        west, south, east, north = session.bbox
        if west >= east or south >= north:
            raise ValueError("The current map bounds do not form a valid GeoFM AOI.")
        center_lon = (west + east) / 2
        center_lat = (south + north) / 2
        width_m = abs(geod.inv(west, center_lat, east, center_lat)[2])
        height_m = abs(geod.inv(center_lon, south, center_lon, north)[2])
        if width_m > 15_360 or height_m > 15_360:
            raise ValueError(
                "Zoom the map to an area no larger than 15.36 km by 15.36 km for PlanAura."
            )
    elif session.pin:
        latitude, longitude = session.pin
        west = geod.fwd(longitude, latitude, 270, 1000)[0]
        east = geod.fwd(longitude, latitude, 90, 1000)[0]
        south = geod.fwd(longitude, latitude, 180, 1000)[1]
        north = geod.fwd(longitude, latitude, 0, 1000)[1]
    else:
        raise ValueError("GeoFM comparison needs current map bounds or a dropped pin.")
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }


def _geofm_result(result: Any) -> Dict[str, Any]:
    envelope = result if isinstance(result, dict) else {"summary": str(result)}
    structured = envelope.get("payload") or {}
    references = envelope.get("evidence") or []
    sources = []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        reference_kind = reference.get("kind")
        source_kind = "dataset" if reference_kind == "stac_item" else (
            "raster" if reference_kind == "artefact" else "api"
        )
        sources.append(
            {
                "title": str(reference.get("identifier") or "GeoFM evidence"),
                "uri": reference.get("uri"),
                "kind": source_kind,
            }
        )
    status = structured.get("status")
    out: Dict[str, Any] = {
        "success": status != "failed",
        "answer": envelope.get("summary") or "GeoFM request completed.",
        "structured": structured,
        "sources": sources,
        "warnings": envelope.get("warnings") or [],
        "error": structured.get("error"),
    }
    features = structured.get("features")
    if status == "complete" and isinstance(features, list) and features:
        out["visualizations"] = [
            {
                "kind": "vector_layer",
                "title": "PlanAura contextual change",
                "spec": {
                    "data": {"type": "FeatureCollection", "features": features},
                    "metric": "cosine_distance",
                    "threshold": (structured.get("statistics") or {}).get("threshold"),
                },
            }
        ]
    return out


async def list_geofm_models() -> Dict[str, Any]:
    """List GeoFM profiles with exact revisions and deployment gates."""
    from mcp_runtime.traced_client import TracedMcpClient

    client = TracedMcpClient.from_geofm(turn_id=get_session().session_id)
    if client is None:
        return {
            "success": False,
            "skipped": True,
            "error": "GeoFM is not enabled in this Planetary Explorer environment.",
        }
    try:
        out = _geofm_result(await client.call("geofm_list_models", {}))
    except Exception as error:
        logger.exception("list_geofm_models failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("list_geofm_models", out)
    return out


async def compare_with_geofm(
    before_item_id: Optional[str] = None,
    after_item_id: Optional[str] = None,
    threshold: float = 0.35,
    max_features: int = 10,
) -> Dict[str, Any]:
    """Submit a durable PlanAura comparison for two loaded HLS scenes.

    Leave both item ids empty to use the earliest and latest loaded scenes
    from one HLS collection. The operation requires user approval because it
    starts billed GPU work.
    """
    from mcp_runtime.traced_client import TracedMcpClient

    session = get_session()
    client = TracedMcpClient.from_geofm(turn_id=session.session_id)
    if client is None:
        return {
            "success": False,
            "skipped": True,
            "error": "GeoFM is not enabled in this Planetary Explorer environment.",
        }
    try:
        normalized_threshold = float(threshold)
        max_features_number = float(max_features)
        if not max_features_number.is_integer():
            raise ValueError("GeoFM max_features must be an integer.")
        normalized_max_features = int(max_features_number)
        if not 0 <= normalized_threshold <= 2:
            raise ValueError("GeoFM threshold must be between 0 and 2.")
        if not 1 <= normalized_max_features <= 100:
            raise ValueError("GeoFM max_features must be between 1 and 100.")
        loaded_item_ids = {
            str(item.get("id"))
            for item in session.stac_items
            if isinstance(item, dict) and item.get("id")
        }
        explicit_pair_is_loaded = bool(
            before_item_id
            and after_item_id
            and before_item_id in loaded_item_ids
            and after_item_id in loaded_item_ids
        )
        epoch_a, epoch_b = _select_geofm_pair(
            before_item_id if explicit_pair_is_loaded else None,
            after_item_id if explicit_pair_is_loaded else None,
        )
        requested_by = (
            session.authenticated_user_id or f"session:{session.session_id}"
        )
        request = {
            "geometry": _geofm_aoi(),
            "item_id_epoch_a": epoch_a,
            "item_id_epoch_b": epoch_b,
            "profile": "planaura_hls",
            "correlation_id": session.session_id,
            "requested_by": requested_by,
            "threshold": normalized_threshold,
            "max_features": normalized_max_features,
        }
        out = _geofm_result(
            await client.call(
                "geofm_compare_epochs",
                {
                    "request": request,
                    **_geofm_owner_proof(
                        "submit",
                        requested_by,
                        request,
                    ),
                },
            )
        )
    except PermissionError:
        out = {"success": False, "error": "GeoFM submission was not approved."}
    except Exception as error:
        logger.exception("compare_with_geofm failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("compare_with_geofm", out)
    return out


async def get_geofm_run(run_id: str) -> Dict[str, Any]:
    """Poll a durable GeoFM run and return validated results when complete."""
    from mcp_runtime.traced_client import TracedMcpClient

    client = TracedMcpClient.from_geofm(turn_id=get_session().session_id)
    if client is None:
        return {"success": False, "error": "GeoFM is not enabled."}
    try:
        requested_by = get_session().authenticated_user_id or (
            f"session:{get_session().session_id}"
        )
        out = _geofm_result(
            await client.call(
                "geofm_get_run",
                {
                    "run_id": run_id,
                    "requested_by": requested_by,
                    **_geofm_owner_proof(
                        "get",
                        requested_by,
                        {"run_id": run_id},
                    ),
                },
            )
        )
    except Exception as error:
        logger.exception("get_geofm_run failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("get_geofm_run", out)
    return out


async def cancel_geofm_run(run_id: str) -> Dict[str, Any]:
    """Cancel a queued or running GeoFM operation after user approval."""
    from mcp_runtime.traced_client import TracedMcpClient

    client = TracedMcpClient.from_geofm(turn_id=get_session().session_id)
    if client is None:
        return {"success": False, "error": "GeoFM is not enabled."}
    try:
        requested_by = get_session().authenticated_user_id or (
            f"session:{get_session().session_id}"
        )
        out = _geofm_result(
            await client.call(
                "geofm_cancel_run",
                {
                    "run_id": run_id,
                    "requested_by": requested_by,
                    **_geofm_owner_proof(
                        "cancel",
                        requested_by,
                        {"run_id": run_id},
                    ),
                },
            )
        )
    except PermissionError:
        out = {"success": False, "error": "GeoFM cancellation was not approved."}
    except Exception as error:
        logger.exception("cancel_geofm_run failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("cancel_geofm_run", out)
    return out


async def retry_geofm_run(run_id: str) -> Dict[str, Any]:
    """Start another durable attempt for a failed GeoFM run after approval."""
    from mcp_runtime.traced_client import TracedMcpClient

    client = TracedMcpClient.from_geofm(turn_id=get_session().session_id)
    if client is None:
        return {"success": False, "error": "GeoFM is not enabled."}
    try:
        requested_by = get_session().authenticated_user_id or (
            f"session:{get_session().session_id}"
        )
        out = _geofm_result(
            await client.call(
                "geofm_retry_run",
                {
                    "run_id": run_id,
                    "requested_by": requested_by,
                    **_geofm_owner_proof(
                        "retry",
                        requested_by,
                        {"run_id": run_id},
                    ),
                },
            )
        )
    except PermissionError:
        out = {"success": False, "error": "GeoFM retry was not approved."}
    except Exception as error:
        logger.exception("retry_geofm_run failed")
        out = {"success": False, "error": str(error)}
    _record_evidence("retry_geofm_run", out)
    return out


# ---------------------------------------------------------------------------
# CLARIFICATION TOOL (REQ-CLARIFY-2)
# ---------------------------------------------------------------------------


async def ask_user_to_clarify(
    chat_message: str,
    options: List[str],
    missing_slot: Optional[str] = None,
) -> Dict[str, Any]:
    """Ask the user a clarifying question. Use this whenever you can't
    pick a tool confidently or a required slot is missing.

    Args:
        chat_message: A conversational, user-facing message that explains
                      what you need and guides them on what they can do.
        options: 2-4 short suggestion chips to offer as quick replies.
        missing_slot: Optional name of the missing slot ("pin", "location",
                      "collection", "datetime", etc.).
    """
    out = {
        "action": "clarify",
        "chat_message": chat_message,
        "options": options or [],
        "missing_slot": missing_slot,
    }
    _record_evidence("ask_user_to_clarify", out)
    return out


# ---------------------------------------------------------------------------
# Tool registry — feed to AsyncFunctionTool
# ---------------------------------------------------------------------------


def create_analyst_functions():
    """Return the set of tool functions to register on the AnalystAgent.

    Order is the priority hint shown to the model in the tool list.
    """
    return {
        get_current_datetime,
        search_web,
        search_graphrag,
        general_earth_qa,
        describe_map_screenshot,
        sample_raster_value,
        get_collection_metadata,
        get_terrain_stats,
        get_mobility_path,
        get_extreme_weather_projection,
        compute_netcdf_trend,
        compare_temporal,
        list_geofm_models,
        compare_with_geofm,
        get_geofm_run,
        retry_geofm_run,
        cancel_geofm_run,
        ask_user_to_clarify,
    }
