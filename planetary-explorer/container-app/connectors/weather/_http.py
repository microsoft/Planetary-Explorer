"""Shared HTTP client logic for stub / NIM-shaped scoring endpoints."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import aiohttp

from .provider import (
    Capability,
    ForecastBundle,
    ForecastQuery,
    HealthStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = float(os.getenv("WEATHER_PROVIDER_TIMEOUT_S", "30"))
_DEFAULT_ATTEMPTS = max(1, int(os.getenv("WEATHER_PROVIDER_ATTEMPTS", "2")))
_DEFAULT_RETRY_DELAY_S = max(
    0.0,
    float(os.getenv("WEATHER_PROVIDER_RETRY_DELAY_S", "1")),
)


async def _post_json_with_cold_start_retry(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """POST JSON, retrying only transport failures caused by cold starts."""
    for attempt in range(1, _DEFAULT_ATTEMPTS + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(
                            f"scoring endpoint returned {resp.status}: {text[:200]}"
                        )
                    return await resp.json()
        except (aiohttp.ClientConnectionError, TimeoutError) as exc:
            if attempt >= _DEFAULT_ATTEMPTS:
                raise
            logger.info(
                "weather provider transport attempt %d/%d failed during "
                "activation (%s); retrying",
                attempt,
                _DEFAULT_ATTEMPTS,
                type(exc).__name__,
            )
            if _DEFAULT_RETRY_DELAY_S:
                await asyncio.sleep(_DEFAULT_RETRY_DELAY_S)

    raise RuntimeError("weather provider request exhausted without a result")


async def call_score_endpoint(
    *,
    endpoint_url: str,
    score_path: str,
    api_key: str | None,
    query: ForecastQuery,
    provider_id: str,
    vendor: str,
    capabilities: tuple[Capability, ...],
    extra_response_keys: tuple[str, ...] = (),
) -> ForecastBundle:
    """POST a ForecastQuery to a stub-or-NIM-shaped endpoint, parse result."""
    url = endpoint_url.rstrip("/") + score_path
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "lat": query.lat,
        "lon": query.lon,
        "lead_hours": query.lead_hours,
        "variables": list(query.variables),
        "grid_size": query.grid_size,
    }

    started = time.perf_counter()
    try:
        body = await _post_json_with_cold_start_retry(
            url=url,
            headers=headers,
            payload=payload,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"{provider_id} {exc}") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)

    extras: dict[str, Any] = {}
    provenance_keys = (
        "source",
        "data_source_note",
        "provider_contract",
        "native_model_inference",
        "real_variables",
        "synthetic_fallback_variables",
    )
    for k in (*provenance_keys, *extra_response_keys):
        if k in body:
            extras[k] = body[k]
    extras.setdefault("source", provider_id)
    extras.setdefault("native_model_inference", not bool(body.get("stub", False)))

    return ForecastBundle(
        provider_id=provider_id,
        vendor=vendor,
        issued_at=body.get("issued_at", ""),
        valid_at=body.get("valid_at", ""),
        lead_hours=int(body.get("lead_hours", query.lead_hours)),
        grid=body.get("grid", {"lat": [], "lon": []}),
        variables=body.get("variables", {}),
        units=body.get("units", {}),
        capabilities=capabilities,
        extras=extras,
        stub=bool(body.get("stub", False)),
        latency_ms=latency_ms,
    )


async def call_health(endpoint_url: str, api_key: str | None, provider_id: str) -> HealthStatus:
    url = endpoint_url.rstrip("/") + "/health"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                ok = resp.status == 200
                detail = await resp.text() if not ok else "ok"
                return HealthStatus(
                    provider_id=provider_id,
                    healthy=ok,
                    detail=detail[:200],
                    endpoint=endpoint_url,
                )
    except Exception as exc:  # noqa: BLE001
        return HealthStatus(
            provider_id=provider_id,
            healthy=False,
            detail=f"unreachable: {exc}",
            endpoint=endpoint_url,
        )
