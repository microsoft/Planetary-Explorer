---
title: Get Started Scenario Inventory
description: Evidence-backed inventory of prompts exposed by the deployed frontend Get Started experience
ms.date: 2026-09-01
ms.topic: reference
---

## Research scope

* Inventory every scenario and prompt exposed by the frontend Get Started experience
* Identify the source file and scenario or module grouping
* Capture exact prompt templates and location or date assumptions
* Trace the expected backend route, task, or tool
* Record existing documentation and test coverage
* Flag scenarios that may trigger billed, state-changing, or destructive work, especially GeoFM
* Map the exact Terrain, Mobility, Extreme Weather, and Building Damage
  frontend-to-backend request contracts
* Identify each HTTP method, request body, required setup state or pins, and
  observable success indicators
* Define safe local or direct-API validation that does not invoke production
* Identify blockers in the currently deployed public-demo configuration

## Focused contract research status

Status: Complete

Questions investigated:

* Which frontend event and state branch dispatches each scenario request?
* What endpoint, method, and JSON body does each branch send?
* Which setup result, active module, loaded layers, map state, or pins are
  required before dispatch?
* Which HTTP fields, stream events, UI messages, layers, or map overlays prove
  success?
* Which tests cover the transport, prerequisites, and success handling?
* Which public-demo feature flags, credentials, data sources, or deployment
  settings are likely to block each path?
* How can each contract be validated locally or against a non-production API
  without triggering billed or state-changing work?

Verified so far:

* In the entered app, every Setup button dispatches
  `planetaryexplorer-stac-query`. `Chat.tsx` turns that event into a streamed
  generic query through `POST /api/query/stream`. The request body uses the
  normal `QueryRequest` shape, including `query`, `preferences`,
  `include_visualization`, `session_id`, `stac_mode`, map context when present,
  and conversation history when present.
* Setup clears the parent Chat-routing state for Terrain, Mobility, Extreme
  Weather, and Building Damage, including the current pin, Terrain session,
  and Mobility pair. It does not clear `MapView`'s internal selected-module
  display. The operator must wait for setup completion, select the intended
  module, and place its required pin or pins before clicking the question.
* The four Analyze, Ask, or Assess buttons dispatch only
  `planetaryexplorer-query` with `{ query }`. They do not select a module and
  do not carry coordinates, setup identity, or prerequisite flags.
* On the landing page, both Setup and analysis buttons call `onQuerySelect`.
  They enter the app as a generic initial query instead of preserving the
  intended module contract.
* Terrain pin placement captures a screenshot and initializes local state as
  `{ sessionId: null, lat, lng }`; it does not call the backend. The question
  then uses `POST /api/geoint/terrain/chat` with `message`, `latitude`,
  `longitude`, `radius_km: 5`, optional `session_id`, and optional
  base64-only `screenshot`.
* Mobility becomes ready only after Pin A and Pin B. The question uses
  `POST /api/geoint/mobility` with Point A as `latitude` and `longitude`, Point
  B as `latitude_b` and `longitude_b`, an augmented `user_query`, empty
  `user_context`, `stac_mode`, and an optional screenshot.
* Building Damage pin placement requires UI zoom 16 or higher. The question
  uses `POST /api/geoint/building-damage` with `latitude`, `longitude`, the
  exact scenario question as `user_query`, empty `user_context`, `stac_mode`,
  and an optional screenshot. Final dispatch does not enforce that the pin
  workflow completed.
* Extreme Weather's documented flow uses one pin. The question uses
  `POST /api/geoint/extreme-weather` with `latitude`, `longitude`, the exact
  scenario question as `user_query`, empty `user_context`, and `stac_mode`.
  Final dispatch does not enforce the pin, and `triggerGeointAnalysis`
  intentionally omits the captured screenshot for this module.
* A setup stream is transport-successful only when it emits an SSE JSON object
  with `type: "query_result"`; the frontend returns that object's `payload`.
  Terrain chat consumes top-level `response`, `session_id`, and `tool_calls`.
  Mobility and Building Damage consume `result.response`, then
  `result.summary`, then top-level `message`. Extreme Weather consumes
  `result.analysis`, then top-level `message` or `content`.

## Findings

* The current registry contains 32 scenario rows and 76 runnable prompt buttons.
  Twelve Vision rows expose setup, raster, and image-analysis prompts. The
  remaining 20 rows expose setup plus a module question.
* `planetary-explorer/web-ui/src/config/canadianExamples.ts` is the current
  prompt registry. It fixes the demo year at 2026 and the broad observation
  range at `2026-01-01/2026-08-26`.
* `planetary-explorer/web-ui/src/components/GetStartedButton.tsx` renders the
  registry and dispatches setup prompts separately from module questions.
* The deployed App Service serves `assets/index-ChGvpStQ.js`; a read-only
  bundle inspection confirmed the same 32 scenario rows, exact prompt strings,
  handlers, route branches, and missing `features` prop at both callers.
* On the landing page, all handlers defer to `onQuerySelect`, so any clicked
  prompt becomes an initial generic request through `/api/query/stream`
  without the in-app event metadata or automatic module selection.
* In the entered app, setup prompts use `/api/query/stream`, which wraps the
  buffered `/api/query` processor. Module questions use dedicated routes when
  the user first selects the instructed module and satisfies its pin or
  loaded-data prerequisites.
* GeoFM Foundation Change is not a Get Started tile. It is a separate module
  in the map module picker. GeoFM submission and retry are confirmation-gated
  writes; cancellation is confirmation-gated destructive work.
