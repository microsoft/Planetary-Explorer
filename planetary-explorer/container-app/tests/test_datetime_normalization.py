"""Unit tests for the STAC datetime normalization helper.

The helper converts the date-only shorthand the semantic translator emits
(``YYYY-MM-DD`` / ``YYYY-MM-DD/YYYY-MM-DD``) into strict RFC3339 before
the query is sent to any STAC endpoint. A single date denotes the whole
calendar day rather than midnight only. Normalizing once at the single STAC
boundary keeps Public Planetary Computer and GeoCatalog working consistently.
"""

from __future__ import annotations

import importlib

import pytest


def _load_app(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://stub")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "stub")
    try:
        return importlib.import_module("fastapi_app")
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"fastapi_app import failed in test env: {exc}")


def _load(monkeypatch):
    return _load_app(monkeypatch)._normalize_stac_datetime


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Date-only range -> RFC3339 start + end-of-day.
        ("2026-05-20/2026-05-21", "2026-05-20T00:00:00Z/2026-05-21T23:59:59Z"),
        # Single date -> RFC3339 full-day interval.
        ("2026-05-20", "2026-05-20T00:00:00Z/2026-05-20T23:59:59Z"),
        ("2026-07-04", "2026-07-04T00:00:00Z/2026-07-04T23:59:59Z"),
        # Already RFC3339 -> unchanged.
        ("2026-05-20T00:00:00Z/2026-05-21T23:59:59Z",
         "2026-05-20T00:00:00Z/2026-05-21T23:59:59Z"),
        # Open upper bound preserved.
        ("2023-01-01/..", "2023-01-01T00:00:00Z/.."),
        # Open lower bound preserved.
        ("../2026-05-21", "../2026-05-21T23:59:59Z"),
        # Mixed (one date-only, one RFC3339).
        ("2026-05-20/2026-05-21T12:00:00Z",
         "2026-05-20T00:00:00Z/2026-05-21T12:00:00Z"),
    ],
)
def test_normalize_stac_datetime_known_shapes(monkeypatch, raw, expected):
    normalize = _load(monkeypatch)
    assert normalize(raw) == expected


@pytest.mark.parametrize("raw", [None, ""])
def test_normalize_stac_datetime_empty_passthrough(monkeypatch, raw):
    normalize = _load(monkeypatch)
    assert normalize(raw) == raw


def test_normalize_stac_datetime_year_only_passthrough(monkeypatch):
    """Year-only ('2026') and month-only ('2026-05') aren't STAC-spec
    range shorthands; pass them through unchanged so the server can
    decide. Most clients don't emit these."""
    normalize = _load(monkeypatch)
    assert normalize("2026") == "2026"
    assert normalize("2026-05") == "2026-05"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "Inspect hls2-s30 assets for 2026-07-04 at this pin",
            "2026-07-04",
        ),
        (
            "Compare imagery from 2026-06-01 to 2026-07-04",
            "2026-06-01/2026-07-04",
        ),
        ("Show imagery for July 2026", "2026-07-01/2026-07-31"),
        ("Show imagery for 2026", "2026-01-01/2026-12-31"),
    ],
)
def test_extract_stac_datetime_fallback_prefers_exact_dates(
    monkeypatch,
    query,
    expected,
):
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app._extract_stac_datetime_fallback(query)

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Show HLS S30 on 2026-07-04", True),
        ("Inspect HLS S30 assets for 2026-07-04 at this pin", True),
        ("Show HLS S30 2026-07-04", True),
        ("Show HLS S30 for the date 2026-07-04", True),
        ("Show HLS S30 around 2026-07-04", False),
        ("Show HLS S30 before 2026-07-04", False),
        ("Compare 2026-06-01 to 2026-07-04", False),
    ],
)
def test_requests_exact_stac_date_known_phrasings(
    monkeypatch,
    query,
    expected,
):
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app._requests_exact_stac_date(query)

    # Assert
    assert result is expected


@pytest.mark.asyncio
async def test_given_exact_date_when_no_results_then_date_is_not_relaxed(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)
    search_calls = []

    async def fake_search(stac_query, *_args, **_kwargs):
        search_calls.append(stac_query)
        return {
            "success": True,
            "results": {"features": [{"id": "substitute-scene"}]},
        }

    monkeypatch.setattr(
        fastapi_app,
        "execute_direct_stac_search",
        fake_search,
    )

    # Act
    result = await fastapi_app.try_alternative_queries(
        original_query="Show HLS S30 on 2026-07-04 at Thunder Bay",
        original_stac_query={
            "collections": ["hls2-s30"],
            "datetime": "2026-07-04T00:00:00Z/2026-07-05T00:00:00Z",
        },
        original_stac_params={},
        translator=None,
        stac_endpoint="planetary_computer",
        requested_bbox=None,
        locked_collection="hls2-s30",
    )

    # Assert
    assert result["success"] is False
    assert search_calls == []


def test_given_static_dem_when_query_mentions_year_then_datetime_fallback_is_skipped(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app._should_apply_stac_datetime_fallback(
        {"collections": ["cop-dem-glo-30"]},
        "Show Copernicus DEM elevation near Calgary for 2026",
    )

    # Assert
    assert result is False


def test_given_dynamic_hls_when_query_mentions_date_then_datetime_fallback_is_used(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app._should_apply_stac_datetime_fallback(
        {"collections": ["hls2-s30"]},
        "Show HLS S30 on 2026-07-04",
    )

    # Assert
    assert result is True


def test_given_translated_date_for_static_dem_when_building_query_then_date_is_removed(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app.build_stac_query(
        {
            "collections": ["cop-dem-glo-30"],
            "datetime": "2026-01-01/2026-12-31",
            "bbox": [-114.32, 50.84, -113.83, 51.21],
        }
    )

    # Assert
    assert "datetime" not in result
    assert "sortby" not in result


def test_given_direct_static_query_when_sanitizing_then_datetime_sort_is_removed(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)

    # Act
    result = fastapi_app._sanitize_static_stac_query(
        {
            "collections": ["cop-dem-glo-30"],
            "datetime": "2026-01-01/2026-12-31",
            "sortby": [
                {"field": "properties.datetime", "direction": "desc"},
                {"field": "id", "direction": "asc"},
            ],
        }
    )

    # Assert
    assert "datetime" not in result
    assert result["sortby"] == [{"field": "id", "direction": "asc"}]


@pytest.mark.asyncio
async def test_given_direct_static_search_without_original_query_then_date_is_removed(
    monkeypatch,
) -> None:
    # Arrange
    fastapi_app = _load_app(monkeypatch)
    sanitized_queries = []
    sanitize = fastapi_app._sanitize_static_stac_query

    def capture(query):
        result = sanitize(query)
        sanitized_queries.append(result)
        return result

    monkeypatch.setattr(fastapi_app, "_sanitize_static_stac_query", capture)
    monkeypatch.setattr(
        fastapi_app,
        "_resolve_stac_endpoint",
        lambda _endpoint: ("", "planetary_computer_pro_unconfigured", True),
    )

    # Act
    await fastapi_app.execute_direct_stac_search(
        {
            "collections": ["cop-dem-glo-30"],
            "datetime": "2026-01-01/2026-12-31",
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        },
        stac_endpoint="planetary_computer_pro",
    )

    # Assert
    assert sanitized_queries == [{"collections": ["cop-dem-glo-30"]}]
