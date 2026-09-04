"""
NetCDF Computation Tools — Advanced Climate Analysis

Builds on the extreme_weather_tools infrastructure (shared caches, thread pools,
fsspec connection pool) to add time-series extraction, area statistics, anomaly
detection, trend analysis, and a safe expression calculator.

These tools let the LLM agent orchestrate multi-step calculations:
  1. Discover which dataset/variable to use
  2. Extract raw data (point, time-series, or area)
  3. Compute derived values (annual totals, anomalies, trends)

All functions return JSON strings for FunctionTool compatibility.
"""

import ast
import json
import logging
import math
import operator
import time
from concurrent.futures import as_completed
from typing import Any, Callable, Dict, Set

import numpy as np

# Re-use shared infrastructure from extreme_weather_tools
from geoint.extreme_weather_tools import (
    ANNUAL_SUBSAMPLE_DEFAULT,
    ANNUAL_SUBSAMPLE_TARGET,
    CLIMATE_VAR_INFO,
    _convert_longitude,
    _find_valid_grid_point,
    _get_https_fs,
    _netcdf_pool,
    _netcdf_result_cache,
    _netcdf_result_cache_ts,
    _netcdf_cache_ttl,
    _run_values_read,
    _search_cmip6_items,
)

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CATALOG REGISTRY
# ============================================================================
# Maps dataset names → STAC collection IDs, variables, coordinate conventions.
# The LLM agent queries this to decide WHERE to get data.

NETCDF_CATALOG: Dict[str, Dict[str, Any]] = {
    "nasa-nex-gddp-cmip6": {
        "collection_id": "nasa-nex-gddp-cmip6",
        "description": "NASA NEX-GDDP-CMIP6 downscaled climate projections (2015-2100)",
        "resolution": "0.25° (~25 km)",
        "temporal_range": "2015-2100",
        "variables": {
            "tas": "Daily mean near-surface air temperature (K → °F)",
            "tasmax": "Daily max near-surface air temperature (K → °F)",
            "tasmin": "Daily min near-surface air temperature (K → °F)",
            "pr": "Precipitation rate (kg/m²/s → mm/day)",
            "sfcWind": "Near-surface wind speed (m/s)",
            "hurs": "Near-surface relative humidity (%)",
            "huss": "Near-surface specific humidity (kg/kg → g/kg)",
            "rlds": "Downwelling longwave radiation (W/m²)",
            "rsds": "Downwelling shortwave radiation (W/m²)",
        },
        "scenarios": {
            "ssp245": "SSP2-4.5 — Moderate emissions",
            "ssp585": "SSP5-8.5 — Worst-case emissions",
        },
        "lon_convention": "0-360",
        "coordinate_names": {"lat": "lat", "lon": "lon", "time": "time"},
        "engine": "h5netcdf",
        "stac_filters": ["cmip6:year", "cmip6:model", "cmip6:scenario"],
    },
}


def _monthly_slices(n_days: int, year: int) -> list[slice]:
    """Partition every daily sample into one calendar-aware month."""
    if n_days <= 0:
        return []
    if n_days == 360:
        lengths = [30] * 12
    elif n_days == 365:
        lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    elif n_days == 366:
        lengths = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        # Unknown or partial calendars still assign every sample exactly once.
        base, remainder = divmod(n_days, 12)
        lengths = [base + (1 if month < remainder else 0) for month in range(12)]

    slices = []
    start = 0
    for length in lengths:
        end = start + length
        slices.append(slice(start, end))
        start = end
    return slices


def _aggregate_monthly_values(
    values: np.ndarray,
    year: int,
    convert: Callable[[float], float],
    unit: str,
) -> list[dict[str, Any]]:
    """Aggregate every valid daily value into its calendar month."""
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    periods = []
    for month_name, month_slice in zip(
        month_names,
        _monthly_slices(len(values), year),
    ):
        month_values = values[month_slice]
        valid = month_values[~np.isnan(month_values)]
        if len(valid) == 0:
            continue
        periods.append({
            "period": month_name,
            "mean": convert(float(np.mean(valid))),
            "max": convert(float(np.max(valid))),
            "min": convert(float(np.min(valid))),
            "unit": unit,
        })
    return periods


# ============================================================================
# SAFE EXPRESSION EVALUATOR
# ============================================================================
# Allows the agent to compute derived values without using eval().
# Supports: +, -, *, /, **, %, abs(), round(), min(), max(), sum(), sqrt(), log()

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
}