* Current coverage is partial. The dynamic frontend config test enforces the
  Canadian 2026 context, and the browser verifier runs the Toronto STAC setup.
  The backend Get Started manifest and live runner contain older prompt text,
  so they do not provide exact-string coverage for the full current gallery.

## Focused frontend-to-backend contract

### Common Setup request

In the entered app, all 11 focused scenarios send Setup through the same path:

```text
GetStartedButton.handleStacQueryClick
  -> planetaryexplorer-stac-query { query, clearSessions: true }
  -> Chat.pendingQuery
  -> apiService.sendChatMessage with streaming handlers
  -> POST /api/query/stream
```

The minimum fresh-session request generated by the frontend is:

```json
{
  "query": "<exact setupQuery>",
  "preferences": {
    "interface_type": "planetary_explorer",
    "data_source": "planetary_computer"
  },
  "include_visualization": true,
  "session_id": "<conversation ID or web-session timestamp>",
  "stac_mode": "public",
  "geoint_mode": false
}
```

The frontend can also add `model`, `reasoning_effort`, `geoint_module`, pin and
map fields, and `conversation_history` when those values exist. On the
documented Setup-first path, the parent module, current pin, Terrain session,
and Mobility pair are cleared before dispatch, so `geoint_module` and `pin`
should be absent and `geoint_mode` should be false.

The stream must contain a JSON SSE data object with `type: "query_result"`.
Its `payload` is the same response body returned by buffered `POST /api/query`.
The frontend treats a stream with no terminal `query_result` as an error.

Setup success then splits by scenario type:

| Scenario setup type | Required payload indicators | Visible frontend indicator |
|---------------------|-----------------------------|----------------------------|
| Bare place used by Mobility and Extreme Weather | HTTP 200, `success: true`, `action: "navigate_to"`, and a usable `navigate_to.bbox` or latitude/longitude | Map camera moves to the requested region; no imagery layer is expected |
| Public imagery used by Terrain | HTTP 200, `success: true`, nonempty `data.stac_results.features`, and a usable `translation_metadata.mosaic_tilejson.tilejson_url` or `translation_metadata.all_tile_urls` | The map creates `satelliteData` and exposes a rendered imagery layer |
| Private imagery required by Building Damage | All imagery indicators above, plus `data_source: "MPC Pro"`, `debug.stac_routing.is_pro: true`, and tenant collection coverage | Source chip identifies MPC Pro and the high-resolution layer renders |

An HTTP 200 or `success: true` with zero STAC features is not setup success for
Terrain or Building Damage.

### Dedicated analysis requests

| Module | Effective endpoint | Hard frontend dispatch gate | Backend-required fields |
|--------|--------------------|-----------------------------|-------------------------|
| Terrain | `POST /api/geoint/terrain/chat` | `terrainSession` exists after one Terrain pin click and Terrain remains selected | Nonempty `message`, valid `latitude`, valid `longitude` |
| Mobility | `POST /api/geoint/mobility` | Mobility is selected and both `mobilityPinCoords.pinA` and `pinB` exist | Valid Point A `latitude` and `longitude`; Point B is optional to the backend but required by this frontend flow |
| Building Damage | `POST /api/geoint/building-damage` | Building Damage is selected; no pin is enforced in `Chat.tsx` | Valid `latitude` and `longitude` |
| Extreme Weather | `POST /api/geoint/extreme-weather` | Extreme Weather is selected; no pin is enforced in `Chat.tsx` | Valid `latitude` and `longitude` |

Terrain sends this body on the first scenario question. `session_id` is omitted
until the backend returns one. The screenshot is base64 without a data-URL
prefix.

```json
{
  "message": "<exact Terrain question>",
  "latitude": "<Terrain pin latitude>",
  "longitude": "<Terrain pin longitude>",
  "radius_km": 5.0,
  "screenshot": "<optional base64 map capture>"
}
```

Follow-ups add `session_id`. The frontend stores a returned session ID with the
same pin coordinates. Strict success requires HTTP 200, top-level
`status: "success"`, nonempty `response`, nonempty `session_id`, and grounded
`tool_calls`. The UI only needs `response` to display a bubble, so a fallback
or agent error string can otherwise look successful.

Mobility sends this body:

```json
{
  "latitude": "<Pin A latitude>",
  "longitude": "<Pin A longitude>",
  "user_query": "<exact question> Analyze traversability from Point A (<A lat to 4 decimals>, <A lng to 4 decimals>) to Point B (<B lat to 4 decimals>, <B lng to 4 decimals>). You MUST use your satellite analysis tools (analyze_directional_mobility, detect_water_bodies, analyze_slope_for_mobility, analyze_vegetation_density, detect_active_fires) at both coordinates. Do NOT answer from general knowledge.",
  "user_context": "",
  "latitude_b": "<Pin B latitude>",
  "longitude_b": "<Pin B longitude>",
  "stac_mode": "public",
  "screenshot": "<optional base64 map capture>"
}
```

The backend ignores `stac_mode` and wraps the agent result as
`{status, result, timestamp}`. Strict success requires HTTP 200,
top-level `status: "success"`, no `result.error`, nonempty
`result.response`, matching `result.location` and `result.destination`, and a
`result.tool_calls` entry for `analyze_two_point_traverse`. The current server
instruction deliberately overrides the frontend's individual-tool demand and
requires one aggregate traverse call.

Building Damage sends this body:

