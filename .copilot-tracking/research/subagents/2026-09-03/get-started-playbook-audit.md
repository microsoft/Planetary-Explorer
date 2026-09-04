---
title: Get Started Publication Audit
description: Evidence log for the first-time operator review of the Get Started documentation and README.
ms.date: 2026-09-03
ms.topic: reference
---

## Research scope

Audit `documentation/get-started-playbook.md` and `README.md` against the
current UI configuration, interaction implementation, verifier scripts, and
specified hardened-release proof files.

## Questions

* Do the publications cover all 11 example families with exact prompts and controls?
* Are location reset behavior, prerequisite gates, and safety limits described accurately?
* Do release identifiers, hashes, counts, and observed values match the proof artifacts?
* Is source and provenance wording supported by runtime behavior and proof?
* Are local and production verifier instructions accurate and clearly separated?
* Do all publication-relative links resolve, with no links into `.copilot-tracking`?

## Findings

### Blocker: The local-only browser command can call a remote API

The playbook calls the default Image Analysis command local-only because its
configured app and API origins are loopback. The verifier checks only those
option values. Its request matcher accepts any POST whose pathname is
`/api/query` or `/api/query/stream`; it does not compare the captured request
origin with `--api-base-url`. The local frontend gets its actual API origin
from `VITE_API_BASE_URL`, and `--api-base-url` is otherwise unused during an
unbound local browser run.

A loopback Vite page built or started with a production API origin can
therefore execute all 12 analyses against production without
`--allow-production` or release-binding arguments. The same omission means a
remote browser matrix does not prove that browser traffic reached the API
revision recorded in its `release` object. The final browser JSON records the
app URL and independently verified release metadata, but not the actual
request URL.

### Blocker: Publication targets are not tracked by Git

All relative targets resolve in the working tree, and neither publication
contains a `.copilot-tracking` reference. However, Git reports these required
publication files as untracked:

* `documentation/get-started-playbook.md`
* `scripts/verify_get_started_image_analysis.mjs`
* `scripts/verify_get_started_scenarios.py`

README.md links the first two, and the playbook tells operators to execute both
verifiers. A reader of the committed repository would receive a broken
playbook link and would not have either release verifier.

### Medium: Two observed values are stale after the hardened rerun

The playbook reports a Yukon road time of 30.8 minutes. The specified hardened
analysis artifact records 1,813 seconds and 30.2 minutes. The playbook also
reports a Lake Ontario centre-cell temperature spread of 0.416 K. The hardened
artifact exposes a two-provider `t2m` spread of 2.113 K and contains no
centre-cell field supporting 0.416 K. Both published values match an older
`analysis-results-final-release.json`, not the named hardened artifact.

### Medium: First-launch Building Damage drops the forced Pro mode

The Building Damage Setup card calls `handleStacQueryClick` with a requested
mode of `pro`. In the map view, that value is dispatched in the Setup event.
On the landing page, `onQuerySelect` receives only the query string and the
handler returns before dispatching `stacMode`. App state defaults to `public`,
and the initial Chat request uses that ambient value.

The natural-language phrase may still route to MPC Pro in the backend, but the
first-time path no longer has the deterministic Pro override used by the map
view. This gated path is not exercised by the final proof because MPC Pro was
disabled. The playbook should either require selecting the MPC Pro toggle
before launching from the landing page or the callback contract should carry
the requested mode.

### Low: Clean-checkout verifier prerequisites are incomplete

The inventory command shells out to Node and calls `require('esbuild')`, so it
requires installed web UI dependencies. The browser verifier also shells out
to Python and loads `playwright` from the web UI, but Playwright is not declared
in `package.json` or the lock file. The playbook says Node Playwright is
required but provides no install or Chromium setup step. Both bare commands can
therefore fail for a first-time operator on a clean checkout before validation
starts.

### Low: Two exact assurance claims exceed the named proof fields

The 597 backend, 160 frontend, 49 Python verifier, 8 browser-semantic, and 1
weather-adapter totals are recorded in `.azure/deployment-plan.md`. The exact
unfiltered result of 644 passes, 1 skip, and 6 baseline mismatches appears only
in the two publications, not in the specified proof JSON or deployment record.
Likewise, the JSON proves zero minimum and active GeoFM replicas, but it has no
approval or submission audit field. Zero active replicas alone does not prove
that no work was approved or submitted.

## Evidence

### Verified publication content

* The TypeScript catalog contains 32 scenario rows across 11 families. Building
  Damage has two rows; every other family has three.
* All 26 fenced playbook prompts match canonical TypeScript strings exactly,
  including case and punctuation.
* All 32 setup prompts, 32 analysis prompts, and 12 Image Analysis prompts in
  the specified final artifacts match canonical TypeScript strings exactly.
* The setup artifact contains 30 passes and 2 MPC Pro blocks. The analysis
  artifact contains 24 passes and 8 prerequisite blocks: 2 Building Damage, 3
  Site Intel, and 3 Resilience. The browser artifact contains 12 passes.
* API, weather, and frontend revision IDs, image digests, deployment ID, bundle
  name, bundle SHA-256, health, traffic, and zero-replica values agree across
  the publications and all four final proof files.
* The browser artifact confirms a 0.41 km maximum pin deviation, 0.52 km maximum
  evidence-centre deviation, 1020 by 920 decoded images, and one grounded
  uniform thematic image.
* Current MapView code clears rendered raster and vector layers, collection
  state, pins, modules, screenshots, comparison state, and analysis sessions on
  a Get Started Setup. A regression test covers navigation-only Setup after
  imagery is loaded.
* Control names, source chips, tool chips, feature gates, static DEM caveat,
  climate provenance, forecast provider provenance, and operational safety
  limits otherwise agree with current code and proof.
* Every relative link resolves in the working tree. Neither publication links
	to `.copilot-tracking`.

### Primary references

* `README.md`
* `documentation/get-started-playbook.md`
* `planetary-explorer/web-ui/src/config/canadianExamples.ts`
* `planetary-explorer/web-ui/src/components/GetStartedButton.tsx`
* `planetary-explorer/web-ui/src/components/MapView.tsx`
* `planetary-explorer/web-ui/src/components/Chat.tsx`
* `planetary-explorer/web-ui/src/config/api.ts`
* `scripts/verify_get_started_scenarios.py`
* `scripts/verify_get_started_image_analysis.mjs`
* `scripts/verify_canadian_demo_browser.py`
* `.copilot-tracking/get-started-validation/setup-results-hardened-release.json`
* `.copilot-tracking/get-started-validation/analysis-results-hardened-release.json`
* `.copilot-tracking/get-started-validation/image-analysis-hardened-final-release/results.json`
* `.copilot-tracking/get-started-validation/image-analysis-hardened-sydney-probe/results.json`
* `.azure/deployment-plan.md`

## Follow-on questions

* Add a verifier regression with a loopback app URL and remote
  `VITE_API_BASE_URL`; require rejection before the first POST.
* Add a landing-page Building Damage test that asserts the initial request uses
  `stac_mode: pro`.
* Persist the unfiltered backend test summary and GeoFM approval/submission
  audit result in a release record if those exact assurances remain public.

## Status

Complete. Not approved because the browser verifier can bypass the documented
production gate and required publication targets are untracked.
