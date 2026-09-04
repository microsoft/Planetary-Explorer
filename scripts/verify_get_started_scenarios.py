"""Validate and exercise the canonical Planetary Explorer Get Started scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WEB_UI = ROOT / "planetary-explorer" / "web-ui"
SCENARIO_SOURCE = WEB_UI / "src" / "config" / "canadianExamples.ts"
DEFAULT_API_URL = (
    "https://ca-earthcopilot-api.thankfulplant-49ee7bc3.eastus2.azurecontainerapps.io"
)

EXPECTED_SETUP: dict[str, dict[str, Any]] = {
    "Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26": {
        "kind": "stac",
        "center": (43.72, -79.38),
        "collection": "sentinel-2-l2a",
    },
    "Show HLS S30 imagery at Calgary, Canada, latitude 51.0300, longitude -114.0800, from 2026-05-01 to 2026-08-26": {
        "kind": "stac",
        "center": (51.03, -114.08),
        "collection": "hls2-s30",
    },
    "Show Landsat imagery over Halifax, Canada from 2026-01-01 to 2026-08-26": {
        "kind": "stac",
        "center": (44.65, -63.58),
        "collection": "landsat-c2-l2",
    },
    "Show MODIS thermal anomalies at latitude 54.5000, longitude -115.0000 in Alberta from 2026-05-01 to 2026-08-26": {
        "kind": "stac",
        "center": (54.5, -115.0),
        "collection": "modis-14A1-061",
    },
    "Show MODIS 13Q1 vegetation indices over cropland south of Regina, Saskatchewan, Canada, latitude 50.3500, longitude -104.6000, from 2026-04-01 to 2026-08-26": {
        "kind": "stac",
        "center": (50.35, -104.6),
        "collection": "modis-13Q1-061",
    },
    "Show collection modis-17A2H-061 gross primary productivity at latitude 54.1500, longitude -126.5500 in British Columbia from 2026-05-01 to 2026-08-26": {
        "kind": "stac",
        "center": (54.15, -126.55),
        "collection": "modis-17A2H-061",
    },
    "Show MODIS 10A1 daily snow cover at Quebec City, Canada, latitude 46.8139, longitude -71.2080, from 2025-02-01 to 2025-02-28": {
        "kind": "stac",
        "center": (46.8139, -71.208),
        "collection": "modis-10A1-061",
    },
    "Show Sentinel-2 imagery along the Mackenzie River near Norman Wells, Canada from 2026-05-01 to 2026-06-30": {
        "kind": "stac",
        "center": (65.282, -126.832),
        "collection": "sentinel-2-l2a",
    },
    "Show Landsat Collection 2 Level-2 imagery along the Hudson Bay coast at Churchill, Manitoba, Canada, latitude 58.7684, longitude -94.1650, from 2026-06-01 to 2026-08-26": {
        "kind": "stac",
        "center": (58.7684, -94.165),
        "collection": "landsat-c2-l2",
    },
    "Show Copernicus DEM terrain around Banff, Canada for 2026 analysis": {
        "kind": "stac",
        "center": (51.23, -115.58),
        "collection": "cop-dem-glo-30",
    },
    "Show Sentinel-1 RTC radar imagery over Vancouver, Canada from 2026-01-01 to 2026-08-26": {
        "kind": "stac",
        "center": (49.2, -123.05),
        "collection": "sentinel-1-rtc",
    },
    "Show Sentinel-1 RTC radar imagery over the Red River, Manitoba from 2026-03-01 to 2026-05-31": {
        "kind": "stac",
        "center": (49.6, -97.08),
        "collection": "sentinel-1-rtc",
    },
    "Show Copernicus DEM elevation near Vancouver, Canada for 2026": {
        "kind": "stac",
        "center": (49.2827, -123.1207),
        "collection": "cop-dem-glo-30",
    },
    "Show Copernicus DEM elevation near Calgary, Alberta, Canada for 2026": {
        "kind": "stac",
        "center": (51.0447, -114.0719),
        "collection": "cop-dem-glo-30",
    },
    "Show Sentinel-2 imagery over Halifax, Canada from 2026-06-01 to 2026-08-26": {
        "kind": "stac",
        "center": (44.6488, -63.5752),
        "collection": "sentinel-2-l2a",
    },
    "Kananaskis, Alberta, Canada": {
        "kind": "navigate",
        "center": (50.7, -115.0),
        "max_distance_km": 100.0,
    },
    "North Vancouver, British Columbia, Canada": {
        "kind": "navigate",
        "center": (49.32, -123.07),
        "max_distance_km": 75.0,
    },
    "Whitehorse, Yukon, Canada": {
        "kind": "navigate",
        "center": (60.7212, -135.0568),
        "max_distance_km": 75.0,
    },
    "Vancouver, British Columbia, Canada": {
        "kind": "navigate",
        "center": (49.2827, -123.1207),
        "max_distance_km": 75.0,
    },
    "Toronto, Ontario, Canada": {
        "kind": "navigate",
        "center": (43.6532, -79.3832),
        "max_distance_km": 75.0,
    },
    "Montreal, Quebec, Canada": {
        "kind": "navigate",
        "center": (45.5019, -73.5674),
        "max_distance_km": 75.0,
    },
    "Show my MPC Pro aerial imagery over Jasper, Alberta from 2026-01-01 to 2026-08-26": {
        "kind": "pro",
        "center": (52.8737, -118.0814),
    },
    "Show my MPC Pro aerial imagery over Lytton, British Columbia, Canada from 2026-01-01 to 2026-08-26": {
        "kind": "pro",
        "center": (50.231, -121.581),
    },
    "Calgary, Alberta, Canada": {
        "kind": "navigate",
        "center": (51.0447, -114.0719),
        "max_distance_km": 75.0,
    },
    "Edmonton, Alberta, Canada": {
        "kind": "navigate",
        "center": (53.5461, -113.4938),
        "max_distance_km": 75.0,
    },
    "Canada": {
        "kind": "navigate",
        "center": (56.1304, -106.3468),
        "max_distance_km": 1500.0,
    },
    "Western Canada": {
        "kind": "navigate",
        "center": (54.0, -116.0),
        "max_distance_km": 1200.0,
    },
    "Lake Ontario, Canada": {
        "kind": "navigate",
        "center": (43.75, -77.9),
        "max_distance_km": 250.0,
    },
    "Saskatchewan, Canada": {
        "kind": "navigate",
        "center": (52.94, -106.45),
        "max_distance_km": 500.0,
    },
    "Nova Scotia, Canada": {
        "kind": "navigate",
        "center": (45.0, -63.0),
        "max_distance_km": 350.0,
    },
}

ADVERSARIAL_SETUP_CONTEXT: dict[str, Any] = {
    "pin": {"lat": -33.8688, "lng": 151.2093},
    "vision_pin": {"lat": -33.8688, "lng": 151.2093},
    "map_bounds": {
        "west": 150.9,
        "south": -34.1,
        "east": 151.4,
        "north": -33.6,
    },
    "current_collection": "sentinel-1-rtc",
    "loaded_collections": ["sentinel-1-rtc"],
    "has_satellite_data": True,
    "vision_mode": True,
    "geoint_mode": True,
}


@dataclass(frozen=True)
class Scenario:
    """One primary Get Started scenario row."""

    family: str
    location: str
    setup_query: str
    question: str | None = None
    raster_query: str | None = None
    image_query: str | None = None
    expected_tools: tuple[str, ...] = ()


def _load_typescript_exports() -> dict[str, Any]:
    """Compile the canonical TypeScript config and return its exports."""
    script = """
