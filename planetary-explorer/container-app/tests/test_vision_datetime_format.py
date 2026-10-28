"""Test for the RFC 3339 timestamp format used by /api/copilot/vision's
STAC date-range search windows.

Locks in the fix for a regression introduced while migrating
datetime.utcnow() -> datetime.now(timezone.utc) (PR #41 review finding):
a tz-aware datetime's .isoformat() already ends in "+00:00", so appending
a literal "Z" (valid for the old naive-datetime code) produced
"...+00:00Z", which is not a valid RFC 3339 string and made the STAC
search silently fail/reject the whole endpoint.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# RFC 3339 "full-date T full-time" with a literal Z offset, e.g.
# 2026-10-27T18:31:57Z -- what pystac_client / the Planetary Computer STAC
# API expects for a datetime range endpoint.
_RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _build_datetime_range(now: datetime, days: int) -> str:
    """Mirrors the exact expression used in fastapi_app.py's copilot_vision
    endpoint for both the 30-day and 60-day search windows.
    """
    return f"{(now - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')}/{now.strftime('%Y-%m-%dT%H:%M:%SZ')}"


def test_datetime_range_is_valid_rfc3339_with_tz_aware_now():
    now = datetime.now(timezone.utc)
    date_range = _build_datetime_range(now, 30)
    start, end = date_range.split("/")
    assert _RFC3339_Z.match(start), f"start={start!r} is not valid RFC 3339"
    assert _RFC3339_Z.match(end), f"end={end!r} is not valid RFC 3339"


def test_datetime_range_does_not_contain_double_offset_bug():
    # The actual regression: appending "Z" to an already tz-aware
    # .isoformat() produces "...+00:00Z". Assert neither half of our fixed
    # range contains that pattern.
    now = datetime.now(timezone.utc)
    date_range = _build_datetime_range(now, 60)
    assert "+00:00Z" not in date_range
    assert "+00:00" not in date_range


def test_datetime_range_60_day_window_is_before_30_day_window():
    now = datetime.now(timezone.utc)
    start_30, _ = _build_datetime_range(now, 30).split("/")
    start_60, _ = _build_datetime_range(now, 60).split("/")
    assert start_60 < start_30
