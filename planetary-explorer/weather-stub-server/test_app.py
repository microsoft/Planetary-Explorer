"""Tests for the NWP adapter response contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import app


@pytest.mark.asyncio
async def test_given_zero_precipitation_when_building_response_then_values_are_nonnegative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    issued = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    times = [(issued + timedelta(hours=offset)).isoformat() for offset in range(25)]

    async def open_meteo_response(*_args, **_kwargs):
        return {
            "hourly": {
                "time": times,
                "precipitation": [0.0] * len(times),
            }
        }

    monkeypatch.setattr(app, "_fetch_openmeteo", open_meteo_response)
    request = app.ScoreRequest(
        lat=45.0,
        lon=-63.0,
        lead_hours=24,
        variables=["precip"],
        grid_size=8,
        issued_at=issued.isoformat(),
    )

    # Act
    response = await app._build_response(request, "aurora-1.x")

    # Assert
    assert min(value for row in response["variables"]["precip"] for value in row) == 0.0
    assert response["native_model_inference"] is False
    assert response["source"] == "ECMWF IFS 0.25"
    assert response["stub"] is True