const fs = require('fs');
const esbuild = require('esbuild');
const source = fs.readFileSync(process.argv[1], 'utf8');
const transformed = esbuild.transformSync(source, { loader: 'ts', format: 'cjs' });
const loaded = { exports: {} };
new Function('module', 'exports', 'require', transformed.code)(loaded, loaded.exports, require);
process.stdout.write(JSON.stringify(loaded.exports));
"""
    result = subprocess.run(
        ["node", "-e", script, str(SCENARIO_SOURCE)],
        cwd=WEB_UI,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def load_scenarios() -> list[Scenario]:
    """Normalize every primary scenario shown in the Get Started modal."""
    exports = _load_typescript_exports()
    scenarios: list[Scenario] = []

    for category in exports["exampleQueries"]:
        for example in category["examples"]:
            scenarios.append(
                Scenario(
                    family=f"Vision - {category['category']}",
                    location=example["description"],
                    setup_query=example["query"],
                    raster_query=example.get("rasterQuery"),
                    image_query=example.get("screenshotQuery"),
                    expected_tools=("sample_raster_value",),
                )
            )

    specialized = (
        ("Terrain", "terrainQueries", "location"),
        ("Mobility", "mobilityQueries", "location"),
        ("Extreme Weather", "extremeWeatherQueries", "location"),
        ("Building Damage", "buildingDamageQueries", "location"),
        ("Site Intel", "siteAuditQueries", "location"),
        ("Resilience", "resilienceQueries", "scenario"),
        ("Forecast", "forecastQueries", "scenario"),
    )
    for family, export_name, location_key in specialized:
        for item in exports[export_name]:
            if family == "Terrain":
                expected_tools = tuple(item.get("expectedTools") or ())
            elif family == "Mobility":
                expected_tools = ("analyze_two_point_traverse",)
            elif family == "Extreme Weather":
                question = item["question"].casefold()
                if "monthly" in question:
                    expected_tools = ("sample_timeseries",)
                elif "ssp245" in question and "ssp585" in question:
                    expected_tools = ("compare_climate_scenarios",)
                else:
                    expected_tools = ("get_precipitation_projection",)
            else:
                expected_tools = ()
            scenarios.append(
                Scenario(
                    family=family,
                    location=item[location_key],
                    setup_query=item["setupQuery"],
                    question=item["question"],
                    expected_tools=expected_tools,
                )
            )

    return scenarios


def _post_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    """POST JSON and return the HTTP status plus decoded response body."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            decoded: Any = json.loads(body)
        except json.JSONDecodeError:
            decoded = {"error": body}
        return error.code, decoded


def _is_transient_result(status: int, payload: Any) -> bool:
    """Retry only definitive pre-dispatch capacity rejection responses."""
    if status != 429 or not isinstance(payload, dict):
        return False
    retry_proof = payload.get("retry")
    return (
        isinstance(retry_proof, dict)
        and retry_proof.get("safe") is True
        and retry_proof.get("stage") == "pre_dispatch"
    )


def _is_loopback_url(url: str) -> bool:
    """Return whether a URL targets the local machine."""
    hostname = (urlparse(url).hostname or "").casefold()
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _post_json_with_retry(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    attempts: int,
    retry_delay_seconds: float,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, int]:
    """POST with bounded retries for transient capacity failures only."""
    status = 0
    response: Any = {}
    for attempt in range(1, attempts + 1):
        status, response = _post_json(base_url, path, payload, headers=headers)
        if not _is_transient_result(status, response) or attempt == attempts:
            return status, response, attempt
        time.sleep(retry_delay_seconds * attempt)
    return status, response, attempts


def _haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Return the great-circle distance between two latitude/longitude pairs."""
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(value))


def _features(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return STAC features from the response shapes used by the API."""
    candidates = (
        payload.get("data", {}).get("stac_results", {}).get("features"),
        payload.get("results", {}).get("features"),
        payload.get("stac_results", {}).get("features"),
    )
    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
    return []


def _first_feature_pin(
    feature: dict[str, Any], fallback: tuple[float, float]
) -> tuple[float, float]:
    """Return a point centered on one rendered feature."""
    bbox = feature.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        return (
            (float(bbox[1]) + float(bbox[3])) / 2,
            (float(bbox[0]) + float(bbox[2])) / 2,
        )
    return fallback


def _feature_covers(feature: dict[str, Any], point: tuple[float, float]) -> bool:
    """Return whether a STAC feature bbox covers a latitude/longitude point."""
    bbox = feature.get("bbox")
    return isinstance(bbox, list) and len(bbox) == 4 and _bbox_covers(bbox, point)


def _select_feature_for_point(
    features: list[dict[str, Any]],
    point: tuple[float, float],
) -> dict[str, Any] | None:
    """Prefer a rendered scene whose bbox contains the scenario point."""
    return next(
        (feature for feature in features if _feature_covers(feature, point)), None
    )


def _requested_date_range(query: str) -> tuple[str, str] | None:
    """Return an explicit ISO date range from a scenario query."""
    dates = re.findall(r"(?<!\d)((?:19|20)\d{2}-\d{2}-\d{2})(?!\d)", query)
    return (dates[0], dates[1]) if len(dates) >= 2 else None


def _feature_overlaps_date_range(
    feature: dict[str, Any],
    requested: tuple[str, str] | None,
) -> bool:
    """Return whether one STAC item overlaps the requested date range."""
    if requested is None:
        return True
    properties = feature.get("properties") or {}
    feature_start = properties.get("start_datetime") or properties.get("datetime")
    feature_end = properties.get("end_datetime") or properties.get("datetime")
    if not feature_start or not feature_end:
        return False
    requested_start, requested_end = requested
    return (
        str(feature_start)[:10] <= requested_end
        and str(feature_end)[:10] >= requested_start
    )


def _evidence_success(payload: dict[str, Any], tool: str) -> tuple[bool, str | None]:
    """Return success and error from one structured Analyst tool result."""
    evidence = (payload.get("structured") or {}).get(tool) or {}
    error = evidence.get("error")
    return evidence.get("success") is True and not error, str(error) if error else None


def _raster_sample_provenance(
    payload: Any,
    feature: dict[str, Any],
) -> dict[str, Any]:
    """Compare structured sample provenance with the selected map scene."""
    if not isinstance(payload, dict):
        sample = {}
    else:
        evidence = (payload.get("structured") or {}).get("sample_raster_value") or {}
        sample = evidence.get("structured") or {}
    sampled_scenes = [
        {
            "item_id": str(scene.get("item_id") or ""),
            "date": str(scene.get("date") or "")[:10],
        }
        for scene in sample.get("sampled_scenes") or []
        if isinstance(scene, dict)
    ]
    sampled_item_ids = list(
        dict.fromkeys(scene["item_id"] for scene in sampled_scenes if scene["item_id"])
    )
    sampled_dates = list(
        dict.fromkeys(scene["date"] for scene in sampled_scenes if scene["date"])
    )
    expected_item_id = str(feature.get("id") or "")
    properties = feature.get("properties") or {}
    expected_dates = {
        str(value)[:10]
        for value in (
            properties.get("datetime"),
            properties.get("start_datetime"),
            properties.get("end_datetime"),
        )
        if value
    }
    matching_scene = next(
        (
            scene
            for scene in sampled_scenes
            if scene["item_id"] == expected_item_id
            and (not expected_dates or scene["date"] in expected_dates)
        ),
        None,
    )
    return {
        "sampled_scenes": sampled_scenes,
        "sampled_item_ids": sampled_item_ids,
        "sampled_dates": sampled_dates,
        "item_matches": bool(expected_item_id and expected_item_id in sampled_item_ids),
        "date_matches": not expected_dates
        or bool(expected_dates.intersection(sampled_dates)),
        "scene_matches": matching_scene is not None,
    }


