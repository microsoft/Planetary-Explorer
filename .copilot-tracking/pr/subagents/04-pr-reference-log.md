---
title: PR Reference Chunks 22-28 Review
description: Review of PR reference lines 10501-14000 for PR description generation
---

## Chunks 22-28 Review

Reviewed only pr-reference.xml lines 10501-14000. The range started inside a
lockfile diff and ended inside the PlanetaryExplorerMapIntegration.js diff, so
both boundary fragments remained partial.

### Files Changed

* Unidentified lockfile fragment (modified): upgraded transitive frontend and
  test dependencies, redirected packages to Microsoft 1ES feeds, and changed
  several integrity records. Its diff header appeared before line 10501.
* planetary-explorer/web-ui/package.json (modified): upgraded Axios; pinned
  Vite, Vitest, esbuild, and Playwright; and added security-oriented transitive
  overrides for browserslist, nanoid, picomatch, postcss, rollup, and ws.
* planetary-explorer/web-ui/src/App.tsx (modified): extended deployment feature
  state with resilience and weather flags and propagated all feature flags to
  landing, header, and map views.
* planetary-explorer/web-ui/src/components/Chat.tsx (modified): added request
  generations, abort propagation, clean Setup resets, scoped history, richer
  STAC provenance, screenshot readiness checks, and safer forecast summaries.
* planetary-explorer/web-ui/src/components/ChatHistoryDrawer.tsx (modified):
  simplified action handling and closed the drawer only after a successful load.
* planetary-explorer/web-ui/src/components/GetStartedButton.tsx (modified):
  exported deployment flags, gated unavailable workflows, forced MPC Pro for
  building-damage Setup, and disabled map-only follow-up actions on the landing
  page.
* planetary-explorer/web-ui/src/components/Header.tsx (modified): passed
  deployment flags into Get Started.
* planetary-explorer/web-ui/src/components/IntelligentLandingPage.tsx
  (modified): routed landing queries through sendChatMessage and supplied a
  geocopilot fallback redirect.
* planetary-explorer/web-ui/src/components/LandingPage.tsx (modified): passed
  feature flags and requested STAC mode through Get Started and corrected hover
  targeting to currentTarget.
* planetary-explorer/web-ui/src/components/MainApp.tsx (modified): made Setup
  clear all analysis and map context, applied requested STAC mode, and prevented
  unavailable modules from being restored from chat history.
* planetary-explorer/web-ui/src/components/MapLayerSelector.css (added): styled
  responsive map-layer visibility and opacity controls.
* planetary-explorer/web-ui/src/components/MapLayerSelector.tsx (added): added
  an accessible layer dialog with visibility toggles, opacity sliders, Escape
  handling, and focus restoration.
* planetary-explorer/web-ui/src/components/MapView.tsx (modified): added layer
  controls, deployment-aware module gating, Setup cleanup, stale-work guards,
  STAC provenance, render-profile restoration, and map expansion fixes.
* planetary-explorer/web-ui/src/components/PlanetaryExplorerMapIntegration.js
  (modified, partial): added the Microsoft MIT header and began removing the
  legacy constructor and heuristic text-response parser. Replacement behavior
  continued beyond line 14000.

### Technical Details

* Upgraded the frontend dependency baseline and pinned patched transitive
  packages, which appeared intended to stabilize builds and address dependency
  advisories.
* Reworked Get Started Setup as a context boundary. It aborted active requests,
  invalidated old generations, denied superseded destructive confirmations,
  reset chat-history retry state, removed stale layers and markers, and started
  a new web session before submitting the Setup query.
* Propagated AbortController signals through terrain, comparison, mobility,
  building-damage, extreme-weather, resilience, site-audit, forecast, and
  general chat paths. Generation checks then discarded late traces, responses,
  screenshots, map renders, and errors from superseded work.
* Scoped saved chat messages to the active conversation and persisted bounded
  scene references, STAC mode, render-profile ID, and original search datetime.
  History restoration also filtered modules against current deployment flags.
* Preserved complete STAC asset metadata for downstream sampling and carried
  public or Pro provenance through tile and item context. Building-damage calls
  additionally received current collection and STAC items.
* Waited up to ten seconds for screenshot imagery before image analysis and
  returned a clarification when the map capture was not ready.
* Distinguished native weather-model results from adapter-backed provider
  contracts, displayed underlying NWP sources, included units in statistics,
  and suppressed aggregation when providers returned mixed units.
* Added cross-provider layer controls for Azure Maps and Leaflet imagery plus
  PlanAura GeoFM overlays. Style reloads restored overlays, no-tile responses
  removed stale rasters, and expansion searches retained the original datetime
  while advancing the searched bounds.
* Disabled Building Damage, Site Intel, Resilience, and Forecast controls when
  their MPC Pro, Fabric, resilience, or weather capabilities were absent. The
  UI copy no longer promised specific weather providers unless configured.
* Replaced the intelligent landing routeQuery call with the common chat endpoint
  and retained navigation through a generated fallback URL.

### Notable Patterns

* Diff comments grounded the primary rationale in stale React closures, late
  asynchronous results, context leakage between Setup workflows, style-reload
  layer loss, and inaccurate provider or imagery claims. No commit metadata was
  present inside the assigned range.
* Automatically denying pending confirmations during Setup reduced the risk of
  approving a destructive action against superseded context.
* Deployment flags only gated frontend controls. Backend authorization still
  needed to enforce MPC Pro imagery access and Fabric-backed capabilities.
* Full asset-object projection and persisted scene references warranted review
  to ensure private MPC Pro signed URLs, credentials, or tenant metadata were
  stripped before chat-history storage, telemetry, or model submission.
* The lockfile fragment resolved packages through Microsoft 1ES feeds and used
  SHA-1 integrity values. This could reduce install portability outside the
  authenticated feed and merited supply-chain policy confirmation.
* New AbortSignal parameters required compatible service signatures across all
  affected API helpers. The landing-page endpoint change also depended on the
  chat response preserving redirect-compatible fields.
* Removing the ChatHistoryDrawer busy guard allowed overlapping actions despite
  retaining actionKey state, which could reintroduce duplicate open, export,
  rename, or delete requests under rapid interaction.
* The range showed regenerated dependency resolution and upgraded Vitest and
  Playwright tooling, but it contained no test files, test execution output,
  build result, or explicit verification record.
* MapLayerSelector.css and MapLayerSelector.tsx lacked a final newline in the
  diff, a minor formatting compatibility issue for repository linting.
