"""Pure ensemble and dossier helpers for the Forecast Agent MAF workflow."""
from __future__ import annotations

import statistics
from typing import Any

from connectors.weather import ForecastBundle

from .messages import (
    ForecastAgentQuery,
    ForecastDossier,
    ProviderResult,
)


def _grid_center_value(field: list[list[float]]) -> float | None:
    if not field or not field[0]:
        return None
    n = len(field)
    m = len(field[0])
    return float(field[n // 2][m // 2])


def _grid_mean(field: list[list[float]]) -> float | None:
    if not field or not field[0]:
        return None
    vals = [v for row in field for v in row]
    return float(sum(vals) / len(vals)) if vals else None


def _bundle_to_dict(bundle: ForecastBundle) -> dict[str, Any]:
    centers = {v: _grid_center_value(arr) for v, arr in bundle.variables.items()}
    means = {v: _grid_mean(arr) for v, arr in bundle.variables.items()}
    return {
        "provider_id": bundle.provider_id,
        "vendor": bundle.vendor,
        "issued_at": bundle.issued_at,
        "valid_at": bundle.valid_at,
        "lead_hours": bundle.lead_hours,
        "grid": bundle.grid,
        "variables": bundle.variables,
        "units": bundle.units,
        "center_values": centers,
        "area_means": means,
        "extras": bundle.extras,
        "stub": bundle.stub,
        "latency_ms": bundle.latency_ms,
    }


def _ensemble_summary(bundles: list[ForecastBundle]) -> dict[str, Any]:
    """Per-variable center-value mean and spread across providers."""
    if len(bundles) < 1:
        return {}
    by_var: dict[str, list[tuple[float, str | None]]] = {}
    for b in bundles:
        for v, arr in b.variables.items():
            c = _grid_center_value(arr)
            if c is not None:
                by_var.setdefault(v, []).append((c, b.units.get(v)))
    out: dict[str, Any] = {"providers": [b.provider_id for b in bundles], "variables": {}}
    for v, samples in by_var.items():
        if not samples:
            continue
        vals = [value for value, _unit in samples]
        units = {unit for _value, unit in samples if unit}
        missing_units = any(not unit for _value, unit in samples)
        if len(units) != 1 or missing_units:
            out["variables"][v] = {
                "error": "mixed_units",
                "units": sorted(units),
                "samples": len(vals),
            }
            continue
        entry: dict[str, Any] = {
            "mean": round(sum(vals) / len(vals), 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "samples": len(vals),
            "unit": next(iter(units)),
        }
        if len(vals) >= 2:
            entry["stdev"] = round(statistics.stdev(vals), 3)
            entry["spread"] = round(max(vals) - min(vals), 3)
        out["variables"][v] = entry
    return out


def build_dossier(
    query: ForecastAgentQuery,
    results: list[ProviderResult],
    *,
    location: dict[str, Any] | None = None,
    workflow_ms: int | None = None,
    routing: dict[str, Any] | None = None,
) -> ForecastDossier:
    succeeded = [r for r in results if r.bundle is not None]
    failed = [r for r in results if r.bundle is None]
    forecasts = [_bundle_to_dict(r.bundle) for r in succeeded if r.bundle is not None]  # type: ignore[arg-type]
    summary = _ensemble_summary([r.bundle for r in succeeded if r.bundle is not None])  # type: ignore[misc]

    note_parts = []
    adapter_bundles = [
        bundle
        for result in succeeded
        if (bundle := result.bundle)
        and bundle.extras.get("native_model_inference") is False
    ]
    if adapter_bundles:
        sources = sorted(
            {
                str(bundle.extras.get("source"))
                for bundle in adapter_bundles
                if bundle.extras.get("source")
            }
        )
        note_parts.append(
            "Provider contracts are backed by operational NWP adapters, not "
            f"native Aurora or Earth-2 inference. Sources: {', '.join(sources)}."
        )
        if any(bundle.extras.get("synthetic_fallback_variables") for bundle in adapter_bundles):
            note_parts.append(
                "One or more variables used deterministic synthetic fallback values; "
                "inspect each forecast's provenance before use."
            )
    elif any(b.stub for r in succeeded if (b := r.bundle)):
        note_parts.append("One or more providers returned explicitly marked stub output.")
    if failed:
        note_parts.append(
            f"{len(failed)} provider(s) failed; ensemble computed from {len(succeeded)} remaining."
        )

    timing: dict[str, int] = {}
    if workflow_ms is not None:
        timing["workflow_ms"] = workflow_ms
    for r in succeeded:
        if r.latency_ms is not None:
            timing[r.provider_id] = r.latency_ms

    return ForecastDossier(
        input={
            "lat": query.lat,
            "lon": query.lon,
            "lead_hours": query.lead_hours,
            "variables": list(query.variables),
            "grid_size": query.grid_size,
            "requested_providers": list(query.requested_providers),
            "user_query": query.user_query,
            "location_label": query.location_label,
        },
        providers_called=[r.provider_id for r in results],
        providers_succeeded=[r.provider_id for r in succeeded],
        providers_failed=[{"provider_id": r.provider_id, "error": r.error or ""} for r in failed],
        forecasts=forecasts,
        ensemble_summary=summary,
        location=location or {},
        timing_ms=timing,
        routing=routing or {},
        note=" ".join(note_parts),
    )