def _response_text(payload: Any) -> str:
    """Return the principal human-readable response from an endpoint payload."""
    if not isinstance(payload, dict):
        return str(payload)
    result = payload.get("result")
    candidates = (
        payload.get("response"),
        payload.get("answer"),
        result.get("analysis") if isinstance(result, dict) else None,
        result.get("response") if isinstance(result, dict) else None,
        result.get("summary") if isinstance(result, dict) else None,
        payload.get("detail"),
        payload.get("error"),
    )
    return str(next((value for value in candidates if value), ""))


def _result_errors(payload: Any) -> list[str]:
    """Collect non-empty structured error values from a result payload."""
    errors: list[str] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child in value.items():
                if "error" in child_key.casefold() and child not in (None, "", [], {}):
                    errors.append(str(child))
                else:
                    walk(child, child_key)
        elif isinstance(value, list):
            for child in value:
                walk(child, key)

    walk(payload)
    return errors


def _query_bbox(
    payload: dict[str, Any], features: list[dict[str, Any]]
) -> list[float] | None:
    """Return the requested or rendered STAC bounds."""
    candidates = (
        payload.get("translation_metadata", {}).get("stac_query", {}).get("bbox"),
        payload.get("data", {}).get("search_metadata", {}).get("bbox"),
        features[0].get("bbox") if features else None,
    )
    for candidate in candidates:
        if isinstance(candidate, list) and len(candidate) == 4:
            return [float(value) for value in candidate]
    return None


def _bbox_covers(bbox: list[float] | None, center: tuple[float, float]) -> bool:
    """Return whether a bbox contains an expected latitude/longitude point."""
    if not bbox:
        return False
    latitude, longitude = center
    return bbox[0] <= longitude <= bbox[2] and bbox[1] <= latitude <= bbox[3]


def run_setup_scenario(
    scenario: Scenario,
    *,
    base_url: str,
    index: int,
    features: dict[str, Any],
    adversarial_context: bool = False,
) -> dict[str, Any]:
    """Execute and validate one primary setup query."""
    expected = EXPECTED_SETUP[scenario.setup_query]
    kind = expected["kind"]
    if kind == "pro" and not features.get("mpcPro"):
        return {
            "family": scenario.family,
            "location": scenario.location,
            "setup_query": scenario.setup_query,
            "expected_kind": kind,
            "outcome": "blocked",
            "elapsed_ms": 0,
            "blocked_reason": "MPC Pro tenant imagery is disabled in this deployment.",
        }
    started = time.perf_counter()
    request_payload = {
        "query": scenario.setup_query,
        "session_id": f"get-started-matrix-{index:02d}-{int(time.time())}",
        "stac_mode": "pro" if kind == "pro" else "public",
        "geoint_mode": False,
        "include_visualization": True,
    }
    if adversarial_context:
        request_payload.update(ADVERSARIAL_SETUP_CONTEXT)
    status, payload = _post_json(base_url, "/api/query", request_payload)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    returned_features = _features(payload) if isinstance(payload, dict) else []
    collections = sorted(
        {
            str(feature.get("collection"))
            for feature in returned_features
            if feature.get("collection")
        }
    )
    bbox = (
        _query_bbox(payload, returned_features) if isinstance(payload, dict) else None
    )
    navigate = payload.get("navigate_to") if isinstance(payload, dict) else None
    actual_center = None
    distance_km = None
    if isinstance(navigate, dict):
        latitude = navigate.get("latitude")
        longitude = navigate.get("longitude")
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            actual_center = (float(latitude), float(longitude))
            distance_km = round(_haversine_km(expected["center"], actual_center), 1)

    feature_covers_point = any(
        _feature_covers(feature, expected["center"]) for feature in returned_features
    )
    requested_dates = _requested_date_range(scenario.setup_query)
    date_matches = any(
        _feature_overlaps_date_range(feature, requested_dates)
        for feature in returned_features
    )
    matching_stac_scene = next(
        (
            feature
            for feature in returned_features
            if feature.get("collection") == expected.get("collection")
            and _feature_covers(feature, expected["center"])
            and _feature_overlaps_date_range(feature, requested_dates)
        ),
        None,
    )
    if kind == "stac":
        passed = status == 200 and matching_stac_scene is not None
        outcome = "pass" if passed else "fail"
    elif kind == "navigate":
        passed = (
            status == 200
            and payload.get("action") == "navigate_to"
            and distance_km is not None
            and distance_km <= expected["max_distance_km"]
        )
        outcome = "pass" if passed else "fail"
    else:
        matching_stac_scene = next(
            (
                feature
                for feature in returned_features
                if str(
                    feature.get("stac_mode")
                    or feature.get("_planetary_explorer_stac_mode")
                    or ""
                ).casefold()
                == "pro"
                and _feature_covers(feature, expected["center"])
                and _feature_overlaps_date_range(feature, requested_dates)
            ),
            None,
        )
        passed = status == 200 and matching_stac_scene is not None
        outcome = "pass" if passed else "fail"

    response_text = ""
    if isinstance(payload, dict):
        response_text = str(
            payload.get("response")
            or payload.get("detail")
            or payload.get("error")
            or ""
        )
    return {
        "family": scenario.family,
        "location": scenario.location,
        "setup_query": scenario.setup_query,
        "expected_kind": kind,
        "outcome": outcome,
        "http_status": status,
        "elapsed_ms": elapsed_ms,
        "action": payload.get("action") if isinstance(payload, dict) else None,
        "expected_center": list(expected["center"]),
        "actual_center": list(actual_center) if actual_center else None,
        "distance_km": distance_km,
        "bbox": bbox,
        "covers_expected_center": _bbox_covers(bbox, expected["center"]),
        "returned_scene_covers_expected_center": feature_covers_point,
        "requested_dates": list(requested_dates) if requested_dates else None,
        "returned_date_matches": date_matches,
        "matching_scene_id": matching_stac_scene.get("id")
        if matching_stac_scene
        else None,
        "expected_collection": expected.get("collection"),
        "collections": collections,
        "item_count": len(returned_features),
        "first_item": returned_features[0].get("id") if returned_features else None,
        "response": response_text[:1000],
    }


