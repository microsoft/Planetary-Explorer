#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: MIT
"""Restore Planetary Explorer Container App runtime settings after azd deploy."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from urllib.request import urlopen

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
API_PORT = 8080


@dataclass(frozen=True)
class RuntimeProfile:
    """Container App ingress and health-probe settings."""

    probes: tuple[dict[str, object], ...]
    sticky_sessions: bool


RUNTIME_PROFILES: dict[str, RuntimeProfile] = {
    "api": RuntimeProfile(
        sticky_sessions=True,
        probes=(
            {
                "type": "Liveness",
                "httpGet": {"path": "/api/health", "port": API_PORT},
                "initialDelaySeconds": 30,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 3,
            },
            {
                "type": "Readiness",
                "httpGet": {"path": "/api/health", "port": API_PORT},
                "initialDelaySeconds": 10,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 3,
            },
        ),
    ),
    "geofm": RuntimeProfile(
        sticky_sessions=False,
        probes=(
            {
                "type": "Startup",
                "httpGet": {"path": "/health", "port": API_PORT},
                "initialDelaySeconds": 2,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 12,
            },
            {
                "type": "Liveness",
                "httpGet": {"path": "/health", "port": API_PORT},
                "periodSeconds": 30,
                "timeoutSeconds": 3,
                "failureThreshold": 3,
            },
            {
                "type": "Readiness",
                "httpGet": {"path": "/ready", "port": API_PORT},
                "initialDelaySeconds": 5,
                "periodSeconds": 15,
                "timeoutSeconds": 10,
                "failureThreshold": 4,
            },
        ),
    ),
    "web-search": RuntimeProfile(
        sticky_sessions=False,
        probes=(
            {
                "type": "Startup",
                "httpGet": {"path": "/health", "port": API_PORT},
                "initialDelaySeconds": 2,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 12,
            },
            {
                "type": "Liveness",
                "httpGet": {"path": "/health", "port": API_PORT},
                "periodSeconds": 30,
                "timeoutSeconds": 3,
                "failureThreshold": 3,
            },
            {
                "type": "Readiness",
                "httpGet": {"path": "/ready", "port": API_PORT},
                "initialDelaySeconds": 5,
                "periodSeconds": 15,
                "timeoutSeconds": 5,
                "failureThreshold": 4,
            },
        ),
    ),
}

logger = logging.getLogger(__name__)


def _enabled(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def reconcile_api_optional_services(name: str, resource_group: str) -> None:
    """Apply optional-service outputs to a newly deployed or adopted API."""
    values: list[str] = []
    removed_values: list[str] = []
    public_demo = _enabled(os.getenv("PUBLIC_DEMO_MODE", ""))
    chat_endpoint = os.getenv("AZURE_COSMOS_CHAT_HISTORY_ENDPOINT", "").strip()
    blob_endpoint = os.getenv("AZURE_CHAT_ARTIFACT_BLOB_ENDPOINT", "").strip()
    chat_requested = public_demo or bool(chat_endpoint or blob_endpoint)
    if chat_requested:
        if public_demo:
            values.extend(
                [
                    "PE_FEATURE_CHAT_HISTORY=false",
                    "CHAT_HISTORY_STORE=disabled",
                    "CHAT_ARTIFACT_STORE=disabled",
                ]
            )
            removed_values.extend(
                [
                    "COSMOS_CHAT_ENDPOINT",
                    "COSMOS_CHAT_DATABASE",
                    "COSMOS_CHAT_CONTAINER",
                    "CHAT_ARTIFACT_BLOB_ENDPOINT",
                    "CHAT_ARTIFACT_CONTAINER",
                ]
            )
        elif chat_endpoint and blob_endpoint:
            values.extend(
                [
                    "PE_FEATURE_CHAT_HISTORY=true",
                    "CHAT_HISTORY_STORE=cosmos",
                    f"COSMOS_CHAT_ENDPOINT={chat_endpoint}",
                    "COSMOS_CHAT_DATABASE="
                    + os.getenv(
                        "AZURE_COSMOS_CHAT_HISTORY_DATABASE",
                        "planetary-explorer",
                    ),
                    "COSMOS_CHAT_CONTAINER="
                    + os.getenv(
                        "AZURE_COSMOS_CHAT_HISTORY_CONTAINER",
                        "chat-history",
                    ),
                    "CHAT_ARTIFACT_STORE=blob",
                    f"CHAT_ARTIFACT_BLOB_ENDPOINT={blob_endpoint}",
                    "CHAT_ARTIFACT_CONTAINER="
                    + os.getenv("AZURE_CHAT_ARTIFACT_CONTAINER", "chat-artifacts"),
                ]
            )
        else:
            raise RuntimeError("Chat history deployment outputs are incomplete.")

    web_search_url = os.getenv("AZURE_WEB_SEARCH_MCP_URL", "").strip()
    if web_search_url:
        web_search_key = os.getenv("WEB_SEARCH_MCP_API_KEY", "").strip()
        if len(web_search_key) < 32:
            raise RuntimeError(
                "WEB_SEARCH_MCP_API_KEY must contain at least 32 characters."
            )
        run_az(
            [
                "containerapp",
                "secret",
                "set",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--secrets",
                f"web-search-mcp-api-key={web_search_key}",
                "--output",
                "none",
            ]
        )
        values.extend(
            [
                "WEB_SEARCH_ENABLED=true",
                f"WEB_SEARCH_MCP_URL={web_search_url}",
                "WEB_SEARCH_MCP_API_KEY=secretref:web-search-mcp-api-key",
            ]
        )

    weather_stub_url = os.getenv("AZURE_WEATHER_STUB_URL", "").strip().rstrip("/")
    if weather_stub_url:
        parsed_weather_url = urlsplit(weather_stub_url)
        if parsed_weather_url.scheme != "https" or not parsed_weather_url.hostname:
            raise RuntimeError("AZURE_WEATHER_STUB_URL must be an absolute HTTPS URL.")
        values.extend(
            [
                "FORECAST_AGENT_ENABLED=1",
                f"AURORA_ENDPOINT_URL={weather_stub_url}",
                f"EARTH2_FCN_ENDPOINT_URL={weather_stub_url}",
            ]
        )

    geofm_url = os.getenv("AZURE_GEOFM_MCP_URL", "").strip()
    if geofm_url:
        api_key = os.getenv("GEOFM_MCP_API_KEY", "").strip()
        owner_key = os.getenv("GEOFM_OWNER_SIGNING_KEY", "").strip()
        if len(api_key) < 32 or len(owner_key) < 32:
            raise RuntimeError("GeoFM API and owner-signing keys are required.")
        run_az(
            [
                "containerapp",
                "secret",
                "set",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--secrets",
                f"geofm-mcp-api-key={api_key}",
                f"geofm-owner-signing-key={owner_key}",
                "--output",
                "none",
            ]
        )
        values.extend(
            [
                "GEOFM_ENABLED=true",
                f"GEOFM_MCP_URL={geofm_url}",
                "GEOFM_MCP_API_KEY=secretref:geofm-mcp-api-key",
                "GEOFM_OWNER_SIGNING_KEY=secretref:geofm-owner-signing-key",
            ]
        )

    if values or removed_values:
        arguments = [
            "containerapp",
            "update",
            "--name",
            name,
            "--resource-group",
            resource_group,
        ]
        if values:
            arguments.extend(["--set-env-vars", *values])
        if removed_values:
            arguments.extend(["--remove-env-vars", *removed_values])
        arguments.extend(["--output", "none"])
        run_az(arguments)


def configure_logging() -> None:
    """Configure concise command-line logging."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def create_parser() -> argparse.ArgumentParser:
    """Create the postdeploy command-line parser."""
    parser = argparse.ArgumentParser(
        description="Restore Container App ingress and health-probe settings."
    )
    parser.add_argument("--profile", choices=sorted(RUNTIME_PROFILES), default="api")
    parser.add_argument("--name", default="")
    parser.add_argument("--resource-group", default="")
    return parser


