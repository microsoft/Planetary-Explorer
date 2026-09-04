---
title: PR reference analysis
description: Verified analysis of the Get Started hardening release against geofm-guided-workflow
---

## PR Reference Analysis

### Summary

The branch contains four commits and changes 92 files. It adds dynamic map-layer controls and hardens the complete Get Started path across frontend state isolation, deterministic geospatial analysis, evidence provenance, bounded retries, feature gating, and release verification.

### Changes by Significance

#### Get Started Context Isolation

* Treated every Setup action as a fresh conversation and map context boundary
* Aborted or invalidated superseded chat, screenshot, comparison, terrain, mobility, and generic GEOINT work before late continuations could restore stale state
* Scoped persisted history to the active conversation and rechecked history generations after conflict reconciliation
* Denied outstanding destructive confirmations when a new Setup superseded their context
* Added regression coverage for stale map workflows, late history reconciliation, setup history offsets, and feature-aware restoration

#### Geospatial Evidence and Routing

* Made v2 collection loads authoritative and preserved Public versus MPC Pro provenance through search, rendering, history, signing, restoration, and raster sampling
* Added deterministic STAC asset inspection and point-coverage scene selection
* Expanded raster evidence with numeric success requirements, scale and offset handling, product bands, indices, and exact sampled scene/date provenance
* Normalized exact-date and static-collection behavior so Setup queries retained their requested observation windows
* Added deterministic two-point mobility and monthly climate paths with bounded work, completeness contracts, and labeled partial results
* Required Building Damage to use deployment-enabled MPC Pro plus authenticated GeoCatalog scene resolution rather than client-authored mode labels

#### Map and Workflow Experience

* Added an accessible dynamic layer dialog with visibility, opacity, focus restoration, and Azure Maps/Leaflet parity
* Preserved relevant imagery and completed GeoFM overlays across style reloads while removing stale layers on empty results or new Setup actions
* Added deployment-aware gates for MPC Pro, Fabric, Resilience, and Forecast entry points
* Updated Canadian examples with explicit locations, dates, collections, bands, and expected tools
* Corrected legend replacement so denied, queued, and failed GeoFM work retained the loaded HLS layer

#### Reliability and Safety

* Added side-effect-aware Agent Service retries that stop after dispatch or tool execution
* Added bounded admission for mobility and climate work to prevent duplicate or indefinitely queued computation
* Required confirmation for GeoFM mutations that can activate billed GPU work
* Distinguished native weather inference from NWP adapters, deterministic fallbacks, and stubs; rejected mixed forecast units
* Reverified API, weather, frontend, traffic, and worker release identity after long Python and browser matrices to reject mixed-release reports
* Marked API-only Building Damage verification as blocked unless real browser screenshot and authenticated Pro scene evidence are available

#### Verification and Documentation

* Added or expanded backend, frontend, weather-adapter, Python verifier, and browser verifier tests
* Added a Get Started playbook and updated deployment, weather, and Thunder Bay guidance
* Pinned frontend tooling and security-sensitive transitive dependencies

### Issue References

None

### Security Analysis

* Building Damage provenance now fails closed against the configured authenticated GeoCatalog
* Persisted history retains minimal scene references and omits STAC asset payloads and signed URLs
* Superseded write confirmations are denied during Setup reset
* Production verification requires explicit consent and immutable Azure release binding before and after execution
* No credentials, tokens, or secret values were added to the branch

### Verification Notes

* Frontend: 21 files, 169 tests passed
* Frontend production build: passed with Vite 7.3.6
* Backend: 608 passed and 1 skipped, excluding two unchanged known-baseline files with six existing failures
* Python release verifier: 35 passed
* Browser verifier semantics: 10 passed
* Focused backend provenance and mobility contracts: 15 passed
* Patch integrity: `git diff --check` passed
* Diagnostics: touched files were clean; only unchanged optional Teams imports remained unresolved in `fastapi_app.py`
* Branch freshness: 0 commits behind `fork/geofm-guided-workflow`
* Conventional commits: all four branch commits conform
* User-owned `.vscode/settings.json` changes were excluded from the commits and PR diff
