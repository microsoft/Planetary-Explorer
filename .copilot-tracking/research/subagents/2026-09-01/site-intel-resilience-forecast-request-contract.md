---
title: Site Intel Resilience and Forecast Request Contract Research
description: Frontend-to-backend contract research for the three Get Started scenarios
author: GitHub Copilot
ms.date: 2026-09-01
ms.topic: reference
---

## Status

Complete

## Research questions

* What exact frontend action and module state does each Get Started scenario establish?
* Which backend endpoint and request body does each scenario use?
* Which scenarios require a selected module, a map pin, or both?
* Which response fields or events indicate success?
* Which feature gates and deployment settings control scenario availability?
* Which tests exercise the contract, and what production blockers remain likely?
* How can each path be validated safely without invoking production?

## Working hypothesis

Site Intel and Forecast are pin-scoped GEOINT workflows routed through dedicated
`/api/geoint/*` endpoints. Resilience is a region-scoped workflow that selects the
module before dispatching the question and calls a resilience planner endpoint
without requiring a map pin. The frontend API service and backend route models
must agree on request field names for the scenario to succeed.

## Findings

### Shared Get Started event path

The header path is the supported in-app path. `GetStartedButton` dispatches a
`planetaryexplorer-query` event. `Chat` waits for React state propagation, reads
the current module and map context from refs, and submits the pending query.

The landing-page path is materially different. `LandingPage` passes
`onQuerySelect={(query) => onEnter('all', query)}`. Every handler returns through
that callback before dispatching a module-selection event. The initial query
therefore enters ordinary chat with no scenario module or pin. This prevents a
landing-page Get Started scenario from reaching any of the three dedicated
contracts unless a separate routing layer infers it later.

The Setup button in every scenario calls `handleStacQueryClick`. It dispatches
`planetaryexplorer-stac-query` with `{query, clearSessions: true}`. In
`MainApp`, that clears all selected modules except Resilience. This ordering
means Site Intel and Forecast users must run Setup first, then select the module
and place the pin, exactly as the UI instructions state.

### Site Intel

Frontend prerequisites:

* Selected module must be `site_audit`
* A `vision_pin`, generic current pin, or finite map-center fallback supplies
  coordinates
* The explicit UI workflow says Setup, select Site Intel, drop a pin, then Audit
* A zero/zero coordinate returns `isSiteAuditResponse: true` and
  `isClarification: true` without making the API call
* Capacity defaults to `200` MW only when the text contains an audit verb;
  otherwise a missing explicit MW value produces a clarification

Request:

```http
POST /api/sites/audit
Authorization: Bearer <user-token>
Content-Type: application/json
```

```json
{
  "lat": 51.18,
  "lng": -114.05,
  "claimed_mw": 200,
  "user_query": "For 2026, score our candidate data-centre sites near Calgary for power, water, competition, wildfire, flood, and heat exposure."
}
```

The backend requires numeric `lat` and `lng`, defaults a falsey
`claimed_mw` to 200, and accepts either `user_query` or legacy `query`. The
endpoint requires a user assertion even though Fabric data access now uses the
backend application identity. A bearer token or
`X-MS-TOKEN-AAD-ACCESS-TOKEN` is accepted.

Success is a direct dossier object, not a wrapper. The frontend expects:

* `scores.overall` plus power, water, hazards, competition, parcel_match, and
  precedent scores
* `summaries` keyed by dimension
* `evidence` and `data_provenance` arrays
* `engine: "maf_workflow_v2"`

The chat success object has `isSiteAuditResponse: true`, a formatted `response`,
and the raw `dossier`.

Feature and runtime gates:

* Get Started intends to use `/api/config.features.fabric`
* Deployment flag is `enableFabric`, surfaced as `PE_FEATURE_FABRIC`
* Fabric coordinates are `FABRIC_LAKEHOUSE_WORKSPACE_ID` and
  `FABRIC_LAKEHOUSE_ID`