```json
{
  "latitude": "<map-context pin latitude or 0>",
  "longitude": "<map-context pin longitude or 0>",
  "user_query": "<exact Building Damage question>",
  "user_context": "",
  "stac_mode": "public",
  "screenshot": "<optional base64 map capture>"
}
```

The backend ignores `stac_mode` and defaults `radius_miles` to 5. A screenshot
takes the direct GPT vision path. Strict transport success requires HTTP 200,
top-level `status: "success"`, nonempty `result.response`, no embedded error,
matching `result.location`, and grounded `result.tool_calls`. Screenshot success
uses `gpt_vision_analysis`; intended no-screenshot fallback evidence is
`assess_building_damage` plus `classify_damage_severity`. Semantic success for
these starter prompts additionally requires the Setup response to prove MPC
Pro routing and tenant before-and-after imagery. The final request itself has
only one screenshot and carries no before date, after date, item IDs, or asset
URLs.

Extreme Weather sends this body:

```json
{
  "latitude": "<map-context pin latitude or 0>",
  "longitude": "<map-context pin longitude or 0>",
  "user_query": "<exact Extreme Weather question>",
  "user_context": "",
  "stac_mode": "public"
}
```

`triggerGeointAnalysis` excludes screenshots for this module, and the backend
ignores `stac_mode`. It generates a new session ID, but the frontend does not
store it. Strict success requires HTTP 200, top-level `status: "success"`,
nonempty `result.analysis`, nonempty `session_id`, and at least one successful
`result.tool_calls` entry whose result has no `error`. Error text from the
agent can otherwise be wrapped in a successful envelope with an empty tool
list.

### Exact scenario and tool expectations

The exact Setup and question strings are in the Module inventory below. Their
analysis evidence should be checked as follows:

| Scenario | Request-specific expectation |
|----------|------------------------------|
| Terrain: Vancouver | Tool calls should include `get_elevation_analysis`, `get_slope_analysis`, `analyze_flood_risk`, and `find_flat_areas` |
| Terrain: Calgary | Tool calls should include elevation and slope evidence; no line-of-sight or viewshed tool exists in the current GEOINT implementation |
| Terrain: Halifax | Tool calls should include `analyze_flood_risk` and `analyze_environmental_sensitivity` |
| Mobility: Kananaskis | The body appends both pins; backend tool evidence should be `analyze_two_point_traverse` |
| Mobility: North Shore Mountains | The body appends both pins; backend tool evidence should be `analyze_two_point_traverse` |
| Mobility: Yukon River corridor | The body appends both pins; backend tool evidence should be `analyze_two_point_traverse` |
| Extreme Weather: Vancouver | `peak daily` marks the query as trend-like and skips the direct variable fast path; the full agent should return precipitation evidence for 2026, normally `get_precipitation_projection` |
| Extreme Weather: Toronto | `trend` skips the direct variable fast path; valid evidence can include `compute_trend`, `sample_timeseries`, or precipitation projection data, but the LLM-planned tool set is nondeterministic |
| Extreme Weather: Montreal | The route deterministically parses 2026 and calls `compare_climate_scenarios` because both SSP245 and SSP585 appear |
| Building Damage: Jasper | A valid Setup must prove an MPC Pro tenant aerial layer; final screenshot evidence uses `gpt_vision_analysis` |
| Building Damage: Lytton | A valid Setup must prove an MPC Pro tenant aerial layer; final screenshot evidence uses `gpt_vision_analysis` |

None of the four dedicated analysis responses adds a new map layer or overlay.
Their normal visible success indicator is a non-error assistant chat bubble.

## Safe validation approach

No production request is needed to validate this contract.

1. Use a frontend Vitest contract test with `apiService` mocked. Dispatch the
   same window events as Get Started, set module and pin props, and assert the
   endpoint helper arguments and rendered response bubble.
2. Use FastAPI `TestClient` locally for route-shape probes. Posting `{}` to
   each dedicated route returns a deterministic 400 before agent or data-tool
   initialization: Terrain reports missing `message`, while Mobility,
   Building Damage, and Extreme Weather report missing coordinates.
3. Use in-process mocked happy paths for valid bodies. Patch the Terrain agent,
   Mobility wrapper, Building Damage OpenAI client and agent, and Extreme
   Weather agent or fast-path tools. Assert the strict success fields above.
   This validates serialization and response handling without Foundry, Azure
   OpenAI, STAC, NetCDF, Azure Maps, private data, or billed inference.
4. Reuse `test_query_stream.py`'s fake `unified_query_processor` pattern for
   Setup. Feed one `navigate_to` payload and one nonempty STAC payload into
   the frontend map tests instead of calling a catalog.
5. If integration validation is later approved, target a local or isolated
   non-production API only. Check one request at a time and reject HTTP 200
   responses containing `error`, empty tool lists, zero imagery features, or
   fallback completion strings. Do not use the public-demo production hosts
   for this validation.

Malformed-input probes validate only route registration and field validation.
They do not validate downstream data or model availability.

## Focused test assessment