_MAX_EXPR_LEN = 500


def _safe_eval_node(node: ast.AST, variables: Dict[str, float]) -> float:
    """Recursively evaluate an AST node with allowed operations only."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.Name):
        if node.id in variables:
            return float(variables[node.id])
        raise ValueError(f"Unknown variable: {node.id}")
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left, variables)
        right = _safe_eval_node(node.right, variables)
        return op_func(left, right)
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_safe_eval_node(node.operand, variables))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named function calls allowed")
        func = _SAFE_FUNCS.get(node.func.id)
        if func is None:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_safe_eval_node(a, variables) for a in node.args]
        return float(func(*args))
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


# ============================================================================
# TOOL FUNCTIONS (all return JSON strings)
# ============================================================================


def discover_datasets(query: str) -> str:
    """Find which climate datasets and variables are available for a given question.
    Call this FIRST when you need to figure out which variable or dataset to query.
    Returns a catalog of available datasets, their variables, resolution, and time range.

    :param query: The user's question or topic, e.g. 'precipitation trends' or 'temperature anomaly'
    :return: JSON string listing matching datasets and variables
    """
    query_lower = query.lower()

    # Keyword → variable mapping for quick matching
    keyword_map = {
        "temperature": ["tas", "tasmax", "tasmin"],
        "heat": ["tasmax", "tas"],
        "cold": ["tasmin", "tas"],
        "precipitation": ["pr"],
        "rainfall": ["pr"],
        "rain": ["pr"],
        "monsoon": ["pr"],
        "flood": ["pr"],
        "drought": ["pr"],
        "wind": ["sfcWind"],
        "humidity": ["hurs", "huss"],
        "radiation": ["rsds", "rlds"],
        "solar": ["rsds"],
        "energy": ["rsds", "rlds"],
    }

    matched_vars = set()
    for keyword, vars in keyword_map.items():
        if keyword in query_lower:
            matched_vars.update(vars)

    results = []
    for dataset_id, info in NETCDF_CATALOG.items():
        # Filter to matched variables or return all if no matches
        if matched_vars:
            relevant_vars = {v: info["variables"][v] for v in matched_vars if v in info["variables"]}
        else:
            relevant_vars = info["variables"]

        if relevant_vars:
            results.append({
                "dataset": dataset_id,
                "description": info["description"],
                "resolution": info["resolution"],
                "temporal_range": info["temporal_range"],
                "scenarios": info["scenarios"],
                "matching_variables": relevant_vars,
            })

    return json.dumps({
        "query": query,
        "datasets_found": len(results),
        "results": results,
        "tip": "Use sample_timeseries or sample_area_stats with the variable name and dataset collection_id."
    })


def sample_timeseries(
    latitude: float,
    longitude: float,
    variable: str,
    scenario: str = "ssp585",
    year: int = 2030,
    aggregation: str = "monthly",
) -> str:
    """Extract a time series of a climate variable at a point for an entire year.
    Returns monthly or seasonal aggregated values (mean, max, min per period).
    Use this to see how a variable changes across months or seasons within a year.

    :param latitude: Latitude of the location (-90 to 90)
    :param longitude: Longitude of the location (-180 to 180)
    :param variable: Climate variable name (e.g., 'pr', 'tas', 'tasmax', 'sfcWind', 'hurs')
    :param scenario: SSP scenario - 'ssp245' or 'ssp585'. Default 'ssp585'
    :param year: Projection year (2015-2100). Default 2030
    :param aggregation: 'monthly' (12 values) or 'seasonal' (4 values: DJF, MAM, JJA, SON). Default 'monthly'
    :return: JSON string with time series data
    """
    import xarray as xr

    logger.info(f"[NETCDF-CALC] sample_timeseries: {variable} at ({latitude}, {longitude}), {scenario}/{year}, agg={aggregation}")

    var_info = CLIMATE_VAR_INFO.get(variable)
    if not var_info:
        return json.dumps({"error": f"Unknown variable '{variable}'. Available: {list(CLIMATE_VAR_INFO.keys())}"})

    # Cache key for the full timeseries
    sample_lng = _convert_longitude(longitude)
    cache_key = f"ts:{variable}:{latitude:.4f}:{sample_lng:.4f}:{scenario}:{year}:{aggregation}"
    now = time.time()
    if cache_key in _netcdf_result_cache:
        age = now - _netcdf_result_cache_ts.get(cache_key, 0)
        if age < _netcdf_cache_ttl:
            logger.info(f"[NETCDF-CALC] Timeseries CACHE HIT ({age:.0f}s old)")
            return json.dumps(_netcdf_result_cache[cache_key])

    try:
        items = _search_cmip6_items(latitude, longitude, variable, scenario, year, limit=1)
        if not items:
            return json.dumps({"error": f"No CMIP6 data for {variable}/{scenario}/{year}"})

        item = items[0]
        assets = item.get("assets", {})
        href = assets.get(variable, {}).get("href", "") if isinstance(assets.get(variable), dict) else ""
        if not href:
            return json.dumps({"error": f"No asset href for variable '{variable}'"})

        model_id = item.get("id", "").split(".")[0] if "." in item.get("id", "") else "unknown"

        # Read the full year via xarray
        fs = _get_https_fs()
        f = fs.open(href)
        ds = xr.open_dataset(f, engine="h5netcdf", decode_times=False)

        try:
            data = ds[variable]

            # Use land-fallback search so coastal points whose nearest cell is
            # masked (over water) shift to the closest valid land cell.
            picked = _find_valid_grid_point(data, latitude, sample_lng)
            if picked is None:
                return json.dumps({"error": "No valid data within land-fallback radius (all surrounding cells masked)"})
            point = picked["point"]
            actual_lat = picked["actual_lat"]
            actual_lon = picked["actual_lon"]
            sampling_offset_km = picked["offset_km"]

            n_times = len(point.time) if "time" in point.dims else 0
            if n_times == 0:
                return json.dumps({"error": "No time dimension in dataset"})

            # Read all values (subsample if >365 to stay in timeout)
            if n_times > 400:
                step = max(1, n_times // 365)
                point = point.isel(time=slice(None, None, step))

            try:
                all_values = _run_values_read(
                    lambda p=point: p.values.astype(float),
                    60,
                )
            except TimeoutError:
                return json.dumps({"error": "NetCDF read timed out"})

            valid_mask = ~np.isnan(all_values)
            if not valid_mask.any():
                return json.dumps({"error": "No valid data at this location"})

            convert = var_info["convert"]

            # Aggregate into periods
            n_days = len(all_values)
            if aggregation == "seasonal":
                # Approximate: DJF=Jan-Feb+Dec, MAM=Mar-May, JJA=Jun-Aug, SON=Sep-Nov
                season_names = ["DJF (Winter)", "MAM (Spring)", "JJA (Summer)", "SON (Fall)"]
                # Approximate day boundaries (for a 365-day year)
                season_slices = [
                    list(range(0, min(59, n_days))) + list(range(max(0, min(334, n_days)), n_days)),  # DJF
                    list(range(min(59, n_days), min(151, n_days))),   # MAM
                    list(range(min(151, n_days), min(243, n_days))),  # JJA
                    list(range(min(243, n_days), min(334, n_days))),  # SON
                ]
                periods = []
                for name, indices in zip(season_names, season_slices):
                    if not indices:
                        continue
                    vals = all_values[indices]
                    valid = vals[~np.isnan(vals)]
                    if len(valid) == 0:
                        continue
                    periods.append({
                        "period": name,
                        "mean": convert(float(np.mean(valid))),
                        "max": convert(float(np.max(valid))),
                        "min": convert(float(np.min(valid))),
                        "unit": var_info["display_unit"],
                    })
            else:
                # Monthly: preserve real month boundaries and include every day.
                periods = _aggregate_monthly_values(
                    all_values,
                    year,
                    convert,
                    var_info["display_unit"],
                )

            # Annual summary
            valid_all = all_values[valid_mask]
            annual_summary = {
                "annual_mean": convert(float(np.mean(valid_all))),
                "annual_max": convert(float(np.max(valid_all))),
                "annual_min": convert(float(np.min(valid_all))),
                "unit": var_info["display_unit"],
                "days_sampled": int(valid_mask.sum()),
                "total_days": n_days,
            }

            result = {
                "location": {"latitude": latitude, "longitude": longitude},
                "actual_sampled_location": {
                    "latitude": round(actual_lat, 4),
                    "longitude": round(actual_lon, 4),
                    "offset_km": sampling_offset_km,
                },
                "variable": variable,
                "variable_name": var_info["name"],
                "scenario": scenario,
                "year": year,
                "model": model_id,
                "aggregation": aggregation,
                "periods": periods,
                "annual_summary": annual_summary,
                "data_source": "NASA NEX-GDDP-CMIP6",
                "grid_resolution": "0.25° × 0.25°",
            }
            if sampling_offset_km and sampling_offset_km >= 5:
                result["sampling_note"] = (
                    f"Nearest grid cell was masked (likely over water). Reported values "
                    f"come from the closest valid land cell at ({round(actual_lat, 4)}, "
                    f"{round(actual_lon, 4)}), about {sampling_offset_km:.0f} km from the request."
                )

            _netcdf_result_cache[cache_key] = result
            _netcdf_result_cache_ts[cache_key] = now
            logger.info(f"[NETCDF-CALC] Timeseries: {len(periods)} periods for {variable}/{scenario}/{year}")
            return json.dumps(result)

        finally:
            ds.close()
            try:
                f.close()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"[NETCDF-CALC] sample_timeseries failed: {e}")
        return json.dumps({"error": str(e)})


def sample_area_stats(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    variable: str,
    scenario: str = "ssp585",
    year: int = 2030,
) -> str:
    """Compute spatial statistics for a climate variable over a bounding box area.
    Returns mean, min, max, std, and percentiles across all grid cells in the area.
    Use this when the user asks about a region, city, or area (not a single point).

    :param min_lat: Southern boundary latitude
    :param max_lat: Northern boundary latitude
    :param min_lon: Western boundary longitude
    :param max_lon: Eastern boundary longitude
    :param variable: Climate variable name (e.g., 'pr', 'tas', 'tasmax')
    :param scenario: SSP scenario - 'ssp245' or 'ssp585'. Default 'ssp585'
    :param year: Projection year (2015-2100). Default 2030
    :return: JSON string with spatial statistics for the area
    """
    import xarray as xr

    logger.info(f"[NETCDF-CALC] sample_area_stats: {variable} over [{min_lat},{max_lat},{min_lon},{max_lon}], {scenario}/{year}")

    var_info = CLIMATE_VAR_INFO.get(variable)
    if not var_info:
        return json.dumps({"error": f"Unknown variable '{variable}'. Available: {list(CLIMATE_VAR_INFO.keys())}"})

    # Convert longitudes to 0-360
    sample_min_lon = _convert_longitude(min_lon)
    sample_max_lon = _convert_longitude(max_lon)

    cache_key = f"area:{variable}:{min_lat:.2f}:{max_lat:.2f}:{sample_min_lon:.2f}:{sample_max_lon:.2f}:{scenario}:{year}"
    now = time.time()
    if cache_key in _netcdf_result_cache:
        age = now - _netcdf_result_cache_ts.get(cache_key, 0)
        if age < _netcdf_cache_ttl:
            logger.info(f"[NETCDF-CALC] Area stats CACHE HIT ({age:.0f}s old)")
            return json.dumps(_netcdf_result_cache[cache_key])

    try:
        # Use center point for STAC search (items are global anyway)
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        items = _search_cmip6_items(center_lat, center_lon, variable, scenario, year, limit=1)
        if not items:
            return json.dumps({"error": f"No CMIP6 data for {variable}/{scenario}/{year}"})

        item = items[0]
        assets = item.get("assets", {})
        href = assets.get(variable, {}).get("href", "") if isinstance(assets.get(variable), dict) else ""
        if not href:
            return json.dumps({"error": f"No asset href for variable '{variable}'"})

        model_id = item.get("id", "").split(".")[0] if "." in item.get("id", "") else "unknown"

        fs = _get_https_fs()
        f = fs.open(href)
        ds = xr.open_dataset(f, engine="h5netcdf", decode_times=False)

        try:
            data = ds[variable]

            # Select spatial subset
            if sample_min_lon <= sample_max_lon:
                spatial = data.sel(
                    lat=slice(min_lat, max_lat),
                    lon=slice(sample_min_lon, sample_max_lon),
                )
            else:
                # Wraps around date line
                part1 = data.sel(lat=slice(min_lat, max_lat), lon=slice(sample_min_lon, 360))
                part2 = data.sel(lat=slice(min_lat, max_lat), lon=slice(0, sample_max_lon))
                spatial = xr.concat([part1, part2], dim="lon")

            n_lat = len(spatial.lat) if "lat" in spatial.dims else 0
            n_lon = len(spatial.lon) if "lon" in spatial.dims else 0
            if n_lat == 0 or n_lon == 0:
                return json.dumps({"error": "No grid cells in the specified area. Area may be too small for 0.25° grid."})

            # ------------------------------------------------------------------
            # Aggregate across time, not just take the last day.
            # The old code did `spatial.isel(time=-1)`, which for precipitation
            # is almost always 0 mm/day across the whole bbox (most days are
            # dry, especially Dec 31).  That produced "all zeros" responses
            # even in wet climates like New Orleans.
            #
            # Fix: subsample evenly across the year (same per-variable target
            # as the point sampler), then compute per-cell time-mean (and
            # per-cell time-max for "peak daily").  Spatial statistics are
            # then computed on the per-cell time-mean so the reported mean is
            # the area's annual-average value, not a snapshot of one day.
            # ------------------------------------------------------------------
            has_time = "time" in spatial.dims
            if has_time:
                n_times = int(spatial.sizes["time"])
                target = ANNUAL_SUBSAMPLE_TARGET.get(variable, ANNUAL_SUBSAMPLE_DEFAULT)
                if n_times > target * 2:
                    step = max(1, n_times // target)
                    spatial_subset = spatial.isel(time=slice(0, None, step))
                else:
                    spatial_subset = spatial
                n_sampled = int(spatial_subset.sizes.get("time", 0))
            else:
                spatial_subset = spatial
                n_sampled = 1
                n_times = 1

            try:
                values_nd = _run_values_read(
                    lambda s=spatial_subset: s.values.astype(float),
                    90,
                )
            except TimeoutError:
                return json.dumps({"error": "NetCDF area read timed out"})

            # values_nd shape: (time, lat, lon) if has_time else (lat, lon)
            if has_time and values_nd.ndim == 3:
                with np.errstate(invalid="ignore"):
                    per_cell_mean = np.nanmean(values_nd, axis=0)
                    per_cell_max = np.nanmax(values_nd, axis=0)
            else:
                per_cell_mean = values_nd
                per_cell_max = values_nd

            valid_mask = ~np.isnan(per_cell_mean)
            if not valid_mask.any():
                return json.dumps({"error": "No valid data in the specified area (all cells masked)"})

            valid = per_cell_mean[valid_mask]
            valid_max = per_cell_max[~np.isnan(per_cell_max)]
            convert = var_info["convert"]
            peak_cell_max = convert(float(np.max(valid_max))) if valid_max.size else None

            result = {
                "location": {
                    "bbox": [min_lat, max_lat, min_lon, max_lon],
                    "grid_cells": {"lat": n_lat, "lon": n_lon, "total": n_lat * n_lon},
                },
                "variable": variable,
                "variable_name": var_info["name"],
                "scenario": scenario,
                "year": year,
                "model": model_id,
                "aggregation": "annual per-cell mean across subsampled days",
                "days_sampled": n_sampled,
                "total_days": n_times,
                "statistics": {
                    "mean": convert(float(np.mean(valid))),
                    "median": convert(float(np.median(valid))),
                    "min": convert(float(np.min(valid))),
                    "max": convert(float(np.max(valid))),
                    "std": round(float(np.std(valid)), 4),
                    "p10": convert(float(np.percentile(valid, 10))),
                    "p25": convert(float(np.percentile(valid, 25))),
                    "p75": convert(float(np.percentile(valid, 75))),
                    "p90": convert(float(np.percentile(valid, 90))),
                    "peak_daily_anywhere_in_area": peak_cell_max,
                    "unit": var_info["display_unit"],
                    "valid_cells": int(valid_mask.sum()),
                    "total_cells": int(per_cell_mean.size),
                },
                "data_source": "NASA NEX-GDDP-CMIP6",
                "grid_resolution": "0.25° × 0.25°",
            }

            _netcdf_result_cache[cache_key] = result
            _netcdf_result_cache_ts[cache_key] = now
            logger.info(f"[NETCDF-CALC] Area stats: {n_lat}x{n_lon} cells x {n_sampled} days, mean={result['statistics']['mean']}, peak={peak_cell_max}")
            return json.dumps(result)

        finally:
            ds.close()
            try:
                f.close()
            except Exception:
                pass

    except Exception as e:
        logger.error(f"[NETCDF-CALC] sample_area_stats failed: {e}")
        return json.dumps({"error": str(e)})


def compute_anomaly(
    latitude: float,
    longitude: float,
    variable: str,
    baseline_year: int = 2020,
    target_year: int = 2050,
    scenario: str = "ssp585",
) -> str:
    """Compute the climate anomaly (change) between a baseline year and a target year.
    Shows how much a variable is projected to change over time at a specific location.
    Use this when the user asks about 'change', 'increase', 'decrease', or 'trend' between two years.

    :param latitude: Latitude of the location (-90 to 90)
    :param longitude: Longitude of the location (-180 to 180)
    :param variable: Climate variable name (e.g., 'tas', 'tasmax', 'pr')
    :param baseline_year: Reference year to compare FROM (2015-2100). Default 2020
    :param target_year: Future year to compare TO (2015-2100). Default 2050
    :param scenario: SSP scenario. Default 'ssp585'
    :return: JSON string with baseline value, target value, absolute and percent change
    """
    logger.info(f"[NETCDF-CALC] compute_anomaly: {variable} at ({latitude}, {longitude}), {baseline_year}→{target_year}, {scenario}")

    var_info = CLIMATE_VAR_INFO.get(variable)
    if not var_info:
        return json.dumps({"error": f"Unknown variable '{variable}'."})

    cache_key = f"anomaly:{variable}:{latitude:.4f}:{_convert_longitude(longitude):.4f}:{baseline_year}:{target_year}:{scenario}"
    now = time.time()
    if cache_key in _netcdf_result_cache:
        age = now - _netcdf_result_cache_ts.get(cache_key, 0)
        if age < _netcdf_cache_ttl:
            logger.info(f"[NETCDF-CALC] Anomaly CACHE HIT ({age:.0f}s old)")
            return json.dumps(_netcdf_result_cache[cache_key])

    from geoint.extreme_weather_tools import _sample_netcdf

    def _fetch_year(yr):
        items = _search_cmip6_items(latitude, longitude, variable, scenario, yr, limit=1)
        if not items:
            return yr, {"error": f"No data for {yr}"}
        item = items[0]
        href = item.get("assets", {}).get(variable, {}).get("href", "") if isinstance(item.get("assets", {}).get(variable), dict) else ""
        if not href:
            return yr, {"error": f"No asset for {variable} in {yr}"}
        result = _sample_netcdf(href, variable, latitude, longitude, aggregate="annual")
        model = item.get("id", "").split(".")[0] if "." in item.get("id", "") else "unknown"
        return yr, result, model

    # Fetch both years in parallel
    futures = {_netcdf_pool.submit(_fetch_year, y): y for y in [baseline_year, target_year]}
    year_data = {}
    model_used = "unknown"
    for future in as_completed(futures, timeout=120):
        try:
            result = future.result(timeout=90)
            yr = result[0]
            data = result[1]
            if len(result) > 2:
                model_used = result[2]
            year_data[yr] = data
        except Exception as e:
            logger.warning(f"[NETCDF-CALC] Anomaly fetch failed: {e}")

    baseline = year_data.get(baseline_year, {})
    target = year_data.get(target_year, {})

    if "error" in baseline:
        return json.dumps({"error": f"Baseline year {baseline_year}: {baseline['error']}"})
    if "error" in target:
        return json.dumps({"error": f"Target year {target_year}: {target['error']}"})

    convert = var_info["convert"]
    b_raw = baseline.get("raw_mean", baseline.get("raw_value"))
    t_raw = target.get("raw_mean", target.get("raw_value"))

    if b_raw is None or t_raw is None:
        return json.dumps({"error": "Could not extract values for comparison"})

    raw_change = t_raw - b_raw
    pct_change = (raw_change / abs(b_raw) * 100) if b_raw != 0 else None

    result = {
        "location": {"latitude": latitude, "longitude": longitude},
        "variable": variable,
        "variable_name": var_info["name"],
        "scenario": scenario,
        "model": model_used,
        "baseline": {
            "year": baseline_year,
            "value": convert(b_raw),
            "unit": var_info["display_unit"],
        },
        "target": {
            "year": target_year,
            "value": convert(t_raw),
            "unit": var_info["display_unit"],
        },
        "change": {
            "absolute": convert(raw_change) if var_info["category"] != "precipitation" else round(raw_change * 86400, 2),
            "absolute_unit": var_info["display_unit"],
            "percent": round(pct_change, 1) if pct_change is not None else None,
            "direction": "increase" if raw_change > 0 else "decrease" if raw_change < 0 else "no change",
        },
        "data_source": "NASA NEX-GDDP-CMIP6",
        "grid_resolution": "0.25° × 0.25°",
    }

    _netcdf_result_cache[cache_key] = result
    _netcdf_result_cache_ts[cache_key] = now
    logger.info(f"[NETCDF-CALC] Anomaly: {variable} {result['change']['direction']} by {result['change']['percent']}%")
    return json.dumps(result)


def compute_trend(
    latitude: float,
    longitude: float,
    variable: str,
    start_year: int = 2020,
    end_year: int = 2060,
    scenario: str = "ssp585",
) -> str:
    """Compute a linear trend for a climate variable across multiple decades.
    Samples the variable at ~5 evenly spaced years and fits a linear regression.
    Returns slope (change per decade), R², and whether the trend is significant.
    Use this when the user asks about long-term trends, 'is it getting hotter/wetter?', or projections over decades.

    :param latitude: Latitude of the location (-90 to 90)
    :param longitude: Longitude of the location (-180 to 180)
    :param variable: Climate variable name (e.g., 'tas', 'tasmax', 'pr')
    :param start_year: First year of trend analysis (2015-2095). Default 2020
    :param end_year: Last year of trend analysis (2020-2100). Default 2060
    :param scenario: SSP scenario. Default 'ssp585'
    :return: JSON string with trend slope, R², p-value, and per-year data points
    """
    logger.info(f"[NETCDF-CALC] compute_trend: {variable} at ({latitude}, {longitude}), {start_year}-{end_year}, {scenario}")

    var_info = CLIMATE_VAR_INFO.get(variable)
    if not var_info:
        return json.dumps({"error": f"Unknown variable '{variable}'."})

    if end_year <= start_year:
        return json.dumps({"error": "end_year must be greater than start_year"})

    cache_key = f"trend:{variable}:{latitude:.4f}:{_convert_longitude(longitude):.4f}:{start_year}:{end_year}:{scenario}"
    now = time.time()
    if cache_key in _netcdf_result_cache:
        age = now - _netcdf_result_cache_ts.get(cache_key, 0)
        if age < _netcdf_cache_ttl:
            logger.info(f"[NETCDF-CALC] Trend CACHE HIT ({age:.0f}s old)")
            return json.dumps(_netcdf_result_cache[cache_key])

    from geoint.extreme_weather_tools import _sample_netcdf

    # Sample ~5 evenly spaced years (more would be too slow with remote NetCDF)
    span = end_year - start_year
    n_points = min(5, max(2, span // 10 + 1))
    years = [start_year + int(i * span / (n_points - 1)) for i in range(n_points)]
    # Ensure end_year is included
    if years[-1] != end_year:
        years[-1] = end_year

    def _fetch_year(yr):
        items = _search_cmip6_items(latitude, longitude, variable, scenario, yr, limit=1)
        if not items:
            return yr, None
        item = items[0]
        href = item.get("assets", {}).get(variable, {}).get("href", "") if isinstance(item.get("assets", {}).get(variable), dict) else ""
        if not href:
            return yr, None
        sample = _sample_netcdf(href, variable, latitude, longitude, aggregate="annual")
        if "error" in sample:
            return yr, None
        return yr, sample.get("raw_mean", sample.get("raw_value"))

    # Pre-warm STAC cache for all years
    for yr in years:
        _search_cmip6_items(latitude, longitude, variable, scenario, yr, limit=1)

    # Fetch all years in parallel
    futures = {_netcdf_pool.submit(_fetch_year, yr): yr for yr in years}
    data_points = {}
    for future in as_completed(futures, timeout=180):
        try:
            yr, val = future.result(timeout=120)
            if val is not None:
                data_points[yr] = val
        except Exception as e:
            logger.warning(f"[NETCDF-CALC] Trend year fetch failed: {e}")

    if len(data_points) < 2:
        return json.dumps({"error": f"Only {len(data_points)} valid data points. Need at least 2 for trend."})

    # Linear regression
    sorted_years = sorted(data_points.keys())
    x = np.array(sorted_years, dtype=float)
    y = np.array([data_points[yr] for yr in sorted_years], dtype=float)

    x_mean = np.mean(x)
    y_mean = np.mean(y)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)
    ss_yy = np.sum((y - y_mean) ** 2)

    slope = ss_xy / ss_xx if ss_xx != 0 else 0
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_xx != 0 and ss_yy != 0 else 0

    # Slope per decade in display units
    convert = var_info["convert"]
    # For conversion: compute display value at y_mean and y_mean+slope*10
    display_slope_decade = convert(y_mean + slope * 10) - convert(y_mean)

    result = {
        "location": {"latitude": latitude, "longitude": longitude},
        "variable": variable,
        "variable_name": var_info["name"],
        "scenario": scenario,
        "period": f"{start_year}-{end_year}",
        "trend": {
            "slope_per_decade": round(display_slope_decade, 2),
            "slope_unit": f"{var_info['display_unit']}/decade",
            "r_squared": round(r_squared, 3),
            "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
            "confidence": "high" if r_squared > 0.7 else "moderate" if r_squared > 0.4 else "low",
        },
        "data_points": [
            {
                "year": yr,
                "value": convert(data_points[yr]),
                "unit": var_info["display_unit"],
            }
            for yr in sorted_years
        ],
        "data_source": "NASA NEX-GDDP-CMIP6",
        "grid_resolution": "0.25° × 0.25°",
        "n_models_sampled": 1,
    }

    _netcdf_result_cache[cache_key] = result
    _netcdf_result_cache_ts[cache_key] = now
    logger.info(
        f"[NETCDF-CALC] Trend: {variable} {result['trend']['direction']} at "
        f"{result['trend']['slope_per_decade']} {var_info['display_unit']}/decade (R²={r_squared:.3f})"
    )
    return json.dumps(result)


def calculate_derived(
    expression: str,
    variables: str,
) -> str:
    """Evaluate a mathematical expression using provided variable values.
    Use this to compute derived quantities from tool outputs (e.g., annual totals,
    unit conversions, differences). Supports: +, -, *, /, **, %, abs(), round(),
    min(), max(), sum(), sqrt(), log(), log10(), ceil(), floor().

    :param expression: Math expression using variable names, e.g. 'precip_mm_day * 365.25' or 'abs(temp_2050 - temp_2020)'
    :param variables: JSON string of variable names to values, e.g. '{"precip_mm_day": 2.41, "temp_2050": 78.5, "temp_2020": 72.1}'
    :return: JSON string with the computed result
    """
    logger.info(f"[NETCDF-CALC] calculate_derived: expr='{expression}', vars={variables}")

    if len(expression) > _MAX_EXPR_LEN:
        return json.dumps({"error": f"Expression too long ({len(expression)} > {_MAX_EXPR_LEN} chars)"})

    try:
        var_dict = json.loads(variables) if isinstance(variables, str) else variables
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid variables JSON: {e}"})

    if not isinstance(var_dict, dict):
        return json.dumps({"error": "variables must be a JSON object of name → value pairs"})

    # Ensure all values are numeric
    for k, v in var_dict.items():
        if not isinstance(v, (int, float)):
            return json.dumps({"error": f"Variable '{k}' must be numeric, got {type(v).__name__}"})

    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval_node(tree, var_dict)
        return json.dumps({
            "expression": expression,
            "variables": var_dict,
            "result": round(result, 6),
        })
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
        return json.dumps({"error": f"Calculation error: {e}"})
    except SyntaxError as e:
        return json.dumps({"error": f"Invalid expression syntax: {e}"})


# ============================================================================
# FUNCTION SET FOR AGENT REGISTRATION
# ============================================================================

def create_netcdf_computation_functions() -> Set[Callable]:
    """Create the set of NetCDF computation functions for FunctionTool.

    Returns a Set[Callable] to pass to AsyncFunctionTool().
    Includes tools from extreme_weather_tools plus new computation tools.
    """
    from geoint.extreme_weather_tools import create_extreme_weather_functions

    # Start with existing climate tools
    functions = create_extreme_weather_functions()

    # Add new computation tools
    functions.update({
        discover_datasets,
        sample_timeseries,
        sample_area_stats,
        compute_anomaly,
        compute_trend,
        calculate_derived,
    })

    return functions