def _get_json(base_url: str, path: str) -> tuple[int, Any]:
    """GET JSON and return the HTTP status plus decoded response body."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8", errors="replace"))


def run_setup_matrix(
    scenarios: list[Scenario],
    base_url: str,
    *,
    release_metadata: dict[str, str] | None = None,
    adversarial_context: bool = False,
) -> dict[str, Any]:
    """Execute all primary Get Started setup queries."""
    config_status, config = _get_json(base_url, "/api/config")
    if config_status != 200:
        raise RuntimeError(f"Could not read deployment config: HTTP {config_status}")
    deployment_features = config.get("features", {})
    results = []
    for index, scenario in enumerate(scenarios, start=1):
        result = run_setup_scenario(
            scenario,
            base_url=base_url,
            index=index,
            features=deployment_features,
            adversarial_context=adversarial_context,
        )
        results.append(result)
        print(
            f"[{index:02d}/{len(scenarios)}] {result['outcome'].upper():7} "
            f"{scenario.family}: {scenario.location} ({result['elapsed_ms']} ms)",
            file=sys.stderr,
        )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "deployment_features": deployment_features,
        "scenario_count": len(scenarios),
        "adversarial_context": (
            ADVERSARIAL_SETUP_CONTEXT if adversarial_context else None
        ),
        "results": results,
    }
    if release_metadata:
        report["release"] = release_metadata
    return report


def _run_vision_raster(
    scenario: Scenario,
    *,
    base_url: str,
    index: int,
    attempts: int,
    retry_delay_seconds: float,
    model: str | None,
) -> dict[str, Any]:
    """Load one Vision dataset and run its canonical raster sample."""
    expected = EXPECTED_SETUP[scenario.setup_query]
    setup_status, setup = _post_json(
        base_url,
        "/api/query",
        {
            "query": scenario.setup_query,
            "session_id": f"get-started-vision-setup-{index:02d}-{int(time.time())}",
            "stac_mode": "public",
            "geoint_mode": False,
            "include_visualization": True,
        },
    )
    features = _features(setup) if isinstance(setup, dict) else []
    if setup_status != 200 or not features:
        return {
            "family": scenario.family,
            "location": scenario.location,
            "question": scenario.raster_query,
            "outcome": "fail",
            "stage": "setup",
            "http_status": setup_status,
            "response": _response_text(setup)[:1000],
        }

    pin = expected["center"]
    feature = _select_feature_for_point(features, pin)
    if feature is None:
        return {
            "family": scenario.family,
            "location": scenario.location,
            "question": scenario.raster_query,
            "outcome": "fail",
            "stage": "scene_selection",
            "pin": list(pin),
            "item_count": len(features),
            "response": "No returned scene covers the canonical scenario point.",
        }
    tile_urls = (setup.get("translation_metadata") or {}).get("all_tile_urls") or []
    matching_tiles = [
        tile
        for tile in tile_urls
        if not tile.get("item_id") or tile.get("item_id") == feature.get("id")
    ]
    started = time.perf_counter()
    request_payload = {
        "query": scenario.raster_query,
        "session_id": f"get-started-vision-raster-{index:02d}-{int(time.time())}",
        "stac_mode": "public",
        "geoint_mode": True,
        "geoint_module": "vision",
        "include_visualization": True,
        "pin": {"lat": pin[0], "lng": pin[1]},
        "current_collection": expected["collection"],
        "stac_items": [feature],
        "tile_urls": matching_tiles[:1],
        "has_satellite_data": True,
    }
    if model:
        request_payload["model"] = model
        request_payload["reasoning_effort"] = "low"
    status, payload, attempt_count = _post_json_with_retry(
        base_url,
        "/api/query",
        request_payload,
        attempts=attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    success, evidence_error = _evidence_success(payload, "sample_raster_value")
    tools = payload.get("tools_used") or [] if isinstance(payload, dict) else []
    provenance = _raster_sample_provenance(payload, feature)
    return {
        "family": scenario.family,
        "location": scenario.location,
        "question": scenario.raster_query,
        "outcome": "pass"
        if (
            status == 200
            and success
            and "sample_raster_value" in _tool_names(tools)
            and provenance["scene_matches"]
        )
        else "fail",
        "stage": "raster",
        "http_status": status,
        "elapsed_ms": elapsed_ms,
        "attempts": attempt_count,
        "pin": list(pin),
        "collection": expected["collection"],
        "item_id": feature.get("id"),
        "tools_used": tools,
        **provenance,
        "evidence_error": evidence_error,
        "response": _response_text(payload)[:1500],
    }


def _module_request(
    scenario: Scenario,
    *,
    base_url: str,
    features: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """Return endpoint, request body, or a capability block reason."""
    center = EXPECTED_SETUP[scenario.setup_query]["center"]
    latitude, longitude = center
    if scenario.family == "Terrain":
        return (
            "/api/geoint/terrain/chat",
            {
                "message": scenario.question,
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": 5.0,
            },
            None,
        )
    if scenario.family == "Mobility":
        return (
            "/api/geoint/mobility",
            {
                "latitude": latitude,
                "longitude": longitude,
                "latitude_b": latitude + 0.035,
                "longitude_b": longitude + 0.05,
                "user_query": scenario.question,
            },
            None,
        )
    if scenario.family == "Extreme Weather":
        return (
            "/api/geoint/extreme-weather",
            {
                "latitude": latitude,
                "longitude": longitude,
                "user_query": scenario.question,
            },
            None,
        )
    if scenario.family == "Building Damage":
        if not features.get("mpcPro"):
            return "", None, "MPC Pro tenant imagery is disabled in this deployment."
        return (
            "",
            None,
            (
                "Building Damage requires a browser-captured screenshot backed by "
                "authenticated MPC Pro scene references; the API-only matrix does "
                "not manufacture that evidence."
            ),
        )
    if scenario.family == "Site Intel":
        if not features.get("fabric"):
            return "", None, "Fabric-backed Site Intel is disabled in this deployment."
        return (
            "/api/sites/audit",
            {
                "lat": latitude,
                "lng": longitude,
                "claimed_mw": 200,
                "user_query": scenario.question,
            },
            None,
        )
    if scenario.family == "Resilience":
        if features.get("resilience") is False:
            return "", None, "Resilience is disabled in this deployment."
        token = os.getenv("PLANETARY_EXPLORER_ACCESS_TOKEN")
        if not token:
            return "", None, "Sign-in is required for the Resilience workflow."
        lower = (scenario.question or "").casefold()
        region = "BC" if "vancouver" in lower else None
        hazards = [hazard for hazard in ("heat", "wildfire") if hazard in lower]
        return (
            "/api/resilience/assess/smart",
            {
                "region_filter": region,
                "horizon_days": 7,
                "hazards": hazards or ["heat", "wildfire"],
                "user_query": scenario.question,
            },
            None,
        )
    if scenario.family == "Forecast":
        if features.get("weather") is False:
            return "", None, "Forecast providers are disabled in this deployment."
        hours = (
            120
            if "five-day" in (scenario.question or "")
            else 24
            if "24 hour" in (scenario.question or "")
            else 72
        )
        return (
            "/api/geoint/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "lead_hours": hours,
                "grid_size": 8,
                "user_query": scenario.question,
                "location_label": scenario.location,
            },
            None,
        )
    raise ValueError(f"Unsupported scenario family: {scenario.family}")


def _tool_names(tools: Any) -> set[str]:
    """Normalize tool evidence into a set of names."""
    if not isinstance(tools, list):
        return set()
    return {
        str(tool.get("tool") or tool.get("name"))
        if isinstance(tool, dict)
        else str(tool)
        for tool in tools
        if tool
    }


def _validate_module_result(
    scenario: Scenario,
    status: int,
    payload: Any,
    elapsed_ms: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Apply family-specific success checks to a module response."""
    errors = _result_errors(payload)
    result = payload.get("result") if isinstance(payload, dict) else None
    details: dict[str, Any] = {"errors": errors}
    family = scenario.family
    if family == "Terrain":
        tools = payload.get("tool_calls") if isinstance(payload, dict) else None
        if tools is None and isinstance(result, dict):
            tools = result.get("tool_calls")
        details["tools"] = tools or []
        names = _tool_names(tools)
        valid = (
            status == 200
            and bool(_response_text(payload))
            and set(scenario.expected_tools).issubset(names)
            and not errors
        )
    elif family == "Mobility":
        details["analysis_type"] = (
            result.get("analysis_type") if isinstance(result, dict) else None
        )
        tools = result.get("tool_calls") if isinstance(result, dict) else []
        details["tools"] = tools or []
        traverse_result = next(
            (
                tool.get("result")
                for tool in tools or []
                if isinstance(tool, dict)
                and tool.get("tool") == "analyze_two_point_traverse"
                and isinstance(tool.get("result"), dict)
            ),
            None,
        )
        route = traverse_result.get("route") if traverse_result else None
        corridor = traverse_result.get("corridor") if traverse_result else None
        details["traverse_evidence"] = {
            "distance_km": route.get("distance_km")
            if isinstance(route, dict)
            else None,
            "corridor_status": corridor.get("overall_status")
            if isinstance(corridor, dict)
            else None,
            "waypoints_sampled": corridor.get("waypoints_sampled")
            if isinstance(corridor, dict)
            else None,
            "has_origin": isinstance(traverse_result.get("origin"), dict)
            if traverse_result
            else False,
            "has_destination": isinstance(traverse_result.get("destination"), dict)
            if traverse_result
            else False,
            "origin_source_count": len(
                (traverse_result.get("coverage") or {}).get("origin_sources") or []
            )
            if traverse_result
            else 0,
            "destination_source_count": len(
                (traverse_result.get("coverage") or {}).get("destination_sources") or []
            )
            if traverse_result
            else 0,
            "waypoints_with_data": (
                (traverse_result.get("coverage") or {}).get("waypoints_with_data")
            )
            if traverse_result
            else 0,
        }
        substantive_evidence = (
            traverse_result is not None
            and traverse_result.get("complete") is True
            and isinstance(details["traverse_evidence"]["distance_km"], (int, float))
            and details["traverse_evidence"]["corridor_status"]
            in {"GO", "SLOW-GO", "NO-GO"}
            and isinstance(details["traverse_evidence"]["waypoints_sampled"], int)
            and details["traverse_evidence"]["waypoints_sampled"] > 0
            and details["traverse_evidence"]["has_origin"]
            and details["traverse_evidence"]["has_destination"]
            and details["traverse_evidence"]["origin_source_count"] > 0
            and details["traverse_evidence"]["destination_source_count"] > 0
            and details["traverse_evidence"]["waypoints_with_data"] > 0
        )
        details["within_ingress_retry_window"] = (
            elapsed_ms is None or elapsed_ms <= 50_000
        )
        valid = (
            status == 200
            and bool(_response_text(payload))
            and set(scenario.expected_tools).issubset(_tool_names(tools))
            and substantive_evidence
            and details["within_ingress_retry_window"]
            and not errors
        )
    elif family == "Extreme Weather":
        tools = result.get("tool_calls") if isinstance(result, dict) else []
        details["tools"] = tools or []
        evidence_valid = True
        by_name = {
            str(tool.get("tool")): tool.get("result")
            for tool in tools or []
            if isinstance(tool, dict) and tool.get("tool")
        }
        if "sample_timeseries" in scenario.expected_tools:
            timeseries = by_name.get("sample_timeseries") or {}
            periods = (
                timeseries.get("periods") if isinstance(timeseries, dict) else None
            )
            numeric_periods = [
                period
                for period in periods or []
                if isinstance(period, dict)
                and isinstance(period.get("mean"), (int, float))
            ]
            details["monthly_period_count"] = len(numeric_periods)
            evidence_valid = len(numeric_periods) == 12
        elif "compare_climate_scenarios" in scenario.expected_tools:
            comparison_result = by_name.get("compare_climate_scenarios") or {}
            comparison = (
                comparison_result.get("comparison")
                if isinstance(comparison_result, dict)
                else {}
            ) or {}
            comparison_cells = {
                f"{variable}.{ssp}": comparison.get(variable, {})
                .get(ssp, {})
                .get("value")
                for variable in ("tasmax", "pr")
                for ssp in ("ssp245", "ssp585")
            }
            details["comparison_cells"] = comparison_cells
            evidence_valid = all(
                isinstance(value, (int, float)) for value in comparison_cells.values()
            )
        valid = (
            status == 200
            and bool(_response_text(payload))
            and set(scenario.expected_tools).issubset(_tool_names(tools))
            and evidence_valid
            and not errors
        )
    elif family == "Site Intel":
        scores = payload.get("scores") if isinstance(payload, dict) else None
        details["scores"] = scores or {}
        valid = (
            status == 200
            and isinstance(scores, dict)
            and isinstance(scores.get("overall"), (int, float))
            and not errors
        )
    elif family == "Resilience":
        facilities = payload.get("facilities") if isinstance(payload, dict) else None
        details["route"] = payload.get("route") if isinstance(payload, dict) else None
        details["facility_count"] = (
            len(facilities) if isinstance(facilities, list) else 0
        )
        valid = status == 200 and isinstance(facilities, list) and not errors
    elif family == "Forecast":
        dossier = result if isinstance(result, dict) else {}
        called = dossier.get("providers_called") or []
        succeeded = dossier.get("providers_succeeded") or []
        forecasts = dossier.get("forecasts") or []
        summary = dossier.get("ensemble_summary") or {}
        details["providers_called"] = called
        details["providers_succeeded"] = succeeded
        details["providers_failed"] = dossier.get("providers_failed") or []
        details["ensemble_summary"] = summary
        details["forecast_sources"] = [
            {
                "provider_id": forecast.get("provider_id"),
                "source": (forecast.get("extras") or {}).get("source"),
                "native_model_inference": (forecast.get("extras") or {}).get(
                    "native_model_inference"
                ),
                "data_source_note": (forecast.get("extras") or {}).get(
                    "data_source_note"
                ),
            }
            for forecast in forecasts
            if isinstance(forecast, dict)
        ]
        question = (scenario.question or "").casefold()
        expected_providers = (
            {"aurora-1.x", "earth2-fcn"}
            if "aurora" in question and "earth-2" in question
            else set()
        )
        if "every available model" in question:
            required_variables = {"t2m", "precip", "u10", "v10"}
        else:
            required_variables = set()
            if "temperature" in question:
                required_variables.add("t2m")
            if "wind" in question:
                required_variables.update({"u10", "v10"})
            if "precip" in question or "rain" in question:
                required_variables.add("precip")
        details["required_variables"] = sorted(required_variables)
        summary_variables = summary.get("variables") or {}

        def variable_values(forecast: dict[str, Any], variable: str) -> list[float]:
            return [
                value
                for row in (forecast.get("variables") or {}).get(variable, [])
                if isinstance(row, list)
                for value in row
                if isinstance(value, (int, float))
            ]

        forecast_provenance_valid = len(forecasts) == len(succeeded) and all(
            isinstance(forecast, dict)
            and forecast.get("provider_id") in succeeded
            and bool((forecast.get("extras") or {}).get("source"))
            and isinstance(
                (forecast.get("extras") or {}).get("native_model_inference"),
                bool,
            )
            and all(
                isinstance((forecast.get("units") or {}).get(variable), str)
                and bool((forecast.get("units") or {}).get(variable))
                and bool(variable_values(forecast, variable))
                for variable in required_variables
            )
            for forecast in forecasts
        )
        summaries_valid = all(
            isinstance(summary_variables.get(variable), dict)
            and not summary_variables[variable].get("error")
            and isinstance(summary_variables[variable].get("mean"), (int, float))
            and isinstance(summary_variables[variable].get("min"), (int, float))
            and isinstance(summary_variables[variable].get("max"), (int, float))
            and isinstance(summary_variables[variable].get("unit"), str)
            and bool(summary_variables[variable].get("unit"))
            and summary_variables[variable].get("samples") == len(succeeded)
            for variable in required_variables
        )
        precipitation_valid = "precip" not in required_variables or (
            summary_variables["precip"]["min"] >= 0
            and all(
                min(variable_values(forecast, "precip")) >= 0 for forecast in forecasts
            )
        )
        every_provider_valid = "every available model" not in question or (
            len(called) >= 2
            and set(called) == set(succeeded)
            and not dossier.get("providers_failed")
        )
        valid = (
            status == 200
            and len(succeeded) > 0
            and expected_providers.issubset(set(succeeded))
            and set(succeeded)
            == {
                forecast.get("provider_id")
                for forecast in forecasts
                if isinstance(forecast, dict)
            }
            and every_provider_valid
            and forecast_provenance_valid
            and summaries_valid
            and precipitation_valid
        )
    else:
        valid = status == 200 and bool(_response_text(payload)) and not errors
    return valid, details