| Test or verifier | What it covers | Material gap |
|------------------|----------------|--------------|
| `web-ui/src/config/__tests__/canadianExamples.test.ts` | Every focused question contains 2026 and every scenario has Canadian context | No click, route, body, prerequisite, response, or feature-gate assertions |
| `web-ui/src/components/__tests__/GeointModulesFlow.test.tsx` | Module picker opens and Terrain selection emits `terrain`; generic Canadian pin placement | No Terrain ready state, Mobility two-pin state, Building Damage zoom gate, Extreme Weather pin, or dedicated endpoint call |
| `web-ui/src/components/__tests__/TerrainWorkflow.test.tsx` | Synthetic message arrays and formatting | Does not render current components or call the API; its Pin-to-automatic-analysis narrative no longer matches current behavior |
| `container-app/tests/test_query_stream.py` | Cached request body and terminal `query_result` SSE contract | No real Setup response or map parsing |
| `container-app/tests/test_terrain_agent_contract.py` | Terrain `analyze` delegates to `chat`; failed synthesis preserves measured evidence | No FastAPI route, request parsing, screenshot, or frontend contract |
| `container-app/tests/test_get_started_queries.py` | Generic AnalystAgent planning with mocked legacy tool names; 12 public Vision cache keys | Does not exercise any of the four dedicated endpoints, omits Building Damage, uses stale prompt text and tools such as `get_terrain_stats`, `get_mobility_path`, and `get_extreme_weather_projection` |
| `container-app/tests/test_stac_mode_routing.py` | Request mode precedence and refusal to silently fall back when Pro is unconfigured | Not connected to Building Damage Get Started rendering or feature gating |
| `scripts/verify_canadian_demo_browser.py` | Local modal inventory and Toronto public Sentinel-2 Setup | No focused module scenario |

Repository search found no test that invokes `/api/geoint/terrain/chat`,
`/api/geoint/mobility`, `/api/geoint/building-damage`, or
`/api/geoint/extreme-weather`.

## Public-demo blockers

Confirmed from current source, saved `earthcopilot` azd state, checked-in
deployment parameters, and the deployed-bundle inspection already captured in
this note:

* The saved environment is `PUBLIC_DEMO_MODE=true`. Bicep maps that state to
  `DISABLE_AUTH=true`, so anonymous API transport is not the blocker.
* `enableMpcPro` is false, `mpcProStacUrl` is empty, and the saved environment
  has no MPC Pro configuration. App starts in Public mode and blocks switching
  to Pro when `/api/config.features.mpcPro` is false.
* `GetStartedButton` declares `mpcPro` in its feature shape but never uses it
  to lock Building Damage. `Header` and `LandingPage` also omit the whole
  `features` prop. Building Damage cards are therefore always clickable even
  when the separate Pro toggle is locked.
* Building Damage Setup sends authoritative `stac_mode: "public"`. The text
  says "my MPC Pro aerial imagery", but request mode wins over prose. Public
  NAIP cannot substitute because NAIP covers the United States, not Jasper or
  Lytton. The Setup is therefore expected to clarify, return zero usable
  tiles, or load an unsuitable public source.
* The Building Damage final contract cannot express before-and-after analysis.
  It sends one current screenshot with no epoch or item identity, so a 200
  response cannot establish the promised tenant change assessment.
* Building Damage's direct fallback is broken. `fastapi_app.py` imports
  `_assess_damage_async` and `_classify_severity_async`, but those symbols do
  not exist in `geoint/building_damage_tools.py`. A failed screenshot or
  Agent Service path can therefore end as HTTP 500 instead of falling back.
* Analysis buttons do not select their module. From the landing page they
  always become generic initial queries; in-app users must complete Setup,
  select the module, place pins, and only then click the question.
* Setup clears the parent module state, but `MapView` has no listener for the
  Setup event and retains its internal selected-module display. Running Setup
  after selecting a module can leave the map looking active while Chat routes
  generically; clicking the same module then toggles it off.
* Building Damage and Extreme Weather do not hard-gate missing pins at final
  dispatch. If active without usable map context, they call their dedicated
  endpoints at `(0, 0)`, which is valid input but the wrong location.
* Mobility without both pins silently misses its dedicated branch and reaches
  generic `/api/query/stream`. Its frontend `user_query` also demands five
  individual tools while the current agent mandates one
  `analyze_two_point_traverse` call.
* The Kananaskis wording says "five elevation layers", but the traverse
  prefetches six mixed collections and only one is an elevation model. The
  expected claim is not represented by the request or response schema.
* Calgary asks for line-of-sight, but no Terrain line-of-sight or viewshed tool
  exists. Any line-of-sight conclusion is not grounded by a dedicated tool.
* Vancouver and Toronto climate prompts bypass the cheap single-variable fast
  path because `peak daily` and `trend` are trend keywords. The full agent sees
  a default year of 2030 and must correctly override it from prose with 2026.
  Trend sampling can read up to five remote NetCDF years and has a 180-second
  gather limit inside an endpoint budget of about 230 seconds, so cold-cache
  timeout is plausible.
* Mobility depends on Foundry Agent Service, six public STAC collection
  searches, an elevation transect, and optional Azure Maps route and weather
  calls. It has no endpoint-level direct fallback, and agent failures can be
  returned as `status: "success"` with `result.error`.
* Terrain screenshot capture explicitly documents an Azure Maps WebGL failure
  mode and advises switching to Leaflet. The direct terrain tools can still
  answer without a screenshot, but visual context is lost.
* Terrain's direct chat fallback references `_terrain_client`, which is local
  to a different endpoint. The resulting synthesis failure is caught and raw
  tool output can still be returned, so this is a quality degradation rather
  than a complete route failure.
* Mobility, Building Damage, and Extreme Weather all have success-envelope
  paths that can contain embedded error prose. Frontend completion strings and
  HTTP 200 alone are unsafe validation criteria.

## Evidence