* Microsoft Agent Framework must import and report available
* Site workflow controls include `SITE_PLANNER`, `SITE_EVIDENCE`, and
  `SITE_REVIEW`; their defaults are internal workflow choices rather than
  endpoint availability gates
* Missing Fabric IDs can fall back to bundled Canadian seed tables, but the
  route still requires an authenticated user token

### Resilience

Frontend prerequisites:

* No pin is required; module selection turns pin mode off
* The Get Started Ask handler dispatches
  `planetaryexplorer-select-module` with `{module: "resilience"}` first
* It waits 300 ms, then dispatches `planetaryexplorer-query` with `{query}`
* Province/city terms map to province codes; a national query omits
  `region_filter`
* Hazard text narrows to `heat` and/or `wildfire`; otherwise both are sent
* Horizon defaults to 7 days, supports numeric day text up to 14, and maps
  two-week/fortnight to 14

The supported chat request is streaming:

```http
POST /api/resilience/assess/smart/stream
Authorization: Bearer <user-token>
Content-Type: application/json
```

```json
{
  "horizon_days": 7,
  "hazards": ["heat", "wildfire"],
  "user_query": "For the week of August 26, 2026, which Canadian facilities are most at risk and what is the supply-chain blast radius?"
}
```

`region_filter` is added only when the frontend recognizes a province or city.
The smart endpoint requires non-empty `user_query`. It accepts legacy aliases
`region` and `query`. The non-streaming alternatives are
`/api/resilience/assess/smart` and the deterministic
`/api/resilience/assess`; `ResiliencePanel` still contains a direct buffered
call but is intentionally not mounted in `MapView`.

SSE success is the terminal event payload
`{"type":"dossier","payload":{...}}`. The frontend also accepts an older raw
payload containing `facilities` or `summary`. It surfaces `tool_call`,
`tool_result`, `confirm_request`, and `confirm_resolved` events before the
terminal dossier. Successful chat output sets `isResilienceResponse: true`,
includes the dossier, and dispatches `resilience:facilities` for map markers.

The dossier must provide `facilities`, `summary`, and `provenance`. Standard
dossiers include `summary.facilities_assessed`, `at_risk_facilities`, and
`top_risks`; smart dossiers add `route`, may add `tool_trace`, and may add
`narrative` or `planner_warning`. A stable `assessment_id` is added by the
buffered standard endpoint, but the smart streaming endpoint does not call the
assessment cache stamping helper.

Feature and runtime gates:

* Get Started intends to use `/api/config.features.fabric`
* `RESILIENCE_MVP` gates standard and smart endpoints and defaults on
* `RESILIENCE_PLANNER` gates the smart endpoints and defaults on
* Microsoft Agent Framework must be available
* `RESILIENCE_FORCE_SEED` forces bundled data when enabled
* Fabric configuration may use Resilience-specific IDs or shared
  `FABRIC_LAKEHOUSE_*` IDs
* Fabric failure can degrade to seed data, but every route still requires an
  authenticated user assertion

### Forecast

Frontend prerequisites:

* Selected module must be `forecast`
* A `vision_pin`, generic current pin, or finite map-center fallback supplies
  coordinates
* The explicit UI workflow says Setup, select Forecast, drop a pin, then Ask
* A zero/zero coordinate returns `isClarification: true` without making the
  API call
* Lead defaults to 72 hours; numeric hour terms or numeric `N-day` text map to
  1 through 240 hours

Request:

```http
POST /api/geoint/forecast
Content-Type: application/json
```

```json
{
  "latitude": 43.6532,
  "longitude": -79.3832,
  "lead_hours": 72,
  "grid_size": 8,
  "user_query": "Forecast 2m temperature and 10m wind across southern Saskatchewan for August 26-28, 2026."
}
```

The API service can also send `variables`, `providers`, and `location_label`,
but the current chat path sends only `leadHours`. Backend defaults are
`variables=["t2m","precip","u10","v10"]`, all configured providers, and an
8 by 8 grid. Latitude, longitude, lead hours, and grid size have explicit range
validation. Unlike Site Intel and Resilience, the handler itself does not call
the Fabric assertion guard.

