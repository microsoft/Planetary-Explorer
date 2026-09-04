---
title: Thunder Bay Frontend Workflow Research
description: Accessible interaction path and blockers for the Thunder Bay Foundation Change workflow
ms.date: 2026-09-01
ms.topic: reference
---

## Status

Complete

## Research questions

* What exact accessible names and visible text drive the Thunder Bay workflow from loaded HLS imagery through Foundation Change selection, pin placement, PlanAura submission, and approval-card rendering or denial?
* What is the minimum browser interaction sequence supported by the current implementation and tests?
* What implementation or test conditions are likely to block the workflow?

## Scope

* `planetary-explorer/web-ui/src/components/MapView.tsx`
* Geoint module controls and their tests
* `planetary-explorer/web-ui/src/components/Chat.tsx`
* `planetary-explorer/web-ui/src/components/trace/ConfirmationCard.tsx`
* Relevant frontend tests

## Findings

### Exact UI contract

The loaded Thunder Bay image is identified by the visible legend text `HLS
fire false colour`. The optional layer button and dialog both have the
accessible name `Map layers`. When that dialog is open, the imagery controls
have these names:

* Button: `HLS fire false colour visibility`
* Slider: `HLS fire false colour opacity`

The map is a `region` named `Interactive map`.

The GEOINT launcher is a clickable `div` with the title `Geointelligence
Modules`. It has no button role or keyboard focus. Its menu repeats the visible
heading `Geointelligence Modules`. The Foundation Change card is another
clickable `div`, with these exact visible strings:

* `Foundation Change`
* `PlanAura contextual change from one HLS view and two dates`

Selecting it produces this chat message:

```text
Foundation Change selected. Click the map to set the analysis area, load an HLS view, then ask PlanAura to compare two ISO dates (for example, 2026-07-17 and 2026-08-18). The app resolves a same-tile pair at the pin; GPU work still requires your approval.
```

The map click stores a pin but does not submit GeoFM work. At the documented
Thunder Bay point, the stable chat text is:

```text
Analysis area set at (50.2680°, -89.8572°)

Ask PlanAura to compare two ISO dates. The app will resolve a same-tile HLS pair here before showing the approval card.
```

The map also shows a six-decimal coordinate indicator and visible `Clear`
text. `Clear` is a clickable `span`, not a button. Small projection differences
can make the six-decimal display differ by one unit, as in the captured
`50.268001°, -89.857200°` application state.

In Foundation Change mode, the chat `textarea` has no explicit accessible
label or `aria-label`. Its exact placeholder is `Ask PlanAura to compare
2026-07-17 and 2026-08-18...`. The submit button is named `Send`; pressing
Enter without Shift invokes the same submit handler. While the streamed turn
is pending, the submit control becomes a button with accessible name `Stop
generating` and visible text `Stop`.

A real PlanAura confirmation event has `server_id=geofm`,
`tool=geofm_compare_epochs`, and `tier=write`. It renders an `alertdialog`
whose accessible name is:

```text
WRITE action — approval required
```

Its stable visible body is `Agent wants to call geofm_compare_epochs on
geofm.` The details summary is dynamically rendered as `arguments (N keys)`;
the captured Thunder Bay request says `arguments (4 keys)`. The buttons are
named `Approve` and `Deny`. During a denial request, `Deny` changes to
`Denying…` and both buttons are disabled.

Clicking `Deny` POSTs `{ approved: false }`, removes the card after a successful
broker response, and prevents the underlying `geofm_compare_epochs` call. The
trace result uses `error=denied_by_user`. The tool-level error is `GeoFM
submission was not approved.` Final assistant prose can vary because it is
model-generated.

After an approved and completed run only, the map exposes the visible layer
`PlanAura contextual change`, with controls named `PlanAura contextual change
visibility` and `PlanAura contextual change opacity`. A denied request cannot
produce this layer.

### Minimum browser sequence

Starting with the HLS image already loaded and centered on the documented
point:

1. Click the element with title `Geointelligence Modules`.
2. Click exact visible text `Foundation Change`.
3. Click near the center of the `Interactive map` region, corresponding to
	 `50.2680, -89.8572`.
4. Confirm visible text `Analysis area set` near those coordinates.
5. Fill the only chat `textarea` with the exact comparison prompt and press
	 Enter, or click `Send`:

	 ```text
	 Use PlanAura to compare HLS S30 on 2026-06-01 and 2026-07-04 at the pinned Thunder Bay 36 fire area. Use threshold 0.05 and return up to 10 change features.
	 ```

6. Wait for the `alertdialog` named `WRITE action — approval required` and
	 confirm its body names `geofm_compare_epochs` and `geofm`.
7. Optionally expand `arguments (4 keys)` to inspect the signed request.
8. Click the button named `Deny`. Do not click `Approve` or `Stop`.

If imagery is not already loaded, first fill the chat `textarea` with the
following query and submit it with Enter or `Send`:

```text
Show HLS S30 fire false-colour imagery at latitude 50.2680 and longitude -89.8572 on 2026-07-04
```

Wait for `HLS fire false colour` before opening the module picker. Loading via
the Get Started STAC path after module selection clears non-Resilience GEOINT
state, so the load-first ordering is the reliable path.

### Test coverage

Frontend tests cover separate slices, not the complete browser workflow:

* `GeointModulesFlow.test.tsx` opens the picker by title, selects Foundation
	Change by text, invokes a mocked map click at `50.4452, -104.6189`, confirms
	the pin callback and `Analysis area set`, and asserts that pin placement does
	not call `triggerGeointAnalysis`
* The same file tests the Thunder Bay-shaped HLS response, the `HLS fire false
	colour` layer at 85% opacity, failed TileJSON behavior, saved render-profile
	restoration, and a synthetic completed `PlanAura contextual change` layer
* `api.modelSelection.test.ts` verifies that a chat request serializes
	`geoint_module: foundation_change`, but does not cover the pin, map context,
	stream, or confirmation
* `ConfirmationCard.test.tsx` covers approve, deny, expired, and network-error
	branches in isolation, using `mpc_pro` and `ingest_stac_item` rather than the
	real GeoFM server and tool
* `api.streaming.test.ts` covers split trace events, bearer retry, and abort,
	but has no frontend test for `confirm_request` or `confirm_resolved`
* The Python browser check covers a Toronto STAC query and legend only. There
	is no Playwright test for Thunder Bay, module selection, pinning, chat
	submission, confirmation rendering, or denial

Backend tests independently confirm that `geofm_compare_epochs` is a WRITE
tool, a denial never reaches the underlying client, and a `confirm_request`
precedes the final streamed query result. Backend dispatch tests use the
Thunder Bay pin, but they are not browser tests.

### Likely blockers

* Pointer-only controls block a keyboard-only flow. The GEOINT launcher,
	Foundation Change card, map pin placement, and pin `Clear` control lack
	button semantics and keyboard handlers.
* The chat `textarea` has only a placeholder, so it has no durable explicit
	accessible name. Tests and automation must locate it by placeholder, element
	type, or surrounding CSS.
* The map cannot accept coordinates through an accessible field. Browser
	automation must translate the loaded map center into a pointer click; exact
	six-decimal text is not stable enough for an assertion.
* GeoFM must be enabled and connected. The optional `Foundation Models` button
	should open the `Geospatial Foundation Models` dialog showing `MCP
	connected`, `NRCan/Planaura-1.0`, and `Epoch comparison`. `MCP unavailable`,
	`Not enabled`, or no advertised model prevents a useful comparison.
* The current collection must be `hls2-s30` or `hls2-l30`. The dates must be
	ISO dates, ordered before/after, and seasonally aligned within 45 days. Both
	dates must resolve to the same HLS tile.
* Preflight happens before the card. No card appears when a pair lacks the
	required HLS assets/Fmask, either epoch falls below 70% valid context, or
	the pinned AOI contains no valid PlanAura output pixels.
* A failed TileJSON fetch removes the frontend imagery layer and `Map layers`
	control. This blocks visual verification even though backend catalog
	inference can sometimes still identify HLS from Foundation Change context.
* The confirmation broker is process-local, defaults to a 120-second timeout,
	and depends on sticky-session affinity. The checked infrastructure enables
	sticky sessions, but missing affinity or expiry can make resolution return
	false.
* `MCP_REQUIRE_CONFIRM=0` auto-approves WRITE tools and produces no card. A
	denial test must not run against an environment configured this way.
* Clicking `Stop` while the card is pending aborts the query and clears all
	pending cards; it is not equivalent to `Deny`.
* The expired-card unit test is not representative of Chat integration. The
	card sets `This confirmation already expired.` and immediately calls the
	parent resolution callback; Chat then unmounts it, so the warning can be
	transient or invisible.
* The component tests use `fireEvent` on non-semantic `div` controls. They can
	pass while keyboard accessibility and real map hit-testing remain broken.

## Evidence

* `planetary-explorer/web-ui/src/components/MapView.tsx`
* `planetary-explorer/web-ui/src/components/MainApp.tsx`
* `planetary-explorer/web-ui/src/components/MapLayerSelector.tsx`
* `planetary-explorer/web-ui/src/components/Chat.tsx`
* `planetary-explorer/web-ui/src/components/trace/ConfirmationCard.tsx`
* `planetary-explorer/web-ui/src/components/FoundationModelsInfo.tsx`
* `planetary-explorer/web-ui/src/components/__tests__/GeointModulesFlow.test.tsx`
* `planetary-explorer/web-ui/src/components/__tests__/FoundationModelsInfo.test.tsx`
* `planetary-explorer/web-ui/src/components/trace/__tests__/ConfirmationCard.test.tsx`
* `planetary-explorer/web-ui/src/services/__tests__/api.modelSelection.test.ts`
* `planetary-explorer/web-ui/src/services/__tests__/api.streaming.test.ts`
* `planetary-explorer/container-app/agents/analyst_agent/tools.py`
* `planetary-explorer/container-app/mcp_runtime/confirm_bus.py`
* `planetary-explorer/container-app/mcp_runtime/traced_client.py`
* `planetary-explorer/container-app/tests/test_query_stream.py`
* `planetary-explorer/container-app/tests/test_framework.py`
* `documentation/geofm-thunder-bay-fire.md`
* `documentation/images/geofm-thu036/02-thu036-approval.png`
* `scripts/verify_canadian_demo_browser.py`

## Follow-on questions

No further research is required to describe the current interaction contract.
Implementation work should add a real browser test and repair the inaccessible
controls before treating this path as an accessibility-supported workflow.

## Clarifying questions

None at this stage.