* `planetary-explorer/web-ui/src/config/canadianExamples.ts`
* `planetary-explorer/web-ui/src/components/GetStartedButton.tsx`
* `planetary-explorer/web-ui/src/components/MainApp.tsx`
* `planetary-explorer/web-ui/src/components/MapView.tsx`
* `planetary-explorer/web-ui/src/App.tsx`
* `planetary-explorer/web-ui/src/components/Header.tsx`
* `planetary-explorer/web-ui/src/components/Chat.tsx`
* `planetary-explorer/web-ui/src/services/api.ts`
* `planetary-explorer/container-app/quickstart_cache.py`
* `planetary-explorer/container-app/fastapi_app.py`
* `planetary-explorer/container-app/geoint/terrain_agent.py`
* `planetary-explorer/container-app/geoint/terrain_tools.py`
* `planetary-explorer/container-app/geoint/mobility_agent.py`
* `planetary-explorer/container-app/geoint/mobility_tools.py`
* `planetary-explorer/container-app/geoint/building_damage_agent.py`
* `planetary-explorer/container-app/geoint/building_damage_tools.py`
* `planetary-explorer/container-app/geoint/extreme_weather_agent.py`
* `planetary-explorer/container-app/geoint/extreme_weather_tools.py`
* `planetary-explorer/container-app/geoint/netcdf_computation_tools.py`
* `planetary-explorer/infra/main.parameters.json`
* `planetary-explorer/infra/app/web.bicep`
* `.azure/earthcopilot/.env` (deployment flags inspected without copying secrets)
* `planetary-explorer/web-ui/src/config/__tests__/canadianExamples.test.ts`
* `planetary-explorer/container-app/tests/test_get_started_queries.py`
* `planetary-explorer/container-app/tests/test_query_stream.py`
* `planetary-explorer/container-app/tests/test_stac_mode_routing.py`
* `planetary-explorer/container-app/tests/test_terrain_agent_contract.py`
* `planetary-explorer/container-app/tests/live_get_started_runner.py`
* `scripts/verify_canadian_demo_browser.py`
* Deployed frontend: `https://app-earthcopilot-e1bb5a9c.azurewebsites.net`
* Deployed bundle: `https://app-earthcopilot-e1bb5a9c.azurewebsites.net/assets/index-ChGvpStQ.js`

## Source and routing map

| Responsibility | Source |
|----------------|--------|
| Canonical scenario and prompt registry | `planetary-explorer/web-ui/src/config/canadianExamples.ts` |
| Modal rendering, prompt-button behavior, and event metadata | `planetary-explorer/web-ui/src/components/GetStartedButton.tsx` |
| Landing-page callback that converts any prompt into an initial query | `planetary-explorer/web-ui/src/components/LandingPage.tsx` and `planetary-explorer/web-ui/src/App.tsx` |
| In-app prompt routing and prerequisites | `planetary-explorer/web-ui/src/components/Chat.tsx` |
| Frontend endpoint methods | `planetary-explorer/web-ui/src/services/api.ts` |
| Exact public STAC fast path for 12 Vision setup prompts | `planetary-explorer/container-app/quickstart_cache.py` and `planetary-explorer/container-app/fastapi_app.py` |

Route abbreviations used below:

* `Q-LOAD`: frontend `POST /api/query/stream`, wrapping buffered
  `POST /api/query`, with expected Layer-1 `LOAD`; the 12 exact public Vision
  setup strings bypass all GPT calls and run the cached STAC fast path
* `Q-NAV`: frontend `POST /api/query/stream`, wrapping buffered
  `POST /api/query`, with expected Layer-1 `NAVIGATE` for a bare place
* `Q-AN`: frontend `POST /api/query/stream`, wrapping buffered
  `POST /api/query`, with expected Layer-2 raster or screenshot analysis
* `T`: `POST /api/geoint/terrain/chat`
* `M`: `POST /api/geoint/mobility`
* `B`: `POST /api/geoint/building-damage`
* `E`: `POST /api/geoint/extreme-weather`
* `S`: `POST /api/sites/audit`
* `R`: `POST /api/resilience/assess/smart/stream`
* `F`: `POST /api/geoint/forecast`

## Vision inventory

Every Vision setup prompt is an exact `Q-LOAD` cache key in public mode. The
raster and image prompts use `Q-AN`, with expected tools
`sample_raster_value` and `describe_map_screenshot`, respectively. The latter
two reuse the loaded layer and pin; their year text does not initiate another
dated STAC search.