Success is wrapped as:

```json
{
  "status": "success",
  "result": {
    "providers_called": [],
    "providers_succeeded": [],
    "providers_failed": [],
    "forecasts": [],
    "ensemble_summary": {},
    "note": ""
  },
  "timestamp": "..."
}
```

The frontend unwraps `result`, renders successful or attempted models, failed
models, and `ensemble_summary.variables`, and returns the raw dossier alongside
formatted chat text. A meaningful success requires at least one entry in
`providers_succeeded`; HTTP 200 and `status: success` alone do not prove useful
forecast output.

Feature and runtime gates:

* `/api/config.features.weather` is true when any of
  `AURORA_ENDPOINT_URL`, `EARTH2_FCN_ENDPOINT_URL`, or
  `MAI_WEATHER_ENDPOINT_URL` is non-empty
* `FORECAST_AGENT_ENABLED` separately gates the route and defaults on
* Microsoft Agent Framework must be available
* The provider registry must contain at least one configured provider
* Provider HTTP calls use configurable timeout, attempts, and retry delay via
  `WEATHER_PROVIDER_TIMEOUT_S`, `WEATHER_PROVIDER_ATTEMPTS`, and
  `WEATHER_PROVIDER_RETRY_DELAY_S`

### Configured repository defaults

The checked-in `infra/main.parameters.json` values are:

* `enableFabric: false`
* Empty `fabricWorkspaceId` and `fabricLakehouseId`
* `deployWeatherStub: false`
* Empty Aurora, Earth-2 FCN, and MAI Weather endpoint URLs
* `forecastAgentEnabled: true`

Those defaults make Site Intel and Resilience intentionally unavailable from a
feature-advertising perspective and leave Forecast with no registered provider.

### Exact starter-card derivation

Coordinates below mean the effective pin (`vision_pin`, then current pin, then
finite map center). The query string is passed unchanged from
`canadianExamples.ts`.

| Module and card | Derived behavior after prerequisites |
|-----------------|--------------------------------------|
| Site Intel, Calgary data centre | `POST /api/sites/audit` with `{lat, lng, claimed_mw: 200, user_query: <exact card question>}` because "score" admits the 200 MW default |
| Site Intel, Montreal industrial parcels | No request. The question has no MW and does not contain `audit`, `score`, `rank`, `assess`, or `evaluate`, so Chat asks for asset size |
| Site Intel, Edmonton grid expansion | `POST /api/sites/audit` with `{lat, lng, claimed_mw: 200, user_query: <exact card question>}` because "rank" admits the default |
| Resilience, seven-day Canadian outlook | `POST /api/resilience/assess/smart/stream` with `{horizon_days: 7, hazards: ["heat", "wildfire"], user_query: <exact card question>}` and no `region_filter` |
| Resilience, Vancouver disruption | Same endpoint with `{region_filter: "BC", horizon_days: 7, hazards: ["heat", "wildfire"], user_query: <exact card question>}`; "48 hours" does not alter the 7-day horizon parser |
| Resilience, Western Canada review | Same endpoint with `{horizon_days: 7, hazards: ["heat", "wildfire"], user_query: <exact card question>}` and no `region_filter`; "Western Canada" is not a recognized frontend region hint |
| Forecast, Great Lakes five-day ensemble | `POST /api/geoint/forecast` with `{latitude, longitude, lead_hours: 72, grid_size: 8, user_query: <exact card question>}`; word-form "five-day" does not produce 120 hours and no provider allow-list is sent |
| Forecast, Prairie temperature and wind | Same endpoint/body shape with `lead_hours: 72`; no variables or provider allow-list is sent |
| Forecast, Atlantic precipitation comparison | Same endpoint/body shape with `lead_hours: 72`; the requested Aurora/Earth-2 pair is not sent as `providers`, and default variables include temperature and wind as well as precipitation |

### Test coverage

Focused local frontend validation passed 22 tests across three files:

* `api.streaming.test.ts` verifies Resilience SSE parsing and omission of
  `region_filter` for a national assessment
* `GeointModulesFlow.test.tsx` verifies Resilience selection is region-scoped
  and the universal pin control publishes coordinates
* `canadianExamples.test.ts` verifies Canadian context and 2026 wording only

Backend coverage found during static research:

* `test_site_intel_workflow.py` verifies seed fallback and the Site Intel
  dossier score/provenance shape
* `test_forecast_router.py` verifies provider routing, fallback-all behavior,
  and Agent Framework fail-closed behavior
* `test_endpoint_error_redaction.py` touches Site Intel and Forecast route
  handlers and verifies stable public errors
* Resilience tests cover data loading, planner tools, MCP adapters, narrative,
  risk scoring, and snapshots

No focused test currently proves the complete Get Started event through Chat to
the dedicated Site Intel or Forecast API. There is no direct FastAPI contract
test for Resilience assessment request validation or SSE terminal shape. No test
asserts `/api/config` feature flags reach `GetStartedButton`.

### Likely production blockers

1. Feature flags do not reach either rendered `GetStartedButton`.
   `App` fetches `/api/config`, but `Header` and `LandingPage` do not accept or
   pass `features`. The component therefore uses its permissive defaults and
   presents all three tiles as enabled even when integrations are disabled.
2. Landing-page Get Started bypasses all module selection. Site Intel,
   Resilience, and Forecast examples enter ordinary chat because
   `onQuerySelect` short-circuits each specialized handler.
3. Site Intel and Resilience require a user assertion even with
   `enableAuthentication: false`. `DISABLE_AUTH` alone does not bypass this
   guard; bypass also requires `RESILIENCE_DEV_BYPASS_AUTH`, which must never be
   used in production. An unauthenticated public-demo deployment receives 401.
4. Site Intel UI availability is tied to Fabric even though bundled seed data
   can run without Fabric IDs. Conversely, a true Fabric flag does not prove
   the backend managed identity has workspace access.
5. Resilience availability is represented by the Fabric flag, not its own
   health contract. A deploy can advertise Resilience while `RESILIENCE_MVP`,
   `RESILIENCE_PLANNER`, or Agent Framework makes the smart stream return 503.
6. Forecast availability checks endpoint strings only. It can advertise the
   tile while `FORECAST_AGENT_ENABLED=0`, Agent Framework is unavailable, or
   the endpoints fail health/scoring calls.
7. The Great Lakes "five-day" example does not contain numeric `5-day` text.
   The frontend therefore sends the 72-hour default, not 120 hours.
8. Forecast examples include absolute August 2026 dates, but the API contract
   has no forecast initialization/date field. Provider requests contain only
   location, lead, variables, and grid size, so the named date is advisory text
   and cannot control model valid time.
9. Forecast model labels are not request allow-lists. The current chat call
   sends no `providers` array; selection depends on LLM routing or falls back to
   every configured global provider. "Aurora and Earth-2" is therefore not a
   deterministic two-provider contract.
10. "Western Canada" is not in the Resilience region heuristic. That starter
    example omits `region_filter` and assesses the full registry unless the
    planner independently narrows it from natural language.
11. The Montreal Site Intel example says "clear" but has no MW and none of the
    accepted audit verbs (`audit`, `score`, `rank`, `assess`, `evaluate`). It
    returns a capacity clarification instead of calling `/api/sites/audit`.
12. Resilience SSE parsing recognizes `event: error` blocks, but the backend
    smart stream emits an ordinary data event whose payload has
    `type: "error"`. The frontend currently routes that through progress rather
    than `onError`; absent a dossier, Chat returns a generic retry message.
13. The smart Resilience stream does not stamp/cache `assessment_id`, unlike
    the standard buffered endpoint. Follow-on snapshot consumers cannot assume
    every chat dossier is retrievable from the assessment cache.
14. The browser API base URL is build-time `VITE_API_BASE_URL` or current
    origin. A stale or omitted production build value can direct calls to the
    frontend host instead of the Container App unless a reverse proxy exists.
