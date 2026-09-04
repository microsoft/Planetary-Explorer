"""Tests for the Get Started live scenario verifier."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "verify_get_started_scenarios.py"
SPEC = importlib.util.spec_from_file_location("verify_get_started_scenarios", SCRIPT)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost:8000", True),
        ("http://127.0.0.1:8000", True),
        ("http://[::1]:8000", True),
        ("https://example.test", False),
    ],
)
def test_given_url_when_classifying_then_only_loopback_is_local(url, expected) -> None:
    assert verifier._is_loopback_url(url) is expected


def test_given_failed_scenario_when_reporting_then_exit_is_nonzero() -> None:
    assert (
        verifier._report_exit_code(
            {"results": [{"outcome": "pass"}, {"outcome": "fail"}]}
        )
        == 1
    )
    assert (
        verifier._report_exit_code(
            {"results": [{"outcome": "pass"}, {"outcome": "blocked"}]}
        )
        == 0
    )


def test_given_release_arguments_when_normalizing_then_only_verified_values_remain() -> (
    None
):
    args = verifier.create_parser().parse_args(
        [
            "--api-revision",
            "api--release-1",
            "--api-image-digest",
            "sha256:abc",
        ]
    )

    assert verifier._release_metadata(args) == {
        "api_revision": "api--release-1",
        "api_image_digest": "sha256:abc",
    }


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--verify-release-only", "--base-url", "http://localhost:8000"], True),
        (
            [
                "--run-setups",
                "--base-url",
                "https://api.example",
                "--allow-production",
            ],
            True,
        ),
        (["--run-setups", "--base-url", "http://localhost:8000"], False),
        (["--list"], False),
    ],
)
def test_given_invocation_when_checking_release_requirement_then_remote_runs_bind(
    arguments,
    expected,
) -> None:
    args = verifier.create_parser().parse_args(arguments)

    assert verifier._requires_release_binding(args) is expected


def test_given_windows_az_shim_when_running_then_cmd_expands_quoted_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_which(name: str) -> str | None:
        return {
            "az": r"C:\Program Files\Azure CLI\az.cmd",
            "cmd.exe": r"C:\Windows\System32\cmd.exe",
        }.get(name)

    def fake_run(command: list[str], **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return SimpleNamespace(stdout='{"status": "ok"}')

    monkeypatch.delenv("COMSPEC", raising=False)
    monkeypatch.setattr(verifier.shutil, "which", fake_which)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    result = verifier._run_json_command(["az", "account", "show", "-o", "json"])

    assert result == {"status": "ok"}
    assert captured["command"] == [
        r"C:\Windows\System32\cmd.exe",
        "/d",
        "/s",
        "/c",
        "%PLANETARY_EXPLORER_AZ_COMMAND%",
    ]
    assert (
        captured["env"]["PLANETARY_EXPLORER_AZ_COMMAND"]
        == 'call "C:\\Program Files\\Azure CLI\\az.cmd" account show -o json'
    )


def test_given_live_release_when_verifying_then_control_plane_and_https_are_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    bundle = b"console.log('release');"
    bundle_hash = verifier.hashlib.sha256(bundle).hexdigest()
    args = verifier.create_parser().parse_args(
        [
            "--api-revision",
            "api--release-1",
            "--api-image-digest",
            "sha256:abc",
            "--weather-revision",
            "weather--release-1",
            "--weather-image-digest",
            "sha256:def",
            "--frontend-deployment-id",
            "deploy-1",
            "--frontend-bundle",
            "index-release.js",
            "--frontend-bundle-sha256",
            bundle_hash,
            "--frontend-url",
            "https://web.example/",
            "--azure-subscription",
            "subscription-1",
            "--azure-tenant",
            "tenant-1",
            "--azure-resource-group",
            "rg-test",
            "--azure-container-app",
            "api-test",
            "--azure-weather-app",
            "weather-test",
            "--azure-frontend-app",
            "web-test",
            "--azure-geofm-resource-group",
            "rg-geofm",
            "--azure-geofm-worker",
            "worker-test",
        ]
    )

    def command_result(command: list[str]):
        if command[1:3] == ["account", "show"]:
            return {"id": "subscription-1", "tenantId": "tenant-1"}
        if command[1:3] == ["containerapp", "show"]:
            app_name = command[command.index("--name") + 1]
            if app_name == "worker-test":
                return {
                    "properties": {
                        "template": {"scale": {"minReplicas": 0}},
                    }
                }
            if app_name == "weather-test":
                return {
                    "properties": {
                        "provisioningState": "Succeeded",
                        "latestReadyRevisionName": "weather--release-1",
                    }
                }
            return {
                "properties": {
                    "provisioningState": "Succeeded",
                    "latestReadyRevisionName": "api--release-1",
                    "configuration": {
                        "ingress": {"fqdn": "api.example"},
                    },
                }
            }
        if command[1:4] == ["containerapp", "revision", "show"]:
            app_name = command[command.index("--name") + 1]
            image = (
                "registry/weather@sha256:def"
                if app_name == "weather-test"
                else "registry/api@sha256:abc"
            )
            return {
                "properties": {
                    "healthState": "Healthy",
                    "runningState": (
                        "ScaledToZero" if app_name == "weather-test" else "Running"
                    ),
                    "active": True,
                    "trafficWeight": 100,
                    "template": {
                        "containers": [{"image": image}],
                    },
                }
            }
        if command[1:4] == ["containerapp", "revision", "list"]:
            return [{"properties": {"active": True, "replicas": 0}}]
        return [{"id": "deploy-1", "complete": True, "status": 4, "active": True}]

    monkeypatch.setattr(verifier, "_run_json_command", command_result)
    monkeypatch.setattr(
        verifier,
        "_get_json",
        lambda *_args: (200, {"status": "healthy"}),
    )
    monkeypatch.setattr(
        verifier,
        "_read_url_bytes",
        lambda url: (
            bundle
            if url.endswith(".js")
            else b'<script src="assets/index-release.js"></script>'
        ),
    )

    # Act
    release = verifier._verify_release_metadata(args, "https://api.example")

    # Assert
    assert release["verification"]["api_traffic_weight"] == 100
    assert release["verification"]["weather_traffic_weight"] == 100
    assert release["verification"]["frontend_bundle_live_sha256"] == bundle_hash
    assert release["verification"]["geofm_worker_active_replicas"] == 0


def test_given_release_drift_when_reverifying_then_matrix_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    initial = {
        "api_revision": "api--release-1",
        "verification": {
            "verified_at": "2026-09-03T12:00:00Z",
            "api_traffic_weight": 100,
        },
    }
    monkeypatch.setattr(
        verifier,
        "_verify_release_metadata",
        lambda *_args: {
            "api_revision": "api--release-2",
            "verification": {
                "verified_at": "2026-09-03T12:30:00Z",
                "api_traffic_weight": 100,
            },
        },
    )

    # Act and Assert
    with pytest.raises(ValueError, match="changed during scenario execution"):
        verifier._reverify_release_metadata(SimpleNamespace(), "https://api.example", initial)


def test_given_unmarked_429_when_classifying_then_retry_is_suppressed() -> None:
    assert (
        verifier._is_transient_result(
            429,
            {"detail": "Too Many Requests"},
        )
        is False
    )


def test_given_proven_pre_dispatch_429_when_classifying_then_retry_is_allowed() -> None:
    assert (
        verifier._is_transient_result(
            429,
            {"retry": {"safe": True, "stage": "pre_dispatch"}},
        )
        is True
    )


def test_given_item_interval_when_checking_then_requested_date_must_overlap() -> None:
    feature = {
        "properties": {
            "start_datetime": "2026-06-28T00:00:00Z",
            "end_datetime": "2026-06-28T23:59:59Z",
        }
    }

    assert (
        verifier._feature_overlaps_date_range(
            feature,
            ("2026-05-01", "2026-06-30"),
        )
        is True
    )
    assert (
        verifier._feature_overlaps_date_range(
            feature,
            ("2025-05-01", "2025-06-30"),
        )
        is False
    )


def test_given_mixed_tool_evidence_when_normalizing_then_names_are_preserved() -> None:
    assert verifier._tool_names(
        [{"tool": "sample_timeseries"}, "get_precipitation_projection"]
    ) == {"sample_timeseries", "get_precipitation_projection"}


def test_given_disabled_pro_when_building_result_then_elapsed_time_is_reportable() -> (
    None
):
    query = (
        "Show my MPC Pro aerial imagery over Jasper, Alberta "
        "from 2026-01-01 to 2026-08-26"
    )
    result = verifier.run_setup_scenario(
        verifier.Scenario("Building Damage", "Jasper", query),
        base_url="http://localhost:8000",
        index=1,
        features={"mpcPro": False},
    )

    assert result["outcome"] == "blocked"
    assert result["elapsed_ms"] == 0


def test_given_enabled_pro_when_building_analysis_lacks_rendered_evidence_then_blocked() -> (
    None
):
    # Arrange
    scenario = verifier.Scenario(
        "Building Damage",
        "Jasper",
        (
            "Show my MPC Pro aerial imagery over Jasper, Alberta "
            "from 2026-01-01 to 2026-08-26"
        ),
        question="Assess potential building damage.",
    )

    # Act
    endpoint, body, blocked_reason = verifier._module_request(
        scenario,
        base_url="http://localhost:8000",
        features={"mpcPro": True},
    )

    # Assert
    assert endpoint == ""
    assert body is None
    assert "browser-captured screenshot" in blocked_reason


def test_given_adversarial_context_when_running_setup_then_stale_location_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = "Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26"
    captured: dict = {}

    def post_json(_base_url, _path, payload, **_kwargs):
        captured.update(payload)
        return 200, {
            "translation_metadata": {
                "stac_query": {"bbox": [-79.64, 43.58, -79.12, 43.86]},
            },
            "data": {
                "stac_results": {
                    "features": [
                        {
                            "id": "toronto-scene",
                            "collection": "sentinel-2-l2a",
                            "bbox": [-79.64, 43.58, -79.12, 43.86],
                            "properties": {"datetime": "2026-08-05T00:00:00Z"},
                        }
                    ],
                },
            },
        }

    monkeypatch.setattr(verifier, "_post_json", post_json)

    result = verifier.run_setup_scenario(
        verifier.Scenario("Vision - Optical Imagery", "Toronto", query),
        base_url="http://localhost:8000",
        index=1,
        features={"mpcPro": False},
        adversarial_context=True,
    )

    assert result["outcome"] == "pass"
    assert captured["pin"] == {"lat": -33.8688, "lng": 151.2093}
    assert captured["map_bounds"]["east"] == 151.4
    assert captured["current_collection"] == "sentinel-1-rtc"
    assert captured["geoint_mode"] is True


def test_given_unrelated_pro_scene_when_validating_then_setup_fails(
    monkeypatch,
) -> None:
    query = (
        "Show my MPC Pro aerial imagery over Jasper, Alberta "
        "from 2026-01-01 to 2026-08-26"
    )
    monkeypatch.setattr(
        verifier,
        "_post_json",
        lambda *_args, **_kwargs: (
            200,
            {
                "results": {
                    "features": [
                        {
                            "id": "unrelated",
                            "bbox": [-1, -1, 1, 1],
                            "properties": {"datetime": "2020-01-01T00:00:00Z"},
                            "_planetary_explorer_stac_mode": "pro",
                        }
                    ]
                }
            },
        ),
    )

    result = verifier.run_setup_scenario(
        verifier.Scenario("Building Damage", "Jasper", query),
        base_url="http://localhost:8000",
        index=1,
        features={"mpcPro": True},
    )

    assert result["outcome"] == "fail"
    assert result["returned_scene_covers_expected_center"] is False
    assert result["returned_date_matches"] is False


def test_given_split_pro_evidence_when_validating_then_setup_fails(monkeypatch) -> None:
    query = (
        "Show my MPC Pro aerial imagery over Jasper, Alberta "
        "from 2026-01-01 to 2026-08-26"
    )
    monkeypatch.setattr(
        verifier,
        "_post_json",
        lambda *_args, **_kwargs: (
            200,
            {
                "results": {
                    "features": [
                        {
                            "id": "right-place-wrong-date",
                            "bbox": [-118.2, 52.8, -118.0, 53.0],
                            "properties": {"datetime": "2020-01-01T00:00:00Z"},
                            "_planetary_explorer_stac_mode": "pro",
                        },
                        {
                            "id": "right-date-wrong-place",
                            "bbox": [-1, -1, 1, 1],
                            "properties": {"datetime": "2026-06-01T00:00:00Z"},
                            "_planetary_explorer_stac_mode": "pro",
                        },
                    ]
                }
            },
        ),
    )

    result = verifier.run_setup_scenario(
        verifier.Scenario("Building Damage", "Jasper", query),
        base_url="http://localhost:8000",
        index=1,
        features={"mpcPro": True},
    )

    assert result["returned_scene_covers_expected_center"] is True
    assert result["returned_date_matches"] is True
    assert result["matching_scene_id"] is None
    assert result["outcome"] == "fail"


def test_given_wrong_sample_date_when_validating_then_provenance_fails() -> None:
    feature = {
        "id": "scene-2026",
        "properties": {"datetime": "2026-06-15T12:00:00Z"},
    }
    payload = {
        "structured": {
            "sample_raster_value": {
                "structured": {
                    "sampled_scenes": [{"item_id": "scene-2026", "date": "2030-06-15"}],
                }
            }
        }
    }

    provenance = verifier._raster_sample_provenance(payload, feature)

    assert provenance["item_matches"] is True
    assert provenance["date_matches"] is False
    assert provenance["scene_matches"] is False


def test_given_split_sample_evidence_when_validating_then_scene_does_not_match() -> (
    None
):
    feature = {
        "id": "expected-scene",
        "properties": {"datetime": "2026-06-15T12:00:00Z"},
    }
    payload = {
        "structured": {
            "sample_raster_value": {
                "structured": {
                    "sampled_scenes": [
                        {"item_id": "expected-scene", "date": "2030-06-15"},
                        {"item_id": "other-scene", "date": "2026-06-15"},
                    ],
                }
            }
        }
    }

    provenance = verifier._raster_sample_provenance(payload, feature)

    assert provenance["item_matches"] is True
    assert provenance["date_matches"] is True
    assert provenance["scene_matches"] is False


def test_given_static_scene_without_date_when_validating_then_exact_item_matches() -> (
    None
):
    feature = {
        "id": "static-dem-scene",
        "properties": {},
    }
    payload = {
        "structured": {
            "sample_raster_value": {
                "structured": {
                    "sampled_scenes": [
                        {"item_id": "static-dem-scene", "date": ""},
                    ],
                }
            }
        }
    }

    provenance = verifier._raster_sample_provenance(payload, feature)

    assert provenance["item_matches"] is True
    assert provenance["date_matches"] is True
    assert provenance["scene_matches"] is True


def test_given_partial_climate_comparison_when_validating_then_result_fails() -> None:
    scenario = verifier.Scenario(
        "Extreme Weather",
        "Montreal, Quebec",
        "Montreal, Quebec, Canada",
        question="Compare SSP245 and SSP585.",
        expected_tools=("compare_climate_scenarios",),
    )
    payload = {
        "result": {
            "analysis": "Partial comparison",
            "tool_calls": [
                {
                    "tool": "compare_climate_scenarios",
                    "result": {
                        "comparison": {
                            "tasmax": {"ssp245": {"value": 28.0}},
                            "pr": {},
                        }
                    },
                }
            ],
        }
    }

    valid, details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is False
    assert details["comparison_cells"]["tasmax.ssp245"] == 28.0
    assert details["comparison_cells"]["pr.ssp585"] is None


def test_given_twelve_months_when_validating_then_timeseries_passes() -> None:
    scenario = verifier.Scenario(
        "Extreme Weather",
        "Toronto, Ontario",
        "Toronto, Ontario, Canada",
        question="Show monthly precipitation.",
        expected_tools=("sample_timeseries",),
    )
    payload = {
        "result": {
            "analysis": "Monthly precipitation",
            "tool_calls": [
                {
                    "tool": "sample_timeseries",
                    "result": {
                        "periods": [
                            {"period": str(month), "mean": float(month)}
                            for month in range(1, 13)
                        ]
                    },
                }
            ],
        }
    }

    valid, details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is True
    assert details["monthly_period_count"] == 12


def test_given_negative_forecast_precipitation_when_validating_then_result_fails() -> (
    None
):
    scenario = verifier.Scenario(
        "Forecast",
        "Atlantic Canada precipitation comparison",
        "Nova Scotia, Canada",
        question="Compare Aurora and Earth-2 precipitation.",
    )
    payload = {
        "result": {
            "providers_called": ["aurora-1.x", "earth2-fcn"],
            "providers_succeeded": ["aurora-1.x", "earth2-fcn"],
            "providers_failed": [],
            "forecasts": [
                {
                    "provider_id": provider,
                    "variables": {"precip": [[-0.001]]},
                    "units": {"precip": "mm/hr"},
                    "extras": {
                        "source": source,
                        "native_model_inference": False,
                    },
                }
                for provider, source in (
                    ("aurora-1.x", "ECMWF IFS 0.25"),
                    ("earth2-fcn", "NOAA GFS"),
                )
            ],
            "ensemble_summary": {"variables": {"precip": {"min": -0.001}}},
        }
    }

    valid, _details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is False


def test_given_slow_mobility_result_when_validating_then_result_fails() -> None:
    scenario = verifier.Scenario(
        "Mobility",
        "Yukon River corridor, Yukon",
        "Whitehorse, Yukon, Canada",
        question="Assess this route.",
        expected_tools=("analyze_two_point_traverse",),
    )
    payload = {
        "result": {
            "response": "Mobility assessment",
            "tool_calls": [{"tool": "analyze_two_point_traverse"}],
        }
    }

    valid, details = verifier._validate_module_result(
        scenario,
        200,
        payload,
        elapsed_ms=50_001,
    )

    assert valid is False
    assert details["within_ingress_retry_window"] is False


def test_given_name_only_mobility_tool_when_validating_then_result_fails() -> None:
    scenario = verifier.Scenario(
        "Mobility",
        "Yukon River corridor, Yukon",
        "Whitehorse, Yukon, Canada",
        question="Assess this route.",
        expected_tools=("analyze_two_point_traverse",),
    )
    payload = {
        "result": {
            "response": "Mobility assessment",
            "tool_calls": [{"tool": "analyze_two_point_traverse"}],
        }
    }

    valid, _details = verifier._validate_module_result(
        scenario,
        200,
        payload,
        elapsed_ms=49_999,
    )

    assert valid is False


def test_given_empty_mobility_evidence_when_validating_then_result_fails() -> None:
    scenario = verifier.Scenario(
        "Mobility",
        "Yukon River corridor, Yukon",
        "Whitehorse, Yukon, Canada",
        question="Assess this route.",
        expected_tools=("analyze_two_point_traverse",),
    )
    payload = {
        "result": {
            "response": "Mobility assessment",
            "tool_calls": [
                {
                    "tool": "analyze_two_point_traverse",
                    "result": {
                        "complete": True,
                        "route": {"distance_km": 4.0},
                        "corridor": {"overall_status": "GO", "waypoints_sampled": 1},
                        "origin": {},
                        "destination": {},
                        "coverage": {
                            "origin_sources": [],
                            "destination_sources": [],
                            "waypoints_with_data": 0,
                        },
                    },
                }
            ],
        }
    }

    valid, _details = verifier._validate_module_result(
        scenario,
        200,
        payload,
        elapsed_ms=10_000,
    )

    assert valid is False


def test_given_grounded_forecast_when_validating_then_result_passes() -> None:
    scenario = verifier.Scenario(
        "Forecast",
        "Atlantic Canada precipitation comparison",
        "Nova Scotia, Canada",
        question="Compare Aurora and Earth-2 precipitation.",
    )
    forecasts = [
        {
            "provider_id": provider,
            "variables": {"precip": [[value]]},
            "units": {"precip": "mm/hr"},
            "extras": {
                "source": source,
                "native_model_inference": False,
                "data_source_note": "NWP adapter source",
            },
        }
        for provider, source, value in (
            ("aurora-1.x", "ECMWF IFS 0.25", 0.0),
            ("earth2-fcn", "NOAA GFS", 0.2),
        )
    ]
    payload = {
        "result": {
            "providers_succeeded": ["aurora-1.x", "earth2-fcn"],
            "providers_failed": [],
            "forecasts": forecasts,
            "ensemble_summary": {
                "variables": {
                    "precip": {
                        "mean": 0.1,
                        "min": 0.0,
                        "max": 0.2,
                        "samples": 2,
                        "unit": "mm/hr",
                    },
                }
            },
        }
    }

    valid, details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is True
    assert details["forecast_sources"][0]["source"] == "ECMWF IFS 0.25"


def test_given_forecast_without_source_when_validating_then_result_fails() -> None:
    scenario = verifier.Scenario(
        "Forecast",
        "Prairie temperature and wind",
        "Saskatchewan, Canada",
        question="Forecast temperature and wind.",
    )
    payload = {
        "result": {
            "providers_succeeded": ["aurora-1.x"],
            "forecasts": [
                {
                    "provider_id": "aurora-1.x",
                    "variables": {"precip": [[0.1]]},
                    "units": {"precip": "mm/hr"},
                    "extras": {"native_model_inference": False},
                }
            ],
            "ensemble_summary": {
                "variables": {"precip": {"min": 0.1}},
            },
        }
    }

    valid, _details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is False


def test_given_prairie_forecast_without_temperature_or_wind_when_validating_then_fails() -> (
    None
):
    scenario = verifier.Scenario(
        "Forecast",
        "Prairie temperature and wind",
        "Saskatchewan, Canada",
        question="Forecast 2m temperature and 10m wind across Saskatchewan.",
    )
    payload = {
        "result": {
            "providers_called": ["aurora-1.x"],
            "providers_succeeded": ["aurora-1.x"],
            "providers_failed": [],
            "forecasts": [
                {
                    "provider_id": "aurora-1.x",
                    "variables": {"precip": [[0.1]]},
                    "units": {"precip": "mm/hr"},
                    "extras": {
                        "source": "ECMWF IFS 0.25",
                        "native_model_inference": False,
                    },
                }
            ],
            "ensemble_summary": {
                "variables": {
                    "precip": {
                        "mean": 0.1,
                        "min": 0.1,
                        "max": 0.1,
                        "samples": 1,
                        "unit": "mm/hr",
                    }
                }
            },
        }
    }

    valid, details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is False
    assert details["required_variables"] == ["t2m", "u10", "v10"]


def test_given_one_provider_for_every_model_forecast_when_validating_then_fails() -> (
    None
):
    scenario = verifier.Scenario(
        "Forecast",
        "Great Lakes five-day ensemble",
        "Lake Ontario, Canada",
        question="Use every available model and summarize ensemble spread.",
    )
    variables = {variable: [[0.1]] for variable in ("t2m", "precip", "u10", "v10")}
    units = {
        "t2m": "K",
        "precip": "mm/hr",
        "u10": "m/s",
        "v10": "m/s",
    }
    summaries = {
        variable: {
            "mean": 0.1,
            "min": 0.1,
            "max": 0.1,
            "samples": 1,
            "unit": units[variable],
        }
        for variable in variables
    }
    payload = {
        "result": {
            "providers_called": ["aurora-1.x"],
            "providers_succeeded": ["aurora-1.x"],
            "providers_failed": [],
            "forecasts": [
                {
                    "provider_id": "aurora-1.x",
                    "variables": variables,
                    "units": units,
                    "extras": {
                        "source": "ECMWF IFS 0.25",
                        "native_model_inference": False,
                    },
                }
            ],
            "ensemble_summary": {"variables": summaries},
        }
    }

    valid, _details = verifier._validate_module_result(scenario, 200, payload)

    assert valid is False