def run_analysis_matrix(
    scenarios: list[Scenario],
    base_url: str,
    *,
    attempts: int,
    retry_delay_seconds: float,
    pace_seconds: float,
    model: str | None,
    release_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute all Vision raster and specialized module scenarios."""
    config_status, config = _get_json(base_url, "/api/config")
    if config_status != 200:
        raise RuntimeError(f"Could not read deployment config: HTTP {config_status}")
    deployment_features = config.get("features", {})
    results: list[dict[str, Any]] = []

    vision = [
        scenario for scenario in scenarios if scenario.family.startswith("Vision -")
    ]
    for index, scenario in enumerate(vision, start=1):
        result = _run_vision_raster(
            scenario,
            base_url=base_url,
            index=index,
            attempts=attempts,
            retry_delay_seconds=retry_delay_seconds,
            model=model,
        )
        results.append(result)
        print(
            f"[Vision {index:02d}/{len(vision)}] {result['outcome'].upper():7} "
            f"{scenario.location}",
            file=sys.stderr,
        )
        if pace_seconds:
            time.sleep(pace_seconds)

    specialized = [
        scenario for scenario in scenarios if not scenario.family.startswith("Vision -")
    ]
    for index, scenario in enumerate(specialized, start=1):
        endpoint, body, blocked_reason = _module_request(
            scenario,
            base_url=base_url,
            features=deployment_features,
        )
        if blocked_reason:
            result = {
                "family": scenario.family,
                "location": scenario.location,
                "question": scenario.question,
                "outcome": "blocked",
                "stage": "analysis",
                "blocked_reason": blocked_reason,
            }
        else:
            started = time.perf_counter()
            token = os.getenv("PLANETARY_EXPLORER_ACCESS_TOKEN")
            headers = (
                {"Authorization": f"Bearer {token}"}
                if scenario.family == "Resilience" and token
                else None
            )
            status, payload, attempt_count = _post_json_with_retry(
                base_url,
                endpoint,
                body or {},
                attempts=attempts,
                retry_delay_seconds=retry_delay_seconds,
                headers=headers,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            valid, details = _validate_module_result(
                scenario,
                status,
                payload,
                elapsed_ms,
            )
            result = {
                "family": scenario.family,
                "location": scenario.location,
                "question": scenario.question,
                "outcome": "pass" if valid else "fail",
                "stage": "analysis",
                "endpoint": endpoint,
                "http_status": status,
                "elapsed_ms": elapsed_ms,
                "attempts": attempt_count,
                "request": body,
                "response": _response_text(payload)[:2500],
                **details,
            }
        results.append(result)
        print(
            f"[Module {index:02d}/{len(specialized)}] {result['outcome'].upper():7} "
            f"{scenario.family}: {scenario.location}",
            file=sys.stderr,
        )
        if pace_seconds:
            time.sleep(pace_seconds)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "deployment_features": deployment_features,
        "scenario_count": len(results),
        "results": results,
    }
    if release_metadata:
        report["release"] = release_metadata
    return report


def validate_inventory(scenarios: list[Scenario]) -> None:
    """Require two or three locations in every documented scenario family."""
    counts: dict[str, int] = {}
    for scenario in scenarios:
        counts[scenario.family] = counts.get(scenario.family, 0) + 1

    invalid = {family: count for family, count in counts.items() if count not in (2, 3)}
    if invalid:
        details = ", ".join(f"{family}={count}" for family, count in invalid.items())
        raise ValueError(f"Get Started families must have 2-3 locations: {details}")


def _report_exit_code(report: dict[str, Any]) -> int:
    """Return failure when any runnable scenario failed validation."""
    return (
        1
        if any(result.get("outcome") == "fail" for result in report.get("results", []))
        else 0
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Validate the canonical Get Started scenario inventory."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print every normalized scenario as JSON.",
    )
    parser.add_argument(
        "--run-setups",
        action="store_true",
        help="Execute every primary setup query against the deployed API.",
    )
    parser.add_argument(
        "--run-analyses",
        action="store_true",
        help="Execute Vision raster and specialized module scenarios.",
    )
    parser.add_argument(
        "--adversarial-context",
        action="store_true",
        help=(
            "Run setup rows with a conflicting Sydney pin, bounds, and loaded "
            "collection to prove each example owns its location."
        ),
    )
    parser.add_argument(
        "--verify-release-only",
        action="store_true",
        help="Verify release identifiers without running scenario matrices.",
    )
    parser.add_argument(
        "--base-url",
        help="Planetary Explorer API origin. Required for live execution.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Acknowledge execution against an Azure-hosted production origin.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the JSON result to this path.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Maximum attempts for transient service-capacity failures.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=20.0,
        help="Base delay between transient retries.",
    )
    parser.add_argument(
        "--pace-seconds",
        type=float,
        default=10.0,
        help="Delay between live analysis scenarios.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.6-terra",
        help="Deployed model used for generic Vision analysis routing.",
    )
    parser.add_argument("--api-revision", help="Verified Container Apps revision.")
    parser.add_argument(
        "--api-image-digest", help="Verified immutable API image digest."
    )
    parser.add_argument("--weather-revision", help="Verified weather adapter revision.")
    parser.add_argument(
        "--weather-image-digest",
        help="Verified immutable weather adapter image digest.",
    )
    parser.add_argument(
        "--frontend-deployment-id", help="Verified App Service deployment ID."
    )
    parser.add_argument("--frontend-bundle", help="Verified frontend bundle filename.")
    parser.add_argument(
        "--frontend-bundle-sha256", help="Verified frontend bundle SHA-256."
    )
    parser.add_argument("--frontend-url", help="Frontend HTTPS origin to verify.")
    parser.add_argument("--azure-subscription", help="Expected Azure subscription ID.")
    parser.add_argument("--azure-tenant", help="Expected Microsoft Entra tenant ID.")
    parser.add_argument("--azure-resource-group", help="Azure resource group name.")
    parser.add_argument("--azure-container-app", help="API Container App name.")
    parser.add_argument(
        "--azure-weather-app", help="Weather adapter Container App name."
    )
    parser.add_argument("--azure-frontend-app", help="Frontend App Service name.")
    parser.add_argument(
        "--azure-geofm-resource-group", help="GeoFM worker resource group."
    )
    parser.add_argument("--azure-geofm-worker", help="GeoFM worker Container App name.")
    return parser


def _release_metadata(args: argparse.Namespace) -> dict[str, str]:
    """Return only release identifiers explicitly verified by the caller."""
    fields = {
        "api_revision": args.api_revision,
        "api_image_digest": args.api_image_digest,
        "weather_revision": args.weather_revision,
        "weather_image_digest": args.weather_image_digest,
        "frontend_deployment_id": args.frontend_deployment_id,
        "frontend_bundle": args.frontend_bundle,
        "frontend_bundle_sha256": args.frontend_bundle_sha256,
    }
    return {key: value for key, value in fields.items() if value}


def _requires_release_binding(args: argparse.Namespace) -> bool:
    """Return whether this invocation must prove one immutable release."""
    if args.verify_release_only:
        return True
    return bool(
        (args.run_setups or args.run_analyses)
        and args.base_url
        and not _is_loopback_url(args.base_url)
    )


def _run_json_command(command: list[str]) -> Any:
    """Run a command and decode its JSON output."""
    command_env = None
    if command and command[0] == "az":
        azure_cli = shutil.which("az") or shutil.which("az.cmd")
        if not azure_cli:
            raise FileNotFoundError("Azure CLI executable was not found")
        command = [azure_cli, *command[1:]]
        if Path(azure_cli).suffix.casefold() in {".cmd", ".bat"}:
            command_shell = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
            if not command_shell:
                raise FileNotFoundError("Windows command processor was not found")
            command_env = os.environ.copy()
            command_env["PLANETARY_EXPLORER_AZ_COMMAND"] = (
                f"call {subprocess.list2cmdline(command)}"
            )
            command = [
                command_shell,
                "/d",
                "/s",
                "/c",
                "%PLANETARY_EXPLORER_AZ_COMMAND%",
            ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=command_env,
    )
    return json.loads(result.stdout)


def _read_url_bytes(url: str) -> bytes:
    """Read one no-cache HTTPS resource as bytes."""
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {response.status}")
        return response.read()


def _verify_release_metadata(
    args: argparse.Namespace,
    base_url: str,
) -> dict[str, Any]:
    """Verify release identifiers against live Azure and HTTPS state."""
    release: dict[str, Any] = _release_metadata(args)
    if not release:
        return release

    required = {
        "api_revision": args.api_revision,
        "api_image_digest": args.api_image_digest,
        "weather_revision": args.weather_revision,
        "weather_image_digest": args.weather_image_digest,
        "frontend_deployment_id": args.frontend_deployment_id,
        "frontend_bundle": args.frontend_bundle,
        "frontend_bundle_sha256": args.frontend_bundle_sha256,
        "frontend_url": args.frontend_url,
        "azure_subscription": args.azure_subscription,
        "azure_tenant": args.azure_tenant,
        "azure_resource_group": args.azure_resource_group,
        "azure_container_app": args.azure_container_app,
        "azure_weather_app": args.azure_weather_app,
        "azure_frontend_app": args.azure_frontend_app,
        "azure_geofm_resource_group": args.azure_geofm_resource_group,
        "azure_geofm_worker": args.azure_geofm_worker,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError("Release verification requires: " + ", ".join(sorted(missing)))

    account = _run_json_command(["az", "account", "show", "-o", "json"])
    if account.get("id") != args.azure_subscription:
        raise ValueError("Azure subscription does not match the release target")
    if account.get("tenantId") != args.azure_tenant:
        raise ValueError("Azure tenant does not match the release target")

    app = _run_json_command(
        [
            "az",
            "containerapp",
            "show",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_resource_group,
            "--name",
            args.azure_container_app,
            "-o",
            "json",
        ]
    )
    app_properties = app.get("properties") or {}
    if app_properties.get("provisioningState") != "Succeeded":
        raise ValueError("API Container App provisioning is not successful")
    if app_properties.get("latestReadyRevisionName") != args.api_revision:
        raise ValueError("API revision is not the latest ready revision")
    api_fqdn = ((app_properties.get("configuration") or {}).get("ingress") or {}).get(
        "fqdn"
    )
    if (urlparse(base_url).hostname or "").casefold() != str(api_fqdn).casefold():
        raise ValueError("API base URL does not match the Container App ingress")

    revision = _run_json_command(
        [
            "az",
            "containerapp",
            "revision",
            "show",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_resource_group,
            "--name",
            args.azure_container_app,
            "--revision",
            args.api_revision,
            "-o",
            "json",
        ]
    )
    revision_properties = revision.get("properties") or {}
    containers = (revision_properties.get("template") or {}).get("containers") or []
    image = containers[0].get("image") if containers else ""
    expected_image_suffix = f"@{args.api_image_digest}"
    if not str(image).endswith(expected_image_suffix):
        raise ValueError("API revision image digest does not match")
    if revision_properties.get("healthState") != "Healthy":
        raise ValueError("API revision is not healthy")
    if revision_properties.get("runningState") != "Running":
        raise ValueError("API revision is not running")
    if revision_properties.get("active") is not True:
        raise ValueError("API revision is not active")
    if revision_properties.get("trafficWeight") != 100:
        raise ValueError("API revision is not serving 100% traffic")

    weather_app = _run_json_command(
        [
            "az",
            "containerapp",
            "show",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_resource_group,
            "--name",
            args.azure_weather_app,
            "-o",
            "json",
        ]
    )
    weather_app_properties = weather_app.get("properties") or {}
    if weather_app_properties.get("provisioningState") != "Succeeded":
        raise ValueError("Weather adapter Container App provisioning is not successful")
    if weather_app_properties.get("latestReadyRevisionName") != args.weather_revision:
        raise ValueError("Weather adapter revision is not the latest ready revision")

    weather_revision = _run_json_command(
        [
            "az",
            "containerapp",
            "revision",
            "show",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_resource_group,
            "--name",
            args.azure_weather_app,
            "--revision",
            args.weather_revision,
            "-o",
            "json",
        ]
    )
    weather_revision_properties = weather_revision.get("properties") or {}
    weather_containers = (weather_revision_properties.get("template") or {}).get(
        "containers"
    ) or []
    weather_image = weather_containers[0].get("image") if weather_containers else ""
    if not str(weather_image).endswith(f"@{args.weather_image_digest}"):
        raise ValueError("Weather adapter revision image digest does not match")
    if weather_revision_properties.get("healthState") != "Healthy":
        raise ValueError("Weather adapter revision is not healthy")
    if weather_revision_properties.get("runningState") not in {
        "Running",
        "ScaledToZero",
    }:
        raise ValueError(
            "Weather adapter revision is neither running nor scaled to zero"
        )
    if weather_revision_properties.get("active") is not True:
        raise ValueError("Weather adapter revision is not active")
    if weather_revision_properties.get("trafficWeight") != 100:
        raise ValueError("Weather adapter revision is not serving 100% traffic")

    health_status, health = _get_json(base_url, "/api/health")
    if health_status != 200 or health.get("status") != "healthy":
        raise ValueError("API health endpoint is not healthy")

    deployments = _run_json_command(
        [
            "az",
            "webapp",
            "log",
            "deployment",
            "list",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_resource_group,
            "--name",
            args.azure_frontend_app,
            "-o",
            "json",
        ]
    )
    deployment = next(
        (item for item in deployments if item.get("id") == args.frontend_deployment_id),
        None,
    )
    if not deployment:
        raise ValueError("Frontend deployment ID was not found")
    if not deployment.get("complete") or deployment.get("status") != 4:
        raise ValueError("Frontend deployment did not complete successfully")
    if deployment.get("active") is not True:
        raise ValueError("Frontend deployment is not active")

    geofm_worker = _run_json_command(
        [
            "az",
            "containerapp",
            "show",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_geofm_resource_group,
            "--name",
            args.azure_geofm_worker,
            "-o",
            "json",
        ]
    )
    geofm_scale = ((geofm_worker.get("properties") or {}).get("template") or {}).get(
        "scale"
    ) or {}
    if geofm_scale.get("minReplicas") != 0:
        raise ValueError("GeoFM worker minimum replicas is not zero")
    geofm_revisions = _run_json_command(
        [
            "az",
            "containerapp",
            "revision",
            "list",
            "--subscription",
            args.azure_subscription,
            "--resource-group",
            args.azure_geofm_resource_group,
            "--name",
            args.azure_geofm_worker,
            "-o",
            "json",
        ]
    )
    geofm_active_replicas = sum(
        int((item.get("properties") or {}).get("replicas") or 0)
        for item in geofm_revisions
        if (item.get("properties") or {}).get("active") is True
    )
    if geofm_active_replicas != 0:
        raise ValueError("GeoFM worker has active replicas")

    frontend_url = args.frontend_url.rstrip("/") + "/"
    root = _read_url_bytes(frontend_url).decode("utf-8")
    match = re.search(r'assets/(index-[^"\']+\.js)', root)
    if not match or match.group(1) != args.frontend_bundle:
        raise ValueError("Live frontend bundle name does not match")
    bundle_bytes = _read_url_bytes(f"{frontend_url}assets/{args.frontend_bundle}")
    bundle_sha256 = hashlib.sha256(bundle_bytes).hexdigest()
    if bundle_sha256 != args.frontend_bundle_sha256.casefold():
        raise ValueError("Live frontend bundle SHA-256 does not match")

    release["verification"] = {
        "verified_at": datetime.now(UTC).isoformat(),
        "azure_subscription": args.azure_subscription,
        "azure_tenant": args.azure_tenant,
        "api_fqdn": api_fqdn,
        "api_health": health.get("status"),
        "api_revision_health": revision_properties.get("healthState"),
        "api_revision_running": revision_properties.get("runningState"),
        "api_traffic_weight": revision_properties.get("trafficWeight"),
        "weather_revision_health": weather_revision_properties.get("healthState"),
        "weather_revision_running": weather_revision_properties.get("runningState"),
        "weather_traffic_weight": weather_revision_properties.get("trafficWeight"),
        "frontend_deployment_active": deployment.get("active"),
        "frontend_bundle_live_sha256": bundle_sha256,
        "geofm_worker_min_replicas": geofm_scale.get("minReplicas"),
        "geofm_worker_active_replicas": geofm_active_replicas,
    }
    return release


def _release_binding_snapshot(release: dict[str, Any]) -> dict[str, Any]:
    """Return release evidence without the expected verification timestamp drift."""
    snapshot = dict(release)
    verification = dict(snapshot.get("verification") or {})
    verification.pop("verified_at", None)
    if verification:
        snapshot["verification"] = verification
    else:
        snapshot.pop("verification", None)
    return snapshot


def _reverify_release_metadata(
    args: argparse.Namespace,
    base_url: str,
    initial_release: dict[str, Any],
) -> dict[str, Any]:
    """Recheck live release evidence and reject any mid-matrix drift."""
    current_release = _verify_release_metadata(args, base_url)
    if _release_binding_snapshot(current_release) != _release_binding_snapshot(
        initial_release
    ):
        raise ValueError("Release binding changed during scenario execution")
    return current_release


def main() -> int:
    """Validate and optionally print the scenario inventory."""
    parser = create_parser()
    args = parser.parse_args()
    if (
        args.run_setups or args.run_analyses or args.verify_release_only
    ) and not args.base_url:
        parser.error("--base-url is required for live scenario execution")
    if (
        (args.run_setups or args.run_analyses)
        and not _is_loopback_url(args.base_url)
        and not args.allow_production
    ):
        parser.error("--allow-production is required for every non-loopback origin")
    if _requires_release_binding(args) and not _release_metadata(args):
        parser.error(
            "release-only and remote matrix runs require complete release-binding "
            "arguments"
        )

    try:
        release_metadata = _verify_release_metadata(args, args.base_url or "")
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        parser.error(str(error))
    if args.verify_release_only:
        print(json.dumps(release_metadata, indent=2))
        return 0

    scenarios = load_scenarios()
    validate_inventory(scenarios)

    if args.run_setups:
        report = run_setup_matrix(
            scenarios,
            args.base_url,
            release_metadata=release_metadata,
            adversarial_context=args.adversarial_context,
        )
        try:
            release_metadata = _reverify_release_metadata(
                args,
                args.base_url,
                release_metadata,
            )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            parser.error(str(error))
        if release_metadata:
            report["release"] = release_metadata
        rendered = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(rendered)
        return _report_exit_code(report)
    elif args.run_analyses:
        report = run_analysis_matrix(
            scenarios,
            args.base_url,
            attempts=max(1, args.attempts),
            retry_delay_seconds=max(0.0, args.retry_delay_seconds),
            pace_seconds=max(0.0, args.pace_seconds),
            model=args.model or None,
            release_metadata=release_metadata,
        )
        try:
            release_metadata = _reverify_release_metadata(
                args,
                args.base_url,
                release_metadata,
            )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            parser.error(str(error))
        if release_metadata:
            report["release"] = release_metadata
        rendered = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(rendered)
        return _report_exit_code(report)
    elif args.list:
        print(json.dumps([scenario.__dict__ for scenario in scenarios], indent=2))
    else:
        families = {scenario.family for scenario in scenarios}
        print(f"Validated {len(scenarios)} scenarios across {len(families)} families.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