def run_az(arguments: list[str]) -> str:
    """Run Azure CLI and return its standard output."""
    executable = shutil.which("az")
    if executable is None:
        raise FileNotFoundError("Required command 'az' was not found.")
    result = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def build_update_document(
    resource: dict[str, object],
    profile_name: Literal["api", "geofm", "web-search"] = "api",
) -> dict[str, object]:
    """Build a writable Container Apps YAML document from an ARM response."""
    profile = RUNTIME_PROFILES[profile_name]
    properties = dict(resource["properties"])
    configuration = dict(properties["configuration"])
    ingress = dict(configuration["ingress"])
    ingress.pop("fqdn", None)
    ingress["targetPort"] = API_PORT
    if profile.sticky_sessions:
        ingress["stickySessions"] = {"affinity": "sticky"}
    else:
        ingress.pop("stickySessions", None)
    configuration["ingress"] = ingress

    template = dict(properties["template"])
    template.pop("revisionSuffix", None)
    containers = [dict(container) for container in template["containers"]]
    if not containers:
        raise ValueError("Container App does not define an application container.")
    containers[0]["probes"] = list(profile.probes)
    template["containers"] = containers

    writable_properties: dict[str, object] = {
        "configuration": configuration,
        "template": template,
    }
    for key in ("environmentId", "managedEnvironmentId", "workloadProfileName"):
        value = properties.get(key)
        if value is not None:
            writable_properties[key] = value

    document: dict[str, object] = {"properties": writable_properties}
    identity = resource.get("identity")
    if isinstance(identity, dict) and identity.get("type"):
        writable_identity: dict[str, object] = {"type": identity["type"]}
        user_identities = identity.get("userAssignedIdentities")
        if isinstance(user_identities, dict):
            writable_identity["userAssignedIdentities"] = {
                str(resource_id): {} for resource_id in user_identities
            }
        document["identity"] = writable_identity
    return document


