---
title: Chunks 36-43 PR Reference Review
description: Bounded review of PR reference lines 17501-21293 for PR description generation
---

## Chunks 36-43 Review

The changes added end-to-end verification for the canonical Get Started scenarios. They exercised API setup and analysis paths, browser-rendered imagery, deployment identity, and release stability so a scenario passed only when its returned data and visible evidence matched the requested location, date, collection, tool, and provider behavior.

### Files Changed

* `scripts/tests/test_verify_get_started_scenarios.py` (inferred path because line 17501 began mid-diff): added Python tests for release drift, retry eligibility, temporal and spatial scene matching, raster provenance, climate completeness, mobility evidence, and forecast provenance
* `scripts/tests/verify_get_started_image_analysis.test.mjs`: added Node tests for production consent, complete release binding, expected API-origin matching, imagery-denial classification, adversarial zoom behavior, and post-run release drift
* `scripts/verify_get_started_image_analysis.mjs`: added a Playwright browser verifier that drove canonical Vision scenarios, captured map and request evidence, and wrote structured pass/fail artifacts
* `scripts/verify_get_started_scenarios.py`: added a Python CLI that loaded the TypeScript scenario inventory, ran setup and analysis matrices, validated family-specific evidence, and verified live Azure release metadata

### Technical Details

* Loaded canonical scenario definitions by transpiling `planetary-explorer/web-ui/src/config/canadianExamples.ts` with esbuild, then normalized Vision, Terrain, Mobility, Extreme Weather, Building Damage, Site Intel, Resilience, and Forecast rows into one inventory. Inventory validation required two or three locations per family.
* Validated setup responses against explicit Canadian centers, collections, date ranges, and navigation tolerances. STAC and MPC Pro scenarios required one returned scene to satisfy the location, date, collection, and mode constraints together, which prevented split evidence from producing a false pass.
* Added an adversarial setup mode that submitted stale Sydney pins, bounds, loaded collections, and GEOINT state. The browser flow also required a fresh session and proved that the subsequent Get Started request cleared stale fields and restored non-GEOINT setup behavior.
* Added family-specific analysis checks. Vision sampling required structured `sample_raster_value` success tied to the selected item and date. Mobility required complete route, corridor, endpoint, source, and waypoint evidence within 50 seconds. Climate comparisons required all SSP245 and SSP585 temperature and precipitation cells, while monthly series required 12 numeric periods.
* Required forecast responses to identify successful providers, source provenance, inference mode, requested variables, units, numeric values, and complete ensemble summaries. Precipitation could not be negative, named model comparisons required the expected providers, and “every available model” scenarios required at least two fully successful providers.
* Limited retries to HTTP 429 responses that explicitly declared `retry.safe: true` and `retry.stage: pre_dispatch`. Unmarked throttling responses were not retried, which avoided replaying work after an uncertain dispatch state.
* Added a Playwright image-analysis flow that observed only matching POST requests on the declared API origin, verified map zoom and imagery-layer visibility, compared visible and hidden map pixels, decoded PNG or JPEG screenshot payloads, rejected blank or undersized images, and required `describe_map_screenshot` structured evidence.
* Grounded browser analysis to the submitted pin and collection, rejected coordinate contradictions and statements that the requested imagery was absent, and required color-aware wording for uniform thematic images. MODIS 17A2H responses had to identify GPP and could not mislabel the product as NPP.
* Required explicit `--allow-production` consent and complete release-binding arguments for non-loopback runs. The Python verifier checked the Azure subscription and tenant, API and weather Container App revisions and immutable image digests, health and traffic state, the active App Service deployment, the live frontend bundle SHA-256, and zero active GeoFM worker replicas.
* Reverified release metadata after each live matrix and rejected mid-run drift after excluding only the expected verification timestamp change. This bound reported results to one stable deployment rather than a mixed rollout.
* Distinguished unavailable capabilities from failures. MPC Pro, Fabric, Resilience authentication, and Forecast availability returned blocked outcomes when deployment configuration or sign-in prerequisites were absent.

### Notable Patterns

* The verification logic consistently failed closed: tool names alone, partial evidence, mismatched item/date pairs, missing provider sources, stale UI context, and unbound production deployments did not pass.
* Production safeguards were layered through explicit consent, expected-origin filtering, Azure account checks, immutable image and bundle verification, 100% revision traffic checks, and before/after release snapshots.
* The Resilience path read `PLANETARY_EXPLORER_ACCESS_TOKEN` from the environment and sent it only as an authorization header. The reviewed result objects did not include the token.
* The browser verifier persisted payload images, browser screenshots, response excerpts, and failure captures under `.copilot-tracking/get-started-validation`. Production artifact retention therefore needed to account for visible application or tenant data.
* The scenario loader executed transpiled repository TypeScript through `new Function`. This kept the verifier aligned with the UI inventory but assumed the checked-in scenario source and local dependency tree were trusted.
* Runtime compatibility depended on Python, Node.js, web UI esbuild, Playwright 1.62.1, and Azure CLI commands for Container Apps and App Service. Windows Azure CLI shims received explicit `.cmd`/`.bat` handling through `cmd.exe`.
* Added tests documented verification intent for the critical branches in this range, but no test command output or pass/fail execution log appeared in lines 17501-21293.
* The assigned range began inside a Python test diff, so its path and change header were not visible. The path above was inferred from the tested `verify_get_started_scenarios` API. Commit messages were also outside this range, so rationale was limited to code, docstrings, CLI help, and test assertions present in the bounded diff.