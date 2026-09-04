---
title: Weather provider contract adapter
description: Run CPU-only Aurora, Earth-2 FCN, and MAI Weather contracts over operational NWP data
ms.date: 2026-09-02
ms.topic: reference
---

## Overview

This CPU-only FastAPI service implements the scoring contracts expected for
Microsoft Aurora, NVIDIA Earth-2 FCN, and MAI Weather. It does not run those
native models. The configured contract routes use operational NWP fields from
Open-Meteo:

* `aurora-1.x` contract: ECMWF IFS 0.25
* `earth2-fcn` contract: NOAA GFS
* `mai-weather-1.x` contract: DWD ICON

When Open-Meteo or a requested field is unavailable, the response identifies
which variables used deterministic synthetic fallback values. Do not present
adapter results as native Aurora, Earth-2, or MAI Weather inference.

## Endpoints

| Method | Path                 | Mimics                          |
|--------|----------------------|---------------------------------|
| GET    | `/health`            | liveness                        |
| GET    | `/info`              | model card                      |
| POST   | `/aurora/score`      | Aurora contract over ECMWF IFS  |
| POST   | `/earth2/fcn/score`  | Earth-2 contract over NOAA GFS  |
| POST   | `/mai-weather/score` | MAI contract over DWD ICON      |

### Request

```json
{
  "lat": 38.9,
  "lon": -77.0,
  "lead_hours": 72,
  "variables": ["t2m", "precip", "u10", "v10"],
  "grid_size": 8
}
```

### Response (FCN)

```json
{
  "model": "earth2-fcn",
  "issued_at": "2026-05-27T12:00:00Z",
  "valid_at":  "2026-05-30T12:00:00Z",
  "lead_hours": 72,
  "grid": { "lat": [...], "lon": [...] },
  "variables": { "t2m": [[...]], "precip": [[...]] },
  "units": { "t2m": "K", "precip": "mm/hr" },
  "stub": true,
  "provider_contract": "earth2-fcn",
  "native_model_inference": false,
  "source": "NOAA GFS",
  "real_variables": ["precip", "t2m"],
  "synthetic_fallback_variables": [],
  "data_source_note": "earth2-fcn contract backed by NOAA GFS via Open-Meteo; this is not native model inference"
}
```

Precipitation values are clamped to zero or greater after spatial perturbation.
The normalized Forecast dossier preserves units and all provenance fields.

Aurora additionally returns `cyclone_tracks` when `"cyclone"` is included
in `variables`.

## Configure authentication

If env `STUB_API_KEY` is set, requests must send
`Authorization: Bearer <STUB_API_KEY>`. Unset = open (local dev only).

## Run locally

```powershell
uv run --with-requirements requirements.txt uvicorn app:app --reload --port 8080
```

## Run in Docker

```powershell
docker build -t weather-stub .
docker run -p 8080:8080 -e STUB_API_KEY=dev weather-stub
```

## Swap to a native model endpoint

Deploy the native model endpoints and point `AURORA_ENDPOINT_URL`,
`EARTH2_FCN_ENDPOINT_URL`, or `MAI_WEATHER_ENDPOINT_URL` at them. Native
endpoints must omit the adapter marker or return
`native_model_inference: true`. The request and response shape remains the
same, so the Forecast Agent does not require code changes.
