---
title: "feat(planetary-explorer): harden Get Started workflows"
description: Hardened Get Started context isolation, geospatial evidence, layer controls, and release verification
---

## Summary

This PR hardened the complete Get Started experience and added dynamic map-layer controls. Setup actions now start clean chat and map contexts, analysis results retain verifiable scene and provider provenance, and long-running release checks fail when the deployed revision changes during execution.

## Changes

### Workflow and UI

* Added an accessible map-layer dialog for visibility and opacity across Azure Maps and Leaflet
* Reset stale modules, pins, imagery, confirmations, and history when a new Setup action starts
* Ignored late map, comparison, screenshot, analysis, and history continuations from superseded workflows
* Gated MPC Pro, Fabric, Resilience, and Forecast controls from deployment features
* Preserved valid imagery and completed GeoFM overlays while removing stale layers

### Analysis and Evidence

* Made locked collection loads authoritative and preserved Public versus MPC Pro provenance end to end
* Added deterministic STAC inspection, point-covering scene selection, exact-date handling, and sampled scene/date evidence
* Added bounded two-point mobility and monthly climate analysis contracts
* Required authenticated MPC Pro scene resolution for Building Damage
* Distinguished native weather inference from adapter, fallback, and stub data and rejected mixed units

### Reliability and Verification

* Added side-effect-aware retries and bounded admission for agent, climate, and mobility work
* Required confirmation for GPU-backed GeoFM mutations
* Added release-bound Python and Playwright matrices with post-run drift detection
* Expanded backend, frontend, verifier, and weather-adapter regression coverage
* Added the Get Started playbook and updated deployment guidance

## Related Issues

None

## Validation

* [x] Frontend tests: 169 passed
* [x] Frontend production build
* [x] Backend tests: 608 passed, 1 skipped, excluding two unchanged known-baseline files
* [x] Python verifier tests: 35 passed
* [x] Browser verifier tests: 10 passed
* [x] Patch integrity check

## Notes

The two excluded backend files contain six unchanged baseline failures in LoadAgent and MCP catalog client tests. The user-owned `.vscode/settings.json` change is not included in this PR.
