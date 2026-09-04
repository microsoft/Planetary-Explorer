---
title: Get Started First-Time Reader Test
description: Source-grounded final review of the README and Get Started playbook
author: GitHub Copilot
ms.date: 2026-09-02
ms.topic: reference
---

## Research Questions

* Do README.md and documentation/get-started-playbook.md accurately reflect every material status, prompt, numeric example, prerequisite, safety statement, and 11-family coverage claim in the named final-release evidence?
* Are blocked workflows described honestly, and do runnable instructions match the controls implemented by GetStartedButton.tsx and MapView.tsx?
* Are GPP grounding, Norman Wells longitude, Building Damage gating, Site Intel/Fabric gating, Resilience sign-in, forecast providers, static DEM dates, Yukon coordinates, and GPU safety stated accurately?

## Required Evidence

* README.md
* documentation/get-started-playbook.md
* planetary-explorer/web-ui/src/config/canadianExamples.ts
* .copilot-tracking/get-started-validation/setup-results-final-release.json
* .copilot-tracking/get-started-validation/analysis-results-final-release.json
* .copilot-tracking/get-started-validation/image-analysis-final-release/results.json
* .azure/deployment-plan.md, Get Started section
* planetary-explorer/web-ui/src/components/GetStartedButton.tsx
* planetary-explorer/web-ui/src/components/MapView.tsx

## Findings

### Medium: Site Intel setup is not gallery-runnable in the validated deployment

The playbook frames all 30 passing setup rows as runnable Get Started actions
and labels Site Intel as "Setup passed; analysis blocked." The release artifact
does contain three passing Site Intel navigation rows, including Edmonton, but
the same artifact records `fabric: false`. GetStartedButton disables the whole
Site Intel selector when Fabric is false, and MapView also blocks selection.
A first-time user therefore cannot open those three Setup cards in the deployed
gallery. Only 27 passing setup actions are gallery-reachable; the other three
are API-verifier passes. The playbook should qualify the 30-pass claim and Site
Intel row as API-level validation, or describe the whole Site Intel family as
UI-disabled until Fabric is enabled.

Evidence:

* documentation/get-started-playbook.md:18-28, 98, 378-399
* .copilot-tracking/get-started-validation/setup-results-final-release.json:4-12, 820-849
* planetary-explorer/web-ui/src/components/GetStartedButton.tsx:41-52, 247-253
* planetary-explorer/web-ui/src/components/MapView.tsx:5134-5143, 6833-6849

### Low: Yukon elapsed time does not match the final-release artifact

The recommended table says the complete Yukon two-point evidence passed in
6.3 seconds. The final-release analysis row records 6,808 ms end to end and
6,165 ms inside `analyze_two_point_traverse`; neither rounds to 6.3 seconds.
All route values and coordinates otherwise match.

Evidence:

* documentation/get-started-playbook.md:94
* .copilot-tracking/get-started-validation/analysis-results-final-release.json:1741-1767

### Low: Building Damage omits the hard zoom threshold

The playbook says to zoom to individual buildings, but MapView rejects a
Building Damage pin below zoom 16. GetStartedButton's enabled-state directions
also omit this threshold. This is not currently runnable because MPC Pro is
disabled, but it is a concrete prerequisite once the family is enabled.

Evidence:

* documentation/get-started-playbook.md:350-376
* planetary-explorer/web-ui/src/components/GetStartedButton.tsx:605-647
* planetary-explorer/web-ui/src/components/MapView.tsx:5782-5793

### Low: README Mobility prompt is not the validated canonical prompt

README adds "Yukon" after the year. The TypeScript gallery, playbook, and final
analysis artifact all use the same prompt without that word. The variant is
plausible, but it is not the exact release-validated string presented by the
other three sources.

Evidence:

* README.md:111
* planetary-explorer/web-ui/src/config/canadianExamples.ts:101-106
* documentation/get-started-playbook.md:271-274
* .copilot-tracking/get-started-validation/analysis-results-final-release.json:1741-1756

## References And Evidence

### Confirmed release claims

* The setup matrix contains 32 rows: 30 pass and two Building Damage rows block at zero elapsed milliseconds because MPC Pro is disabled.
* The analysis matrix contains 32 rows: 24 pass and eight block, comprising two Building Damage MPC Pro gates, three Site Intel Fabric gates, and three Resilience sign-in gates.
* The matrix has 11 distinct families. Building Damage has two locations; each other family has three. The playbook recommends exactly one row per family.
* All 26 runnable text prompts in the playbook match a canonical TypeScript prompt value exactly.
* All 12 browser Image Analysis rows pass with 1020 by 920 decoded images. The maximum UI pin error is 0.41 km, maximum evidence-centre error is 0.52 km, and minimum layer pixel delta is 26.66%.
* GPP grounding is honest: the image has one sampled colour bin, zero luminance variance, and the response explicitly says the image is deep, uniform purple, names GPP, and does not claim NPP.
* Norman Wells remains west of Greenwich in every artifact: setup/raster use longitude -126.832 and browser Image Analysis uses -126.85.
* Calgary, Regina, Quebec City, Red River, Metro Vancouver, Yukon, Toronto, and Lake Ontario numeric evidence matches the final artifacts, apart from the Yukon elapsed-time finding above.
* Copernicus DEM is correctly identified as static and dated 2021-04-22 even where the planning question says 2026.
* Forecast correctly names the two successful providers, `aurora-1.x` and `earth2-fcn`, records no failures, and does not claim MAI Weather was configured. The `t2m` spread is 3.281.
* Building Damage is disabled in both gallery and map controls when MPC Pro is false. Resilience remains selectable because its feature flag is true, then the final analysis matrix blocks it at sign-in. These two gate descriptions are honest.
* Vision, Terrain, Mobility, Extreme Weather, Forecast, and Resilience control sequences match the code. Vision analysis buttons are deferred until map view; Terrain and Mobility pin placement wait for the user's exact question; Forecast and Site Intel retain pin context; Resilience is region-scoped and does not require a pin.
* GPU safety matches the deployment plan: no GeoFM approval or request was submitted, and the worker had zero active replicas.

### Primary source ranges

* .azure/deployment-plan.md:13-100
* .copilot-tracking/get-started-validation/setup-results-final-release.json:1-12, 275-379, 457-652, 742-906, 1020-1035
* .copilot-tracking/get-started-validation/analysis-results-final-release.json:51-86, 159-301, 411-479, 1741-1895, 2419-2580, 2658-2787, 2913-2926
* .copilot-tracking/get-started-validation/image-analysis-final-release/results.json:1-17, 294-351, 424-478, 650-686

## Follow-On Questions

No additional research is required for the requested source set. A future
release reader test should repeat the disabled-family UI check after MPC Pro or
Fabric is enabled and should execute authenticated Resilience end to end.

## Clarifying Questions

None.