| Category and scenario | Exact setup prompt | Exact raster prompt | Exact image prompt | Location and date assumption | Risk |
|-----------------------|--------------------|---------------------|--------------------|------------------------------|------|
| Optical: Toronto | `Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26` | `Sample the 2026 red and near-infrared reflectance values at this pin.` | `Explain the colours in this 2026 Toronto image and identify visible land-cover types.` | Toronto bbox; Sentinel-2; explicit range | Public STAC read, then model/raster inference |
| Optical: Calgary | `Show HLS imagery over Calgary, Canada from 2026-05-01 to 2026-08-26` | `What is the 2026 NDVI value at this Calgary pin?` | `Describe urban growth and vegetation patterns visible around Calgary in 2026.` | Calgary bbox; HLS S30; explicit range | Public STAC read, then model/raster inference |
| Optical: Halifax | `Show Landsat imagery over Halifax, Canada from 2026-01-01 to 2026-08-26` | `Sample the 2026 coastal surface-reflectance bands at this location.` | `Identify water, urban, forest, and shoreline features in this 2026 Halifax image.` | Halifax bbox; Landsat C2 L2; explicit range | Public STAC read, then model/raster inference |
| Fire: Alberta | `Show MODIS thermal anomalies across Alberta from 2026-05-01 to 2026-08-26` | `What is the 2026 fire-confidence value at this Alberta pixel?` | `Explain the fire-intensity colours and identify clusters visible in Alberta.` | Alberta bbox; MODIS 14A1; explicit range | Public STAC read, then model/raster inference |
| Vegetation: Saskatchewan | `Show MODIS vegetation indices over Saskatchewan from 2026-04-01 to 2026-08-26` | `Sample the 2026 NDVI and EVI values at this Saskatchewan field.` | `Explain the vegetation colours and identify lower-vigour areas in 2026.` | Saskatchewan bbox; MODIS 13Q1; explicit range | Public STAC read, then model/raster inference |
| Vegetation: British Columbia | `Show MODIS gross primary productivity over British Columbia from 2026-05-01 to 2026-08-26` | `What is the 2026 gross primary productivity value at this location?` | `Explain the productivity colour scale across British Columbia.` | British Columbia bbox; MODIS 17A2H; explicit range | Public STAC read, then model/raster inference |
| Snow: Quebec | `Show MODIS daily snow cover over Quebec from 2026-02-01 to 2026-02-28` | `Sample the February 2026 NDSI value at this Quebec location.` | `Explain the snow-cover colours and identify snow-free areas in Quebec.` | Quebec bbox; MODIS 10A1; February 2026 | Public STAC read, then model/raster inference |
| Water and ice: Mackenzie River | `Show Sentinel-2 imagery along the Mackenzie River in Canada from 2026-05-01 to 2026-06-30` | `Sample 2026 water and ice reflectance at this Mackenzie River pin.` | `Identify open water, ice, snow, and land in this 2026 image.` | Mackenzie River bbox; Sentinel-2; explicit range | Public STAC read, then model/raster inference |
| Water and ice: Hudson Bay | `Show Landsat imagery of Hudson Bay, Canada from 2026-06-01 to 2026-08-26` | `Sample the 2026 water and short-wave infrared bands at this Hudson Bay pin.` | `Explain the natural-colour rendering and identify water, ice, cloud, and coast.` | Hudson Bay bbox; Landsat C2 L2; explicit range | Public STAC read, then model/raster inference |
| Terrain: Banff | `Show Copernicus DEM terrain around Banff, Canada for 2026 analysis` | `What is the elevation in metres at this Banff pin for the 2026 analysis?` | `Explain the elevation colours and identify valleys, slopes, and peaks.` | Banff bbox; static COP-DEM; 2026 is narrative | Public STAC read, then model/raster inference |
| Radar: Vancouver | `Show Sentinel-1 RTC radar imagery over Vancouver, Canada from 2026-01-01 to 2026-08-26` | `What are the 2026 VV and VH backscatter values in dB?` | `Explain the radar colours and distinguish water, vegetation, and built-up areas.` | Vancouver bbox; Sentinel-1 RTC; explicit range | Public STAC read, then model/raster inference |
| Radar: Red River | `Show Sentinel-1 RTC radar imagery over the Red River, Manitoba from 2026-03-01 to 2026-05-31` | `Sample the 2026 radar backscatter at this Red River pin.` | `Explain the radar colour composite and identify possible inundation.` | Red River bbox; Sentinel-1 RTC; explicit range | Public STAC read, then model/raster inference |

## Module inventory

These are intended in-app routes. Except for Resilience, the question button
does not activate its module. The user must follow the modal instructions and
select the module first. On the landing page, every setup or question instead
becomes a generic initial `POST /api/query/stream` request.

