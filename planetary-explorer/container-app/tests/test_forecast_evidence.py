"""Tests for Forecast physical constraints and provenance."""

from __future__ import annotations

from agents.forecast.ensemble import build_dossier
from agents.forecast.messages import ForecastAgentQuery, ProviderResult
from connectors.weather.provider import ForecastBundle


def _adapter_bundle() -> ForecastBundle:
    return ForecastBundle(
        provider_id="aurora-1.x",
        vendor="Microsoft",
        issued_at="2026-09-02T00:00:00Z",
        valid_at="2026-09-03T00:00:00Z",
        lead_hours=24,
        grid={"lat": [45.0], "lon": [-63.0]},
        variables={"precip": [[0.0]]},
        units={"precip": "mm/hr"},
        extras={
            "source": "ECMWF IFS 0.25",
            "native_model_inference": False,
            "synthetic_fallback_variables": [],
        },
        stub=True,
    )


def test_given_nwp_adapter_when_building_dossier_then_provenance_is_explicit() -> None:
    # Arrange
    query = ForecastAgentQuery(lat=45.0, lon=-63.0, lead_hours=24)
    result = ProviderResult(
        provider_id="aurora-1.x",
        vendor="Microsoft",
        bundle=_adapter_bundle(),
    )

    # Act
    dossier = build_dossier(query, [result])

    # Assert
    assert dossier.forecasts[0]["extras"]["source"] == "ECMWF IFS 0.25"
    assert "not native Aurora or Earth-2 inference" in dossier.note


def test_given_precipitation_when_summarizing_then_unit_is_preserved() -> None:
    # Arrange
    query = ForecastAgentQuery(lat=45.0, lon=-63.0, lead_hours=24)
    result = ProviderResult(
        provider_id="aurora-1.x",
        vendor="Microsoft",
        bundle=_adapter_bundle(),
    )

    # Act
    dossier = build_dossier(query, [result])

    # Assert
    assert dossier.ensemble_summary["variables"]["precip"]["unit"] == "mm/hr"


def test_given_mixed_units_when_summarizing_then_arithmetic_is_suppressed() -> None:
    query = ForecastAgentQuery(lat=45.0, lon=-63.0, lead_hours=24)
    kelvin = _adapter_bundle()
    kelvin.variables = {"t2m": [[300.0]]}
    kelvin.units = {"t2m": "K"}
    celsius = _adapter_bundle()
    celsius.provider_id = "earth2-fcn"
    celsius.variables = {"t2m": [[20.0]]}
    celsius.units = {"t2m": "C"}

    dossier = build_dossier(
        query,
        [
            ProviderResult(
                provider_id=kelvin.provider_id, vendor=kelvin.vendor, bundle=kelvin
            ),
            ProviderResult(
                provider_id=celsius.provider_id, vendor=celsius.vendor, bundle=celsius
            ),
        ],
    )

    summary = dossier.ensemble_summary["variables"]["t2m"]
    assert summary == {
        "error": "mixed_units",
        "units": ["C", "K"],
        "samples": 2,
    }
    assert "mean" not in summary
