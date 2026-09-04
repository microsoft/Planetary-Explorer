"""Precomputed Canadian 2026 STAC examples used by the Get Started UI."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


QUICKSTART_QUERIES: dict[str, dict[str, Any]] = {
    "show sentinel-2 imagery over toronto, canada from 2026-06-01 to 2026-08-26": {
        "collections": ["sentinel-2-l2a"],
        "location": "Toronto, Ontario, Canada",
        "bbox": [-79.64, 43.58, -79.12, 43.86],
        "description": "10m surface-reflectance imagery for Greater Toronto",
        "dataset": "Sentinel-2 L2A",
        "intent": "stac",
        "temporal": "2026-06-01/2026-08-26",
    },
    "show hls s30 imagery at calgary, canada, latitude 51.0300, longitude -114.0800, from 2026-05-01 to 2026-08-26": {
        "collections": ["hls2-s30"],
        "location": "Calgary, Alberta, Canada",
        "bbox": [-114.09, 51.02, -114.07, 51.04],
        "description": "30m harmonized Sentinel-2 imagery at a Calgary pixel",
        "dataset": "HLS S30",
        "intent": "stac",
        "temporal": "2026-05-01/2026-08-26",
    },
    "show landsat imagery over halifax, canada from 2026-01-01 to 2026-08-26": {
        "collections": ["landsat-c2-l2"],
        "location": "Halifax, Nova Scotia, Canada",
        "bbox": [-63.85, 44.48, -63.35, 44.82],
        "description": "Landsat surface reflectance over coastal Nova Scotia",
        "dataset": "Landsat C2 L2",
        "intent": "stac",
        "temporal": "2026-01-01/2026-08-26",
    },
    "show modis thermal anomalies at latitude 54.5000, longitude -115.0000 in alberta from 2026-05-01 to 2026-08-26": {
        "collections": ["modis-14A1-061"],
        "location": "Alberta, Canada",
        "bbox": [-115.01, 54.49, -114.99, 54.51],
        "description": "Daily active-fire observations at an Alberta pixel",
        "dataset": "MODIS 14A1",
        "intent": "stac",
        "temporal": "2026-05-01/2026-08-26",
    },
    "show modis 13q1 vegetation indices over cropland south of regina, saskatchewan, canada, latitude 50.3500, longitude -104.6000, from 2026-04-01 to 2026-08-26": {
        "collections": ["modis-13Q1-061"],
        "location": "Regina, Saskatchewan, Canada",
        "bbox": [-104.61, 50.34, -104.59, 50.36],
        "description": "250m NDVI and EVI composites over Regina cropland",
        "dataset": "MODIS 13Q1",
        "intent": "stac",
        "temporal": "2026-04-01/2026-08-26",
    },
    "show collection modis-17a2h-061 gross primary productivity at latitude 54.1500, longitude -126.5500 in british columbia from 2026-05-01 to 2026-08-26": {
        "collections": ["modis-17A2H-061"],
        "location": "British Columbia, Canada",
        "bbox": [-126.56, 54.14, -126.54, 54.16],
        "description": "8-day vegetation productivity at an interior BC pixel",
        "dataset": "MODIS 17A2H",
        "intent": "stac",
        "temporal": "2026-05-01/2026-08-26",
    },
    "show modis 10a1 daily snow cover at quebec city, canada, latitude 46.8139, longitude -71.2080, from 2025-02-01 to 2025-02-28": {
        "collections": ["modis-10A1-061"],
        "location": "Quebec City, Quebec, Canada",
        "bbox": [-71.218, 46.8039, -71.198, 46.8239],
        "description": "500m daily snow cover and NDSI at Quebec City",
        "dataset": "MODIS 10A1",
        "intent": "stac",
        "temporal": "2025-02-01/2025-02-28",
    },
    "show sentinel-2 imagery along the mackenzie river near norman wells, canada from 2026-05-01 to 2026-06-30": {
        "collections": ["sentinel-2-l2a"],
        "location": "Mackenzie River near Norman Wells, Northwest Territories, Canada",
        "bbox": [-127.20, 65.10, -126.50, 65.50],
        "description": "10m spring river and ice observations near Norman Wells",
        "dataset": "Sentinel-2 L2A",
        "intent": "stac",
        "temporal": "2026-05-01/2026-06-30",
    },
    "show landsat collection 2 level-2 imagery along the hudson bay coast at churchill, manitoba, canada, latitude 58.7684, longitude -94.1650, from 2026-06-01 to 2026-08-26": {
        "collections": ["landsat-c2-l2"],
        "location": "Churchill, Manitoba, Canada",
        "bbox": [-94.175, 58.7584, -94.155, 58.7784],
        "description": "30m summer Hudson Bay coastal observations",
        "dataset": "Landsat C2 L2",
        "intent": "stac",
        "temporal": "2026-06-01/2026-08-26",
    },
    "show copernicus dem terrain around banff, canada for 2026 analysis": {
        "collections": ["cop-dem-glo-30"],
        "location": "Banff, Alberta, Canada",
        "bbox": [-115.80, 51.05, -115.35, 51.40],
        "description": "30m terrain elevation for current-year analysis",
        "dataset": "COP-DEM GLO-30",
        "intent": "stac",
    },
    "show sentinel-1 rtc radar imagery over vancouver, canada from 2026-01-01 to 2026-08-26": {
        "collections": ["sentinel-1-rtc"],
        "location": "Vancouver, British Columbia, Canada",
        "bbox": [-123.40, 49.0, -122.70, 49.40],
        "description": "10m terrain-corrected radar backscatter",
        "dataset": "Sentinel-1 RTC",
        "intent": "stac",
        "temporal": "2026-01-01/2026-08-26",
    },
    "show sentinel-1 rtc radar imagery over the red river, manitoba from 2026-03-01 to 2026-05-31": {
        "collections": ["sentinel-1-rtc"],
        "location": "Red River, Manitoba, Canada",
        "bbox": [-97.45, 49.0, -96.70, 50.20],
        "description": "All-weather spring flood observations",
        "dataset": "Sentinel-1 RTC",
        "intent": "stac",
        "temporal": "2026-03-01/2026-05-31",
    },
}


def normalize_query(query: str) -> str:
    """Normalize a query for exact matching."""
    return query.casefold().strip()


def is_quickstart_query(query: str) -> bool:
    """Return whether a query is a fully specified Canadian example."""
    return normalize_query(query) in QUICKSTART_QUERIES


def get_quickstart_classification(query: str) -> dict[str, Any] | None:
    """Return the precomputed router classification for a known example."""
    quickstart = QUICKSTART_QUERIES.get(normalize_query(query))
    if quickstart is None:
        return None
    return {
        "is_quickstart": True,
        "intent": quickstart.get("intent", "stac"),
        "intent_type": quickstart.get("intent", "stac"),
        "collections": quickstart.get("collections", []),
        "has_location": True,
        "has_temporal": "temporal" in quickstart,
        "data_type": "satellite_imagery",
        "confidence": 1.0,
        "router_action": None,
        "description": quickstart.get("description", ""),
        "dataset": quickstart.get("dataset", ""),
        "needs_satellite_data": True,
        "needs_contextual_info": False,
        "needs_vision_analysis": False,
    }


def get_quickstart_location(query: str) -> dict[str, Any] | None:
    """Return the precomputed Canadian location and STAC constraints."""
    quickstart = QUICKSTART_QUERIES.get(normalize_query(query))
    if quickstart is None:
        return None
    return {
        "location": quickstart.get("location", ""),
        "bbox": quickstart.get("bbox", []),
        "collections": quickstart.get("collections", []),
        "temporal": quickstart.get("temporal"),
        "description": quickstart.get("description", ""),
        "dataset": quickstart.get("dataset", ""),
    }


def get_quickstart_stats() -> dict[str, Any]:
    """Return cache statistics for startup telemetry."""
    collections = {
        collection
        for query_data in QUICKSTART_QUERIES.values()
        for collection in query_data.get("collections", [])
    }
    return {
        "total_queries": len(QUICKSTART_QUERIES),
        "collections_covered": sorted(collections),
        "intents": ["stac"],
        "locations": [query.get("location", "") for query in QUICKSTART_QUERIES.values()],
    }


def get_all_quickstart_queries() -> list[str]:
    """Return all normalized Canadian quick-start query strings."""
    return list(QUICKSTART_QUERIES)


logger.info(
    "[LAUNCH] Quick Start Cache initialized with %d pre-computed queries",
    len(QUICKSTART_QUERIES),
)