15. Resilience SSE obtains an access token once but has no 401 refresh-and-retry
  path. Axios calls for Site Intel and Forecast do retry after token refresh,
  so an expired token disproportionately breaks Resilience chat requests.

### Safe validation approach

Do not call deployed hosts while validating this contract.

1. Run frontend unit tests with mocked fetch/Axios and fake map SDKs:

   ```powershell
   npx vitest run src/services/__tests__/api.streaming.test.ts `
     src/components/__tests__/GeointModulesFlow.test.tsx `
     src/config/__tests__/canadianExamples.test.ts --silent
   ```

2. Add or run local FastAPI handler tests that monkeypatch
   `_require_fabric_assertion`, Site Intel workflow calls, Resilience planner
   calls, Forecast workflow calls, and the provider registry. Assert the exact
   status/body/SSE sequence without binding a network port.
3. For a local HTTP Forecast smoke, point both provider URLs at the bundled
   weather stub and run `scripts/smoke-weather.ps1`. It uses localhost only and
   asserts health, provider count, `status: success`, and at least two succeeded
   providers.
4. For local Site Intel/Resilience smoke tests, use bundled seed data and a
   synthetic request object or FastAPI `TestClient`. Patch the auth guard rather
   than enabling the development auth-bypass environment variables globally.
5. Validate `/api/config`, `/api/resilience/health`, and
   `/api/geoint/forecast/health` as pure local handlers with monkeypatched
   environment variables. Treat a feature as ready only when its master flag,
   runtime, provider/data source, and expected route all agree.
6. Inspect the built frontend artifact statically for the intended API host;
   do not use the production URL as a connectivity test.

## References

* `planetary-explorer/web-ui/src/components/GetStartedButton.tsx`
* `planetary-explorer/web-ui/src/components/Chat.tsx`
* `planetary-explorer/web-ui/src/components/MainApp.tsx`
* `planetary-explorer/web-ui/src/components/MapView.tsx`
* `planetary-explorer/web-ui/src/components/LandingPage.tsx`
* `planetary-explorer/web-ui/src/components/Header.tsx`
* `planetary-explorer/web-ui/src/services/api.ts`
* `planetary-explorer/web-ui/src/config/canadianExamples.ts`
* `planetary-explorer/container-app/fastapi_app.py`
* `planetary-explorer/container-app/fabric_client.py`
* `planetary-explorer/container-app/agents/site_intel/executors.py`
* `planetary-explorer/container-app/agents/resilience/executors.py`
* `planetary-explorer/container-app/agents/resilience/planner.py`
* `planetary-explorer/container-app/agents/forecast/messages.py`
* `planetary-explorer/container-app/agents/forecast/ensemble.py`
* `planetary-explorer/container-app/agents/forecast/workflow.py`
* `planetary-explorer/container-app/connectors/weather/_http.py`
* `planetary-explorer/infra/main.parameters.json`
* `planetary-explorer/infra/app/web.bicep`
* `planetary-explorer/scripts/smoke-weather.ps1`
* `planetary-explorer/web-ui/src/services/__tests__/api.streaming.test.ts`
* `planetary-explorer/web-ui/src/components/__tests__/GeointModulesFlow.test.tsx`
* `planetary-explorer/web-ui/src/config/__tests__/canadianExamples.test.ts`
* `planetary-explorer/container-app/tests/test_site_intel_workflow.py`
* `planetary-explorer/container-app/tests/test_forecast_router.py`
* `planetary-explorer/container-app/tests/test_endpoint_error_redaction.py`

## Follow-on questions

* Should Site Intel be advertised when seed fallback is usable but Fabric is
  disabled, or is the Fabric requirement an intentional product policy?
* Should Forecast absolute-date examples be removed, or should the request
  contract gain a model initialization time?
* Should smart Resilience responses be cached and stamped with
  `assessment_id` for M365 snapshot parity?

## Clarifying questions

None required to map the current implementation.