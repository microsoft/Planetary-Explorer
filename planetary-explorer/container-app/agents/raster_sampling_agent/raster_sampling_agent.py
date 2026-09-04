"""
RasterSamplingAgent — designated agent for "what is the value at this pin?"
queries on a loaded STAC raster.

Single tool: `agents.vision_tools.sample_raster_value`. Calls TiTiler `/point`
under the hood. Returns the value with units (NDVI, SST, elevation, FRP, ...).

Public entry point: `RasterSamplingAgent.run(payload)` returning a
`RasterSamplingResult`. The pipeline `RasterSamplingAnalyzer` delegates to
this agent so the surface area looks like every other Layer-2 agent.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional

from .raster_sampling_models import RasterSamplingInput, RasterSamplingResult

logger = logging.getLogger(__name__)


_KNOWN_DATA_TYPES = {
    "sst", "temperature", "elevation", "ndvi", "burn", "fire", "water",
    "snow", "sar", "biomass", "reflectance", "climate", "vegetation",
    "gpp", "npp", "auto",
}


def _parse_numeric_samples(text: str) -> list[dict[str, object]]:
    """Extract aligned metric/value/unit samples from tool markdown."""
    headings = list(re.finditer(r"\*\*([^*\n:]+(?:\s+\([^*\n]+\))?):\*\*", text))
    samples: list[dict[str, object]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():end]
        ndvi_match = re.search(
            r"\*\*NDVI Value:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\*\*",
            block,
        )
        value_match = ndvi_match or re.search(
            r"-\s*(?:Converted|Value|Class):\s*\*\*"
            r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*([^*\n]*)\*\*",
            block,
        )
        if not value_match:
            continue
        unit = "" if ndvi_match else (value_match.group(2).strip() or None)
        samples.append({
            "metric": heading.group(1).strip(),
            "value": float(value_match.group(1)),
            "unit": unit,
        })
    return samples


def _parse_numeric_sample(text: str) -> tuple[float | None, str | None, str | None]:
    """Extract the first aligned value for the legacy singular contract."""
    samples = _parse_numeric_samples(text)
    if not samples:
        return None, None, None
    first = samples[0]
    return first["value"], first["metric"], first["unit"]  # type: ignore[return-value]


def _parse_sample_provenance(text: str) -> tuple[list[str], list[str]]:
    """Extract unique sampled item ids and acquisition dates from tool output."""
    scenes = _parse_sampled_scenes(text)
    item_ids = list(dict.fromkeys(scene["item_id"] for scene in scenes))
    dates = list(dict.fromkeys(scene["date"] for scene in scenes))
    return item_ids, dates


def _parse_sampled_scenes(text: str) -> list[dict[str, str]]:
    """Extract scene ids and their immediately adjacent optional dates."""
    scenes = []
    for item_match in re.finditer(r"(?m)^- Item:\s*([^\r\n]+?)\s*$", text):
        date_match = re.match(
            r"\r?\n- Date:\s*((?:19|20)\d{2}-\d{2}-\d{2})\s*(?:\r?\n|$)",
            text[item_match.end():],
        )
        scenes.append({
            "item_id": item_match.group(1).strip(),
            "date": date_match.group(1) if date_match else "",
        })
    return list({(scene["item_id"], scene["date"]): scene for scene in scenes}.values())


class RasterSamplingAgent:
    """Designated agent for raster point-sampling."""

    async def run(self, payload: RasterSamplingInput) -> RasterSamplingResult:
        started = time.time()
        try:
            from agents.vision_tools import (
                sample_raster_value,
                set_session_context,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("[RASTER_SAMPLING_AGENT] import failed: %s", exc)
            return RasterSamplingResult(
                success=False,
                error=f"import_error: {exc}",
                pin=payload.pin,
                elapsed_ms=int((time.time() - started) * 1000),
            )

        # Build the map_bounds dict the legacy helper expects.
        bounds: dict = {}
        if payload.bbox:
            west, south, east, north = payload.bbox
            bounds.update({
                "north": north,
                "south": south,
                "east": east,
                "west": west,
                "center_lat": (south + north) / 2,
                "center_lng": (west + east) / 2,
            })
        lat, lng = payload.pin
        bounds["pin_lat"] = lat
        bounds["pin_lng"] = lng
        bounds.setdefault("center_lat", lat)
        bounds.setdefault("center_lng", lng)

        data_type = (payload.data_type or "auto").strip().lower() or "auto"
        if data_type not in _KNOWN_DATA_TYPES:
            data_type = "auto"

        try:
            def run_sample() -> str:
                set_session_context(
                    screenshot_base64=payload.screenshot_b64,
                    map_bounds=bounds,
                    stac_items=list(payload.stac_items),
                    loaded_collections=list(payload.loaded_collections),
                    tile_urls=list(payload.tile_urls),
                    stac_mode=payload.stac_mode,
                )
                return sample_raster_value(data_type=data_type)

            raw = await asyncio.to_thread(run_sample)
        except Exception as exc:
            logger.warning("[RASTER_SAMPLING_AGENT] sample_raster_value failed: %s", exc)
            return RasterSamplingResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                pin=payload.pin,
                data_type=data_type,
                elapsed_ms=int((time.time() - started) * 1000),
            )

        text = (raw or "").strip()
        sources = [{"title": cid, "kind": "raster"} for cid in payload.loaded_collections[:3]]
        samples = _parse_numeric_samples(text)
        value, metric, unit = _parse_numeric_sample(text)
        sampled_scenes = _parse_sampled_scenes(text)
        sampled_item_ids, sampled_dates = _parse_sample_provenance(text)
        success = bool(text) and not text.lower().startswith("no ") and value is not None

        return RasterSamplingResult(
            success=success,
            answer=text,
            raw_value=text,
            data_type=data_type,
            pin=payload.pin,
            loaded_collections=list(payload.loaded_collections),
            sources=sources,
            confidence=0.9 if success else 0.2,
            error=None if success else "Sampling returned no numeric value.",
            structured={
                "data_type": data_type,
                "pin": list(payload.pin),
                "lat": payload.pin[0],
                "lng": payload.pin[1],
                "value": value,
                "metric": metric,
                "unit": unit,
                "samples": samples,
                "sampled_scenes": sampled_scenes,
                "sampled_item_ids": sampled_item_ids,
                "sampled_dates": sampled_dates,
                "loaded_collections": list(payload.loaded_collections),
            },
            elapsed_ms=int((time.time() - started) * 1000),
        )


_singleton: Optional[RasterSamplingAgent] = None


def get_raster_sampling_agent() -> RasterSamplingAgent:
    global _singleton
    if _singleton is None:
        _singleton = RasterSamplingAgent()
    return _singleton