def configure_container_app(
    name: str,
    resource_group: str,
    profile_name: Literal["api", "geofm", "web-search"] = "api",
) -> None:
    """Apply and verify a production ingress and probe configuration."""
    resource = json.loads(
        run_az(
            [
                "containerapp",
                "show",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--output",
                "json",
            ]
        )
    )
    document = build_update_document(resource, profile_name)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as temporary_file:
            json.dump(document, temporary_file)
            temporary_path = Path(temporary_file.name)

        run_az(
            [
                "containerapp",
                "update",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--yaml",
                str(temporary_path),
                "--output",
                "none",
            ]
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    verification = json.loads(
        run_az(
            [
                "containerapp",
                "show",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--query",
                "{port:properties.configuration.ingress.targetPort,probes:properties.template.containers[0].probes}",
                "--output",
                "json",
            ]
        )
    )
    expected_probe_types = {
        probe["type"] for probe in RUNTIME_PROFILES[profile_name].probes
    }
    probe_types = {probe.get("type") for probe in verification.get("probes", [])}
    if verification.get("port") != API_PORT or probe_types != expected_probe_types:
        raise RuntimeError(
            f"Container App {profile_name} runtime configuration verification failed."
        )


def wait_for_geofm_readiness(
    name: str,
    resource_group: str,
    attempts: int = 40,
) -> None:
    """Wait for GeoFM storage and queue permissions to become usable."""
    ingress = json.loads(
        run_az(
            [
                "containerapp",
                "show",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--query",
                "{external:properties.configuration.ingress.external,"
                "fqdn:properties.configuration.ingress.fqdn}",
                "--output",
                "json",
            ]
        )
    )
    readiness_url = (
        f"https://{ingress.get('fqdn')}/ready"
        if ingress.get("external") and ingress.get("fqdn")
        else ""
    )
    readiness_command = (
        "python -c \"import urllib.request; "
        "urllib.request.urlopen('http://localhost:8080/ready', timeout=10).read()\""
    )
    for attempt in range(1, attempts + 1):
        if readiness_url:
            try:
                with urlopen(readiness_url, timeout=10) as response:
                    snapshot = json.load(response)
                if response.status == 200 and snapshot.get("ready") is True:
                    return
            except (OSError, ValueError):
                pass
            if attempt < attempts:
                time.sleep(15)
            continue

        revision = run_az(
            [
                "containerapp",
                "show",
                "--name",
                name,
                "--resource-group",
                resource_group,
                "--query",
                "properties.latestRevisionName",
                "--output",
                "tsv",
            ]
        ).strip()
        try:
            run_az(
                [
                    "containerapp",
                    "exec",
                    "--name",
                    name,
                    "--resource-group",
                    resource_group,
                    "--revision",
                    revision,
                    "--command",
                    readiness_command,
                ]
            )
            return
        except subprocess.CalledProcessError:
            if attempt == attempts:
                break
            time.sleep(15)
    raise RuntimeError("GeoFM dependency readiness did not become healthy.")


def main(arguments: list[str] | None = None) -> int:
    """Configure a Container App target from arguments or azd environment."""
    configure_logging()
    parsed_arguments = create_parser().parse_args(arguments)
    default_name_variable = {
        "api": "AZURE_CONTAINER_APP_NAME",
        "geofm": "AZURE_GEOFM_MCP_CONTAINER_APP_NAME",
        "web-search": "AZURE_WEB_SEARCH_MCP_CONTAINER_APP_NAME",
    }[parsed_arguments.profile]
    name = (parsed_arguments.name or os.getenv(default_name_variable, "")).strip()
    resource_group = (
        parsed_arguments.resource_group or os.getenv("AZURE_RESOURCE_GROUP", "")
    ).strip()
    if not name or not resource_group:
        logger.error(
            "%s and AZURE_RESOURCE_GROUP are required.", default_name_variable
        )
        return EXIT_FAILURE

    try:
        if parsed_arguments.profile == "api":
            reconcile_api_optional_services(name, resource_group)
        configure_container_app(name, resource_group, parsed_arguments.profile)
        if parsed_arguments.profile == "geofm":
            wait_for_geofm_readiness(name, resource_group)
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        logger.error(
            "%s postdeploy configuration failed: %s",
            parsed_arguments.profile,
            exc,
        )
        return EXIT_FAILURE

    logger.info(
        "Configured %s ingress and health probes.", parsed_arguments.profile
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())