| Module and scenario | Exact setup prompt | Exact question prompt | Location and date assumption | Expected route and tool | Risk |
|---------------------|--------------------|-----------------------|------------------------------|-------------------------|------|
| Terrain: Vancouver | `Show Copernicus DEM elevation near Vancouver, Canada for 2026` | `For 2026, is this Metro Vancouver location suitable for a construction permit? Analyze slope, flood exposure, and flat areas.` | Vancouver; static DEM; year is narrative | `Q-LOAD` then `T`; elevation, slope, flood, and flat-area tools | Model inference plus public raster reads |
| Terrain: Calgary | `Show Copernicus DEM elevation near Calgary, Canada for 2026` | `Analyze 2026 terrain elevation, slope, and line-of-sight near Calgary at 51.0447N, 114.0719W.` | Fixed Calgary coordinates; static DEM | `Q-LOAD` then `T`; elevation and slope tools | Model inference plus public raster reads |
| Terrain: Halifax | `Show Sentinel-2 imagery over Halifax, Canada from 2026-06-01 to 2026-08-26` | `Assess 2026 coastal flood exposure, environmental sensitivity, and permitting constraints for this Halifax site.` | Halifax; explicit Sentinel-2 range | `Q-LOAD` then `T`; flood and environmental-sensitivity tools | Model inference plus public raster reads |
| Mobility: Kananaskis | `Kananaskis, Alberta, Canada` | `Using 2026 conditions, classify vehicle traversability between these pins across five elevation layers and identify steep terrain barriers.` | Bare place setup; two user pins; 2026 is narrative | `Q-NAV` then `M`; two-point traverse and mobility toolset | Model inference plus several raster calls |
| Mobility: North Shore Mountains | `North Vancouver, British Columbia, Canada` | `For a 2026 search-and-rescue plan, identify flat helicopter landing zones between these pins and explain slope and vegetation constraints.` | Bare place setup; two user pins; 2026 is narrative | `Q-NAV` then `M`; traverse, slope, and vegetation tools | Model inference plus several raster calls |
| Mobility: Yukon River corridor | `Whitehorse, Yukon, Canada` | `Assess this 2026 emergency-supply route for water crossings, wildfire exposure, steep slopes, and ground-vehicle feasibility.` | Bare place setup; two user pins; 2026 is narrative | `Q-NAV` then `M`; traverse, water, fire, slope, vegetation tools | Model inference plus several raster calls |
| Extreme Weather: Vancouver | `Vancouver, British Columbia, Canada` | `What are the projected annual precipitation and peak daily rainfall values for Vancouver in 2026?` | Bare place setup; CMIP6 point at pin; year passed by agent | `Q-NAV` then `E`; precipitation projection | Model inference plus NetCDF reads |
| Extreme Weather: Toronto | `Toronto, Ontario, Canada` | `Compute the 2026 precipitation trend for Toronto and identify the wettest projected period.` | Bare place setup; CMIP6 point at pin; year passed by agent | `Q-NAV` then `E`; precipitation/trend tools | Model inference plus NetCDF reads |
| Extreme Weather: Montreal | `Montreal, Quebec, Canada` | `What are the projected temperature and precipitation trends for Montreal during 2026 under SSP245 and SSP585?` | Bare place setup; two CMIP6 scenarios at pin | `Q-NAV` then `E`; temperature, precipitation, scenario comparison | Model inference plus multiple NetCDF reads |
| Building Damage: Jasper | `Show my MPC Pro aerial imagery over Jasper, Alberta from 2026-01-01 to 2026-08-26` | `Using the 2026 before-and-after tenant imagery, assess potential building damage and distinguish destroyed, major-damage, and unaffected structures.` | MPC Pro mode and tenant coverage required; explicit range | `Q-LOAD` in Pro mode then `B`; GPT vision or `assess_building_damage` fallback | Private data access and billed vision inference |
| Building Damage: Lytton | `Show my MPC Pro aerial imagery over Lytton, British Columbia from 2026-01-01 to 2026-08-26` | `Using the 2026 before-and-after tenant imagery, assess structural damage and identify blocks requiring field verification.` | MPC Pro mode and tenant coverage required; explicit range | `Q-LOAD` in Pro mode then `B`; GPT vision or damage-tool fallback | Private data access and billed vision inference |
| Site Intel: Calgary | `Calgary, Alberta, Canada` | `For 2026, score our candidate data-centre sites near Calgary for power, water, competition, wildfire, flood, and heat exposure.` | Bare place plus selected pin/map center; 200 MW default | `Q-NAV` then `S`; Fabric, MPC, AI Search, weather MAF graph | Multi-service billable reads and model inference |
| Site Intel: Montreal | `Montreal, Quebec, Canada` | `Which 2026 candidate parcels near Montreal clear slope, flood, heat, and grid-proximity thresholds?` | Bare place plus selected pin/map center; 200 MW default | `Q-NAV` then `S`; Fabric, MPC, AI Search, weather MAF graph | Multi-service billable reads and model inference |
| Site Intel: Edmonton | `Edmonton, Alberta, Canada` | `Rank the top three 2026 sites near Edmonton with permitting precedent and grid proximity weighted highest.` | Bare place plus selected pin/map center; 200 MW default | `Q-NAV` then `S`; Fabric, MPC, AI Search, weather MAF graph | Multi-service billable reads and model inference |
| Resilience: national outlook | `Canada` | `For the week of August 26, 2026, which Canadian facilities are most at risk and what is the supply-chain blast radius?` | Canadian registry; frontend sends rolling 7 days, not an as-of date | `Q-NAV` only if module inactive; question auto-selects `R`; assessment and facility tools | Fabric/AI Search/weather/MPC/model calls |
| Resilience: Vancouver outage | `Vancouver, British Columbia, Canada` | `If our Vancouver distribution centre goes offline for 48 hours in 2026, which downstream Canadian facilities are exposed?` | Region heuristic `BC`; 48 hours is scenario duration, frontend horizon remains 7 days | `Q-NAV` only if module inactive; question auto-selects `R`; expected `simulate_outage` | Fabric/AI Search/weather/MPC/model calls |
| Resilience: Western Canada | `Western Canada` | `Show 2026 heat and wildfire risk for all Western Canada facilities this week, ranked by severity with a response playbook.` | No frontend region code for Western Canada; rolling 7 days; heat and wildfire | `Q-NAV` only if module inactive; question auto-selects `R`; assessment plus playbook tools | Fabric/AI Search/weather/MPC/model calls |
| Forecast: Lake Ontario | `Lake Ontario, Canada` | `Give me an August 26-31, 2026 five-day forecast over Lake Ontario using every available model and summarize ensemble spread.` | Bare place/pin; dates are text only; `five-day` is not parsed, so frontend sends default 72 hours | `Q-NAV` then `F`; router may fan out to every configured provider | Potentially expensive multi-model inference |
| Forecast: Saskatchewan | `Saskatchewan, Canada` | `Forecast 2m temperature and 10m wind across southern Saskatchewan for August 26-28, 2026.` | Bare place/pin; dates are text only; frontend sends default 72 hours | `Q-NAV` then `F`; available global weather providers | Potentially expensive multi-model inference |
| Forecast: Nova Scotia | `Nova Scotia, Canada` | `Compare Aurora and Earth-2 FCN precipitation over Nova Scotia for August 27, 2026 and explain model disagreement.` | Bare place/pin; date is text only; frontend sends default 72 hours | `Q-NAV` then `F`; expected Aurora and Earth-2 provider selection | Billed two-model inference |

