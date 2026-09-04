---
title: Get Started Release Evidence Review
description: First-time user audit of Get Started documentation, UI behavior, and final release evidence
ms.date: 2026-09-02
ms.topic: reference
---

## Research Scope

* Review the Get Started playbook and root README examples as a first-time application user
* Verify all 11 example families against the configured UI and execution paths
* Verify exact prompts, location-reset behavior, blocked prerequisites, observed numbers, provenance wording, safety limits, and local links
* Validate user-facing claims against the named final release evidence files
* Report concrete, severity-ordered findings and an approval decision

## Sources

* documentation/get-started-playbook.md
* README.md
* planetary-explorer/web-ui/src/config/canadianExamples.ts
* planetary-explorer/web-ui/src/components/GetStartedButton.tsx
* planetary-explorer/web-ui/src/components/MapView.tsx
* planetary-explorer/web-ui/src/components/Chat.tsx
* planetary-explorer/web-ui/src/components/MainApp.tsx
* planetary-explorer/web-ui/src/components/__tests__/GeointModulesFlow.test.tsx
* .copilot-tracking/get-started-validation/setup-results-final-release.json
* .copilot-tracking/get-started-validation/analysis-results-final-release.json
* .copilot-tracking/get-started-validation/image-analysis-final-release/results.json

## Findings

### Blocker: Release links are not publishable in the current Git state

All local targets resolve in this working copy, but the following files are
untracked: the playbook, its three final evidence artifacts, and the browser
verifier linked by README.md. A first-time reader of the committed repository
cannot follow those links unless the files are added before publication.

### High: Navigation-only Setup does not clear the loaded collection

The Get Started Setup event resets chat routing, sessions, selected modules,
pins, screenshots, and analysis modes. MapView does not clear satelliteData,
currentLayer, lastCollection, active raster layers, or comparisonState in that
event handler. Its navigate_to branch explicitly preserves existing satellite
data and then returns. Mobility, Extreme Weather, Site Intel, Resilience, and
Forecast all use navigation-only Setup prompts, so the README and playbook
claim that every Setup replaces the loaded collection and map state is broader
than the implemented behavior. Existing UI coverage checks only module, pin,
and marker removal; the 12-row browser artifact covers imagery Setup rows, not
navigation-only rows.

### Medium: Two documented observed values do not match release evidence

* The Yukon route road time is documented as 30.0 minutes, while the final
  analysis artifact records 30.8 minutes (1,845 seconds)
* The Lake Ontario centre-cell temperature spread is documented as 3.281,
  while the final artifact records a t2m spread of 0.416 K

### Medium: The gallery tile tip overstates coverage and mislabels gray pixels

GetStartedButton says zooming and panning reveals all available tiles and that
gray tiles represent clouds. MapView caps rendered STAC items at 50 in multiple
paths. The final MODIS thermal-anomaly browser evidence describes visible gray
triangles as excluded-data or tiling artifacts, not clouds. The global tip can
therefore cause a first-time user to misread no-data or partial coverage.

### Low: The public evidence table is only partly self-verifying

The three linked final JSON artifacts bind the API and frontend release and
record current GeoFM replica counts. They do not contain the forecast-adapter
revision or digest, the local test counts, or an approval/submission audit
record. Those claims appear in .azure/deployment-plan.md, but the playbook does
not link that source. In particular, zero active replicas does not by itself
prove that no work was approved or submitted.

### Verified items

* The playbook contains 26 fenced prompts, and every prompt is an exact,
  case-sensitive match for canadianExamples.ts
* The release totals agree across the artifacts: 32 Setup rows with 30 passes
  and 2 MPC Pro blocks; 32 analysis rows with 24 passes and 8 prerequisite
  blocks; 12 Image Analysis rows with 12 passes
* Building Damage is disabled when MPC Pro is false, Site Intel is disabled
  when Fabric is false, Forecast is disabled when weather is false, and
  Resilience analysis is correctly sign-in gated in the release evidence
* Chat Setup routing creates a new web session and omits stale map context,
  module, pin, mobility pins, GEOINT mode, and prior message history
* The maximum browser pin deviation is 0.41 km, the maximum evidence-centre
  deviation is 0.52 km, and every captured image decodes to 1020 by 920 pixels

## Evidence Matrix

| Family                         | Setup                                         | Analysis                        | Image Analysis |
|--------------------------------|-----------------------------------------------|---------------------------------|----------------|
| Building Damage                | 0 passed, 2 MPC Pro blocked                   | 0 passed, 2 MPC Pro blocked     | Not applicable |
| Extreme Weather                | 3 passed                                      | 3 passed                        | Not applicable |
| Forecast                       | 3 passed                                      | 3 passed                        | Not applicable |
| Mobility                       | 3 passed                                      | 3 passed                        | Not applicable |
| Resilience                     | 3 passed                                      | 0 passed, 3 sign-in blocked     | Not applicable |
| Site Intel                     | 3 API passes; gallery disabled without Fabric | 0 passed, 3 Fabric blocked      | Not applicable |
| Terrain                        | 3 passed                                      | 3 passed                        | Not applicable |
| Vision - Fire and Vegetation   | 3 passed                                      | 3 raster passes                 | 3 passed       |
| Vision - Optical Imagery       | 3 passed                                      | 3 raster passes                 | 3 passed       |
| Vision - Terrain and Radar     | 3 passed                                      | 3 raster passes                 | 3 passed       |
| Vision - Water, Snow, and Ice  | 3 passed                                      | 3 raster passes                 | 3 passed       |

The artifact strings exactly match all 32 configured Setup prompts, all 32
configured analysis prompts, and all 12 configured Image Analysis prompts.
The playbook's 26 fenced prompts are also exact configured strings. README.md
contains 25 query-table rows: 19 are exact configured prompts, while the six
remaining rows are explicitly broader Raster, Comparison, or Foundation
Change examples outside the 11-family Get Started registry.

## Recommended Next Checks

* Add a browser regression that begins with loaded imagery, runs a
  navigation-only Setup, and asserts that imagery, layer selector state, and
  map context are cleared
* Recheck all local links after the intended files are staged or replace links
  to internal artifacts with published evidence targets
* Regenerate observed values from the final analysis artifact and verify the
  playbook before release
* Give no-data, cloud, and partial-coverage states distinct user guidance

## Clarifying Questions

None.

## Status

Complete. Not approved because the current Setup behavior contradicts the
documented location-reset contract and publication-critical link targets are
untracked.
