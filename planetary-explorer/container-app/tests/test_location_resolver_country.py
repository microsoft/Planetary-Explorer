"""Country-routing regressions for the enhanced location resolver."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

import location_resolver
from location_resolver import EnhancedLocationResolver, LocationCache


class _Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self):
        return {
            "results": [
                {
                    "score": 9.8,
                    "entityType": "Municipality",
                    "address": {
                        "municipality": "Regina",
                        "countryCode": "CA",
                        "countrySubdivision": "Saskatchewan",
                        "freeformAddress": "Regina, Saskatchewan",
                    },
                    "viewport": {
                        "topLeftPoint": {"lon": -104.75, "lat": 50.53},
                        "btmRightPoint": {"lon": -104.46, "lat": 50.36},
                    },
                }
            ]
        }


class _Session:
    def __init__(self, captured):
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def get(self, url, *, params, headers):
        self.captured.update({"url": url, "params": params, "headers": headers})
        return _Response()


@pytest.mark.asyncio
async def test_given_canadian_city_when_fuzzy_searching_then_country_filter_is_canada(
    monkeypatch,
) -> None:
    captured = {}
    resolver = object.__new__(EnhancedLocationResolver)
    resolver.logger = logging.getLogger(__name__)
    resolver.azure_maps_key = "test-key"
    resolver.azure_maps_use_managed_identity = False
    resolver._token_provider = None
    resolver.azure_maps_client_id = None
    monkeypatch.setattr(
        location_resolver.aiohttp,
        "ClientSession",
        lambda: _Session(captured),
    )

    bbox = await resolver._azure_maps_fuzzy_search("Regina, Canada")

    assert captured["params"]["countrySet"] == "CA"
    assert captured["params"]["query"] == "Regina, Canada"
    assert bbox == [-104.75, 50.36, -104.46, 50.53]


@pytest.mark.asyncio
async def test_given_generated_city_query_when_fuzzy_searching_then_city_filter_is_kept(
    monkeypatch,
) -> None:
    captured = {}
    resolver = object.__new__(EnhancedLocationResolver)
    resolver.logger = logging.getLogger(__name__)
    resolver.azure_maps_key = "test-key"
    resolver.azure_maps_use_managed_identity = False
    resolver._token_provider = None
    resolver.azure_maps_client_id = None
    monkeypatch.setattr(
        location_resolver.aiohttp,
        "ClientSession",
        lambda: _Session(captured),
    )

    await resolver._azure_maps_fuzzy_search(
        "Regina, Saskatchewan, Canada city",
        "city",
    )

    assert captured["params"]["countrySet"] == "CA"
    assert captured["params"]["entityType"] == "Municipality,PopulatedPlace"


def test_given_qualified_canadian_city_when_preprocessing_then_us_bias_is_omitted() -> None:
    resolver = object.__new__(EnhancedLocationResolver)

    queries = resolver._preprocess_location_query("Regina, Canada", "city")

    assert queries
    assert all("usa" not in query.casefold() for query in queries)
    assert all("united states" not in query.casefold() for query in queries)


@pytest.mark.asyncio
async def test_given_city_viewport_when_resolving_then_small_valid_bbox_is_retained() -> None:
    resolver = object.__new__(EnhancedLocationResolver)
    resolver.logger = logging.getLogger(__name__)
    resolver._azure_maps_fuzzy_search = AsyncMock(
        return_value=[-104.75, 50.36, -104.46, 50.53]
    )
    resolver._azure_maps_with_population_priority = AsyncMock(return_value=None)
    resolver._azure_maps_address_search = AsyncMock(return_value=None)
    resolver._is_azure_maps_configured = lambda: True

    bbox = await resolver._strategy_azure_maps(
        "Regina, Saskatchewan, Canada",
        "region",
    )

    assert bbox == [-104.75, 50.36, -104.46, 50.53]
    resolver._azure_maps_address_search.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("declared_type", ["region", "country"])
async def test_given_qualified_city_when_resolving_variants_then_city_type_is_preserved(
    declared_type,
) -> None:
    resolver = object.__new__(EnhancedLocationResolver)
    resolver.logger = logging.getLogger(__name__)
    resolver.cache = LocationCache()
    resolver._is_azure_maps_configured = lambda: True
    resolver._strategy_azure_maps = AsyncMock(
        return_value=[-104.75, 50.36, -104.46, 50.53]
    )

    bbox = await resolver.resolve_location_to_bbox(
        "Regina, Saskatchewan, Canada",
        declared_type,
    )

    assert bbox == [-104.75, 50.36, -104.46, 50.53]
    assert resolver._strategy_azure_maps.await_args.args[1] == "city"


def test_given_canadian_province_when_normalizing_then_it_remains_administrative() -> None:
    resolver = object.__new__(EnhancedLocationResolver)

    assert resolver._normalize_location_type("Saskatchewan, Canada", "country") == "state"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("location", "expected_bbox"),
    [
        ("Calgary, Alberta, Canada", [-114.32, 50.84, -113.83, 51.21]),
        ("Lake Ontario, Canada", [-79.80, 43.10, -76.00, 44.30]),
        ("Western Canada", [-139.06, 48.30, -101.36, 60.00]),
        ("Lytton, British Columbia, Canada", [-121.65, 50.18, -121.50, 50.28]),
    ],
)
async def test_given_get_started_place_when_resolving_then_stored_bounds_win(
    location,
    expected_bbox,
) -> None:
    # Arrange
    resolver = object.__new__(EnhancedLocationResolver)
    resolver.logger = logging.getLogger(__name__)
    resolver.cache = LocationCache()

    # Act
    bbox = await resolver.resolve_location_to_bbox(location, "region")

    # Assert
    assert bbox == expected_bbox