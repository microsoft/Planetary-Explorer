"""Deterministic summaries for STAC collection asset inspection."""

from __future__ import annotations

import math
import re
from typing import Any


_HLS_FIRE_ASSETS = ("B12", "B8A", "B04")
_FIRE_ASSET_LABELS = {
    "B12": "SWIR2",
    "B8A": "narrow NIR",
    "B04": "red",
}


def apply_collection_inspection_overrides(
    *,
    stac_params: dict[str, Any],
    collection_id: str,
    pin: dict[str, Any] | None,
    radius_miles: float = 5.0,
) -> dict[str, Any]:
    """Apply collection and pin invariants to translated STAC parameters."""
    overridden = dict(stac_params)
    overridden.pop("error", None)
    overridden["collections"] = [collection_id]

    if not isinstance(pin, dict):
        return overridden
    try:
        latitude = float(pin["lat"])
        longitude = float(pin["lng"])
    except (KeyError, TypeError, ValueError):
        return overridden

    radius_km = radius_miles * 1.60934
    latitude_offset = radius_km / 111.0
    longitude_scale = max(abs(math.cos(math.radians(latitude))), 1e-6)
    longitude_offset = radius_km / (111.0 * longitude_scale)
    overridden["bbox"] = [
        longitude - longitude_offset,
        latitude - latitude_offset,
        longitude + longitude_offset,
        latitude + latitude_offset,
    ]
    overridden["location_name"] = f"Pinned location ({latitude:.4f}, {longitude:.4f})"
    return overridden


def _asset_sort_key(asset_key: str) -> tuple[int, int, str]:
    band_match = re.fullmatch(r"B(\d+)([A-Z]?)", asset_key, re.IGNORECASE)
    if band_match:
        return (0, int(band_match.group(1)), band_match.group(2).casefold())
    return (1, 0, asset_key.casefold())


def build_collection_asset_inspection_summary(
    *,
    features: list[dict[str, Any]],
    collection_id: str,
    render_assets: list[str] | None,
    render_summary: str,
    stac_mode: str | None,
) -> str:
    """Describe assets from returned items after a collection is rendered."""
    normalized_collection = collection_id.casefold()
    matching_features = [
        feature
        for feature in features
        if str(feature.get("collection") or "").casefold() == normalized_collection
    ]
    resolved_collection = collection_id
    if not matching_features:
        feature_collections = list(
            dict.fromkeys(
                str(feature.get("collection"))
                for feature in features
                if feature.get("collection")
            )
        )
        if len(feature_collections) == 1:
            resolved_collection = feature_collections[0]
            matching_features = [
                feature
                for feature in features
                if str(feature.get("collection")) == resolved_collection
            ]
    if not matching_features:
        return render_summary

    asset_keys = sorted(
        {
            str(asset_key)
            for feature in matching_features
            for asset_key in (feature.get("assets") or {})
        },
        key=_asset_sort_key,
    )
    first_feature = matching_features[0]
    scene_id = str(first_feature.get("id") or "unknown")
    properties = first_feature.get("properties") or {}
    scene_datetime = properties.get("datetime") or properties.get("start_datetime")
    scene_date = str(scene_datetime)[:10] if scene_datetime else "date unavailable"

    lines = [render_summary, "", "**Available assets**"]
    if asset_keys:
        lines.append(f"- {', '.join(f'`{key}`' for key in asset_keys)}")
    else:
        lines.append("- The returned item does not advertise any assets.")

    available_assets = set(asset_keys)
    active_fire_assets = [
        asset for asset in (render_assets or []) if asset in available_assets
    ]
    available_fire_assets = [
        asset for asset in _HLS_FIRE_ASSETS if asset in available_assets
    ]
    if active_fire_assets or len(available_fire_assets) == len(_HLS_FIRE_ASSETS):
        fire_assets = active_fire_assets or available_fire_assets
        fire_labels = " / ".join(
            f"`{asset}` ({_FIRE_ASSET_LABELS.get(asset, 'spectral band')})"
            for asset in fire_assets
        )
        fire_status = "Active map render" if active_fire_assets else "Available recipe"
        lines.extend(["", "**Fire composite**", f"- {fire_status}: {fire_labels}."])

    collection_label = f"`{resolved_collection}`"
    if resolved_collection.casefold() != normalized_collection:
        collection_label += f" (requested as `{collection_id}`)"

    lines.extend(
        [
            "",
            "**Scene**",
            f"- `{scene_id}` acquired {scene_date}; "
            f"{len(matching_features)} matching item(s) inspected.",
            "",
            "**Data source:** "
            f"{'MPC Pro' if (stac_mode or '').casefold() == 'pro' else 'Public Planetary Computer'} "
            f"- {collection_label}",
        ]
    )
    return "\n".join(line for line in lines if line is not None)