## Route caveats

* The two deployed callers instantiate `GetStartedButton` without its
  `features` prop. Its default is fully enabled, so Site Intel, Resilience,
  and Forecast appear interactive even when `/api/config` says their backing
  integrations are unavailable. Building Damage is not gated on MPC Pro.
* The landing-page callback bypasses `analysisType`, loaded-data validation,
  and module-selection events. A question clicked there goes through generic
  `/api/query/stream` without the intended module state.
* Setup prompts clear all non-Resilience module state. Setup must precede
  module selection for Terrain, Mobility, Extreme Weather, Building Damage,
  Site Intel, and Forecast.
* If Resilience is already selected, its setup button does not navigate. The
  bare place query is intercepted by the active Resilience branch and starts
  another planner assessment.
* Public mode gives the 12 Vision setup prompts a deterministic, no-GPT STAC
  fast path. Pro mode disables that cache and runs the full agent pipeline.
* Forecast has no structured forecast initialization date. The prompt text is
  passed as `user_query`, while the connector receives only coordinates,
  variables, grid size, and lead hours. The fixed August dates are stale after
  August 2026 and do not guarantee a historical forecast.
* Resilience similarly receives a horizon, hazard list, region code, and raw
  question, not a structured August 26 assessment date.

## Billed and destructive-work controls

No current Get Started tile directly invokes a destructive endpoint. Every
analysis question can still consume hosted-model capacity. The highest-cost
or private-data paths are Forecast, Building Damage, Site Intel, and
Resilience.

GeoFM Foundation Change is outside Get Started and lives in the map module
picker. Its tool controls are:

| Tool | Tier | Effect | Validation action |
|------|------|--------|-------------------|
| `geofm_list_models` | Read | Read deployment and model metadata | Safe if needed |
| `geofm_get_run` | Read | Poll an existing run | Safe if the run is known |
| `geofm_compare_epochs` | Write | Submit billed GPU work | Deny or avoid |
| `geofm_retry_run` | Write | Start another billed attempt | Deny or avoid |
| `geofm_cancel_run` | Destructive | Cancel queued or running work | Deny unless cancellation is intentional |

The AnalystAgent prompt permits GeoFM comparison only when the user explicitly
asks for PlanAura, a foundation model, embeddings, or contextual-change
detection. None of the current Get Started prompts contains those triggers.
Production still requires confirmation for every GeoFM mutation even when the
general MCP confirmation flag is disabled.

For validation with minimal incremental work:

1. Prefer text-only modal inspection.
2. If one live request is necessary, use a public cached Vision setup prompt,
   such as the Toronto Sentinel-2 example.
3. Do not select Foundation Change.
4. Deny confirmation cards for `geofm_compare_epochs`, `geofm_retry_run`, and
   `geofm_cancel_run`.
5. Skip Forecast, Building Damage, Site Intel, and Resilience when validating
   presentation or navigation rather than backend execution.

## Coverage assessment

| Coverage source | Current coverage | Gap |
|-----------------|------------------|-----|
| `planetary-explorer/web-ui/src/config/__tests__/canadianExamples.test.ts` | Dynamically covers all 32 primary rows for Canadian context and `2026`; Vision coverage checks setup prompts only | Does not render/click the modal or validate 24 raster/image prompts, counts, routes, tools, or feature gates |
| `planetary-explorer/container-app/quickstart_cache.py` plus `test_get_started_queries.py::test_quickstart_cache_contains_exactly_twelve_canadian_2026_queries` | Exact cache entries for all 12 public Vision setup prompts | Does not cover secondary Vision prompts or other modules |
| `scripts/verify_canadian_demo_browser.py` | Opens the modal, rejects four legacy locations, runs the Toronto Sentinel-2 setup, and checks its legend | One scenario only; local app URL; no module route or cost guard coverage |
| `planetary-explorer/container-app/tests/test_get_started_queries.py` | Contains six current Vision setup strings, two current raster strings, and one current Terrain question, plus generic AnalystAgent contract tests | Its independent manifest is partly obsolete, omits current Site Intel, Resilience, Forecast, and Building Damage, and does not import the frontend registry |
| `planetary-explorer/container-app/tests/live_get_started_runner.py` | Legacy live harness | Zero exact matches against the current 74 unique prompt strings; uses old international examples and old endpoint assumptions |
| Module-specific tests | Terrain contract, Site Intel graph, Forecast router, Resilience loaders/planner/tools, module selection, GeoFM confirmation/deny behavior | Contract coverage is not tied to all exact Get Started prompts |
| `README.md` and `planetary-explorer/web-ui/public/STAC_COLLECTION_GUIDE.md` | Illustrative Canadian examples and module descriptions; README includes several exact current prompts | Not a complete or canonical prompt list; some examples are shortened or differ from current strings |

The registry exposes 76 buttons but 74 unique prompt strings because the bare
Vancouver and Montreal setup prompts each appear in two modules.

## Follow-on questions

* Should the landing-page Get Started modal expose only setup prompts, or
  preserve module metadata when it enters the app?
* Should Forecast prompts be updated to relative horizons or should the API
  accept an explicit initialization date?
* Should the two callers pass `/api/config.features` into `GetStartedButton`
  so unavailable billable integrations are visibly locked?

## Clarifying questions

None required to complete the inventory.
