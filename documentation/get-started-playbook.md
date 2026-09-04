---
title: Use Planetary Explorer with the Get Started playbook
description: Run tested Canadian map, raster, terrain, mobility, climate, forecast, site, resilience, and building-damage workflows
ms.date: 2026-09-03
ms.topic: how-to
keywords:
  - Planetary Explorer
  - Get Started
  - Planetary Computer
  - geospatial analysis
  - Canada
estimated_reading_time: 16
---

## What this playbook covers

This playbook turns the **Get Started** gallery into repeatable workflows. It
uses one recommended example from each of the 11 scenario families and records
what a successful result looked like in the deployed application on September
3, 2026 (UTC).

The full validation covered 32 scenarios at two or three Canadian locations
per family. The API matrix passed 30 setup queries and blocked the two Building
Damage setups before external I/O because MPC Pro was disabled. The deployed
gallery exposed 27 of those setup actions; its three Site Intel cards remained
disabled because Fabric was unavailable. All 24 runnable analyses met the
automated family contracts for status, expected tools, and available structured
evidence. Eight analyses were correctly blocked by missing MPC Pro, Fabric, or
sign-in prerequisites. A contract pass does not mean every requested value
exists: for example, the no-fire Alberta pixel returned `FireMask` but no
`MaxFRP`.

An HTTP 200 response alone was not counted as success. Validation checked the
requested place, collection, date, scene, tool, numeric evidence, provider
completion, and, where applicable, screenshot bytes. All 12 Image Analysis
workflows also passed a real-browser gate that proved the requested map layer
changed pixels, the submitted pin stayed within 0.41 km of the intended point,
the backend evidence centre stayed within 0.52 km of that pin, the image decoded
at 1020 by 920 pixels, and `describe_map_screenshot` returned collection- and
location-aligned structured evidence. The one uniform thematic view was accepted
only because the response named its visible dark-purple colour and explicitly
reported that no variation was visible.

Location independence was tested separately. All 32 Setup rows ran while a
conflicting Sydney pin, map bounds, Sentinel-1 collection, Vision mode, and
GEOINT mode were attached. Thirty runnable rows loaded their own canonical
locations, the two MPC Pro rows remained capability-blocked, and none failed.
The browser suite also started every imagery example from a distant loaded
image and stale Vision pin. All 12 examples created a new session, sent no
stale location fields, and completed at their intended Canadian locations. A
separate Toronto workflow also passed from a country-scale Sydney/Australia
view at zoom level 4.

### Validated release

The evidence below is bound to one production release. The verifier checked
the live Azure control plane, active App Service deployment, downloaded bundle
hash, API health, traffic weight, and GeoFM worker replicas before each matrix.

| Component | Release evidence |
|-----------|------------------|
| API | Revision `ca-earthcopilot-api--getstarted-hardened-0903-0316`, image `sha256:4b5288048cd6ab9033284e49cea6ad85129fb30925c82f0fde88dc6ba04dd73e`, healthy and serving 100% traffic |
| Forecast adapter | Revision `ca-weather-44gnuvaloryac--getstarted-0902-1700`, image `sha256:4f928d2b54e2fb0712703eba111395c9a62e2b0d6901d908fa4ac8a5cff2660b` |
| Frontend | OneDeploy `72b1ce87-7b21-4793-990b-c9e557fe7d10`, bundle `index-jUC2ydNZ.js`, SHA-256 `6e446d885a45f14e593ea0f88f5edfb30c682eb5e90e9a320584d4106e02d05a` |
| Local release tests | 597 backend passed with 1 skip; 160 frontend, 49 Python verifier, 8 browser-semantic, and 1 weather-adapter test passed |
| Unfiltered backend | 644 passed, 1 skipped, and 6 known baseline mismatches remained in two excluded test files |
| Setup evidence | 32-row release matrix: 30 passed, 2 capability-blocked, 0 failed |
| Analysis evidence | 32-row release matrix: 24 passed, 8 prerequisite-gated, 0 failed |
| Browser evidence | 12-row release matrix: 12 passed, 0 failed |
| GPU posture | GeoFM worker minimum replicas `0`, active replicas `0`; these scenario matrices do not invoke approval-gated GeoFM tools |

## Know the controls

| Control | Use |
|---------|-----|
| **Get Started** | Open the tested query gallery and choose a module family |
| **Go** | Run the exact Setup or Analyze prompt on a gallery card |
| Four-square map control | Select a geointelligence module before placing its pin or pins |
| Plus-pin map control | Place a general-purpose pin without selecting a module |
| **Map layers** | Show or hide available imagery and model overlays and change opacity |
| **MPC Pro** | Route STAC searches to a configured private GeoCatalog; disabled when unavailable |
| Source and tool chips | Confirm the catalog and analysis tool used for an answer |
| **Restart** | Clear the whole conversation when you no longer need its messages; Setup already replaces stale map and analysis state |

> [!IMPORTANT]
> You can start a Get Started example from any selected map location. Its
> **Setup** action clears the previous pin, module, map context, and routing
> session before loading the example. Wait for the new map to finish drawing,
> then place the new pin or pins requested by that example. An **Analyze**
> action intentionally uses those newly placed coordinates.

## Use the common map workflow

The four Vision families use the same three-stage pattern.

1. Select **Get Started**, then select **Vision**.
2. In **Step 1: STAC Search**, select **Go** on the example's Setup card.
3. The app clears any previous location, pin, module, and loaded collection.
   Wait until the response identifies the requested place, collection, and
   date. Also wait for the map to centre and the raster colours to finish
   drawing. Open **Map layers** and confirm the requested imagery layer is
   listed and visible. Do not place a pin while the camera is still moving.
4. Select the four-square map control, select **Vision Analysis**, and click
   near the centre of the loaded image.
5. Confirm chat says **Pin Placed**. For a point-qualified example, confirm the
   displayed coordinates are close to the coordinates in the Setup prompt.
6. Reopen **Get Started** and **Vision**.
7. Choose one analysis:
   - **Raster Analysis** reads source pixels and returns numeric values.
   - **Image Analysis** describes only the currently rendered map view.
8. Confirm the answer shows **Data: Public PC** and the expected tool chip:
   **Raster sample** or **Vision**.

> [!IMPORTANT]
> Raster Analysis and Image Analysis answer different questions. A screenshot
> can explain visible colours and patterns, but it cannot establish a source
> pixel value. A raster sample can report a pixel value, but one pixel does not
> prove conditions across a region. Successful **Vision** tool evidence proves
> that the screenshot was processed; you must still confirm the requested
> imagery layer is visible and that the answer describes what is actually on
> the map.

## Recommended examples

| Family | Recommended example | Validation state |
|--------|---------------------|------------------|
| Vision - Optical Imagery | Calgary HLS S30 vegetation | Setup, raster, visible-layer, and Image Analysis gates passed |
| Vision - Fire and Vegetation | Regina MODIS NDVI and EVI | Setup, raster, visible-layer, and Image Analysis gates passed |
| Vision - Water, Snow, and Ice | Quebec City MODIS snow cover | Setup, raster, visible-layer, and Image Analysis gates passed |
| Vision - Terrain and Radar | Red River Sentinel-1 backscatter | Setup, raster, visible-layer, and Image Analysis gates passed |
| Terrain | Metro Vancouver construction screening | Passed with slope, flat-area, and flood tools |
| Mobility | Yukon emergency-supply corridor | Passed complete two-point route and coverage evidence |
| Extreme Weather | Toronto monthly precipitation | Passed with all 12 months and 360 daily values |
| Forecast | Lake Ontario five-day ensemble | Passed with two configured NWP-backed provider contracts |
| Building Damage | Jasper wildfire damage | Blocked: MPC Pro is required and disabled |
| Site Intel | Edmonton grid expansion | Setup passed; analysis blocked because Fabric is disabled |
| Resilience | Vancouver distribution disruption | Setup passed; analysis blocked because sign-in is required |

## Analyze optical imagery near Calgary

Use this example to learn the full Setup, Raster Analysis, and Image Analysis
sequence on high-resolution optical imagery.

### Load Calgary HLS imagery

```text
Show HLS S30 imagery at Calgary, Canada, latitude 51.0300, longitude -114.0800, from 2026-05-01 to 2026-08-26
```

### Sample Calgary NDVI

```text
What is the 2026 NDVI value at this Calgary pin?
```

### Describe Calgary imagery

```text
Describe urban growth and vegetation patterns visible around Calgary in 2026.
```

The validated raster result used
`HLS.S30.T11UQS.2026235T183919.v2.0`. It reported red reflectance `511`,
near-infrared reflectance `3183`, and NDVI `0.723`. The browser check submitted
a decodable 1020 by 920 JPEG from a pin at `51.0300, -114.0800` and returned
successful **Vision** tool evidence.

Interpret NDVI as a relative vegetation signal at the sampled pixel. It is not
a land-use classification or proof of urban growth. The Image Analysis prompt
describes development patterns visible in one 2026 view; it does not measure
growth. Compare aligned scenes from multiple dates before making a change
claim.

## Inspect vegetation near Regina

Use this example when both NDVI and EVI are useful. EVI can retain sensitivity
in dense vegetation and reduce some atmospheric and soil-background effects.

### Load Regina vegetation indices

```text
Show MODIS 13Q1 vegetation indices over cropland south of Regina, Saskatchewan, Canada, latitude 50.3500, longitude -104.6000, from 2026-04-01 to 2026-08-26
```

### Sample Regina NDVI and EVI

```text
Sample the 2026 NDVI and EVI values at this Regina cropland pin.
```

### Describe Regina vegetation colours

```text
Explain the vegetation colours and identify lower-vigour areas near Regina in 2026.
```

The validated August 5 scene reported NDVI `0.52` and EVI `0.39` at the exact
pin. Both are positive vegetation signals. Do not compare raw colours between
screenshots unless the render profile and scale are the same. MODIS pixels are
250 metres, so a sample can mix more than one field or land-cover type.

## Read snow cover near Quebec City

This archival example deliberately uses February 2025 because that date has a
verified daily MODIS snow scene at the point.

### Load Quebec City snow cover

```text
Show MODIS 10A1 daily snow cover at Quebec City, Canada, latitude 46.8139, longitude -71.2080, from 2025-02-01 to 2025-02-28
```

### Sample Quebec City snow cover

```text
Sample the February 2025 NDSI value at this Quebec City pin.
```

### Describe Quebec City snow colours

```text
State the colours actually visible in this February 2025 MODIS snow-cover image and whether they vary, then explain only those visible colours around Quebec City.
```

The validated February 28 scene returned NDSI snow cover of `48%`. The browser
workflow submitted a real 1020 by 920 map image and returned successful Vision
evidence. Cloud, water, forest canopy, and urban surfaces can complicate snow
interpretation; inspect the collection legend and quality layers before using
the value operationally.

## Inspect Red River radar backscatter

Radar works through cloud and does not depend on daylight. This makes it useful
for spring flood monitoring, but dark backscatter is not automatically flood.

### Load Red River radar

```text
Show Sentinel-1 RTC radar imagery over the Red River, Manitoba from 2026-03-01 to 2026-05-31
```

### Sample Red River backscatter

```text
Sample the 2026 radar backscatter at this Red River pin.
```

### Describe Red River radar

```text
Explain the radar colour composite and identify possible inundation.
```

The validated May 22 scene reported VV `-14.03 dB` and VH `-23.18 dB` from the
same item and date. Smooth open water commonly appears dark, but radar shadow,
surface roughness, vegetation, incidence angle, and processing choices also
affect backscatter. Confirm possible inundation against an earlier reference
scene, terrain, gauge data, and local reports.

## Screen terrain in Metro Vancouver

1. Open **Get Started**, then select **Terrain**.
2. Run the Setup prompt and wait for the DEM layer to draw.
3. Select the four-square map control, select **Terrain**, and place a pin in
   the loaded area.
4. Reopen **Get Started** and run the Analyze prompt.

### Load Metro Vancouver terrain

```text
Show Copernicus DEM elevation near Vancouver, Canada for 2026
```

### Analyze Metro Vancouver terrain

```text
For 2026, is this Metro Vancouver location suitable for a construction permit? Analyze slope, flood exposure, and flat areas.
```

The validated response invoked slope, flat-area, and flood tools. Within the
five-kilometre analysis radius it reported mean slope `4.1 degrees`, `67.8%`
flat terrain, and `32.2%` frequently flooded area. The combined conclusion was
high flood risk and **not suitable without significant mitigation**.

This is screening evidence, not a permit decision. The flood layer describes
historical water occurrence, not a 2026 event forecast. Confirm parcel
boundaries, drainage, geotechnical conditions, regulations, and engineering
requirements with authoritative local sources. Copernicus DEM is a static
terrain reference; the validated item is dated April 22, 2021. “For 2026”
describes the planning question, not a claim that elevation was acquired in
2026.

## Assess a Yukon mobility corridor

1. Open **Get Started**, then select **Mobility**.
2. Run the Setup prompt to navigate to Whitehorse.
3. Select the four-square map control and select **Mobility**.
4. Place Pin A at `60.7212, -135.0568`, then Pin B at
   `60.7562, -135.0068`. Small click differences change the route result.
5. Reopen **Get Started** and run the Analyze prompt.

### Navigate to Whitehorse

```text
Whitehorse, Yukon, Canada
```

### Analyze the Yukon route

```text
Assess this 2026 emergency-supply route for water crossings, wildfire exposure, steep slopes, and ground-vehicle feasibility.
```

The validated route was `4.75 km` direct and `7.35 km` by road, with estimated
road time `30.2 minutes`, total ascent `104.9 m`, and a `SLOW-GO` corridor
classification. The complete result had one populated waypoint and six source
collections at each endpoint.

Read the structured route, endpoint, corridor, coverage, and road fields, not
only the short narrative. The result is a planning aid. It does not replace
road closure notices, fire perimeters, water-crossing inspection, land access
permission, current weather, or field reconnaissance.

## Compare monthly Toronto precipitation

1. Open **Get Started**, then select **Extreme Weather**.
2. Run the Setup prompt and wait for the map to centre on Toronto.
3. Select the four-square map control, select **Extreme Weather**, and place a
   pin near the requested location.
4. Reopen **Get Started** and run the Analyze prompt.

### Navigate to Toronto

```text
Toronto, Ontario, Canada
```

### Analyze Toronto precipitation

```text
Show monthly projected precipitation for Toronto in 2026 and identify the wettest month.
```

The validated NASA NEX-GDDP-CMIP6 result contained all 12 calendar months and
360 daily values. In that run, March was wettest at `5.26 mm/day`; annual mean
was `2.77 mm/day` and peak daily precipitation was `30.43 mm`.

These are downscaled model projections, not observations or a weather
forecast. The validated result used one UKESM1-0-LL SSP5-8.5 grid cell about
`3.2 km` from the pin at 0.25-degree resolution. Compare models and scenarios
before using the projection for adaptation decisions.

## Run a Lake Ontario forecast ensemble

1. Open **Get Started**, then select **Forecast**.
2. Run the Setup prompt and wait for the map to centre on Lake Ontario.
3. Select the four-square map control, select **Forecast**, and place a pin.
4. Reopen **Get Started** and run the Analyze prompt.

### Navigate to Lake Ontario

```text
Lake Ontario, Canada
```

### Run the Lake Ontario ensemble

```text
Give me a 120-hour (five-day) forecast over Lake Ontario using every available model and summarize ensemble spread.
```

The validated deployment ran the `aurora-1.x` and `earth2-fcn` provider
contracts with no transport failures. In this deployment those contracts were
backed by ECMWF IFS and NOAA GFS through Open-Meteo, not native Aurora or
Earth-2 inference. The centre-cell temperature spread was `2.113 K`. The
application formats the structured dossier into provider status, source,
units, ensemble mean, spread, standard deviation, and sample count.

“Every available model” means every provider contract shown by the current
deployment; MAI Weather was not configured in the validated environment. Check
each result's `native_model_inference`, source, unit, and synthetic-fallback
fields before interpretation. Treat this output as an NWP comparison, not an
official forecast, and use an operational weather service for safety-critical
decisions.

## Prepare Building Damage for Jasper

> [!WARNING]
> This workflow did not run in the validated deployment. It requires private
> before-and-after aerial imagery in MPC Pro. The disabled tile is the expected
> behavior when that prerequisite is absent.

An operator must enable MPC Pro and configure a private GeoCatalog containing
authorized imagery before you begin. Do not substitute public imagery and call
the result a tenant building-damage assessment.

### Load Jasper tenant imagery

```text
Show my MPC Pro aerial imagery over Jasper, Alberta from 2026-01-01 to 2026-08-26
```

### Assess Jasper building damage

```text
Using the 2026 before-and-after tenant imagery, assess potential building damage and distinguish destroyed, major-damage, and unaffected structures.
```

After enabling the prerequisite, confirm **Data: MPC Pro**, verify both source
dates and scene identifiers, zoom to level 16 or higher so individual buildings
are visible, select **Building Damage** from the four-square map control, and
place a pin on the target structure. The capability-gated picker path is
covered by local UI tests, but the assessment remains unvalidated without real
tenant imagery. Treat all classifications as screening output requiring
image-quality review and field verification.

## Prepare Site Intel for Edmonton

> [!NOTE]
> Navigation to Edmonton passed, but analysis was blocked because Fabric was
> disabled. No site ranking was produced or validated.

An operator must enable Fabric and configure the workspace, Lakehouse, and
required power, water, hazard, competition, and permitting data.

### Navigate to Edmonton

```text
Edmonton, Alberta, Canada
```

### Rank Edmonton sites

```text
Rank the top three 2026 sites near Edmonton with permitting precedent and grid proximity weighted highest.
```

When enabled, select **Site Intel**, place a candidate-site pin, and inspect
the component scores and source records behind the overall rank. A high score
does not establish land availability, interconnection capacity, water rights,
permit eligibility, cost, or community acceptance.

## Prepare Resilience for Vancouver

> [!NOTE]
> Navigation to Vancouver passed, but analysis was intentionally blocked
> without an authenticated user. The workflow was not bypassed or claimed as a
> pass.

Sign in with an identity authorized to read the configured facility and
supply-chain data. Fabric-backed operational data must also be populated for a
meaningful result.

### Navigate to Vancouver

```text
Vancouver, British Columbia, Canada
```

### Assess Vancouver disruption

```text
If our Vancouver distribution centre goes offline for 48 hours in 2026, which downstream Canadian facilities are exposed?
```

When enabled, select **Resilience** and run the prompt. Review facility IDs,
hazards, route or edge evidence, lead times, and downstream dependencies. Keep
sensitive operational data within its authorized audience and validate the
generated response playbook with the responsible operations team.

## Verify a result before using it

Use these checks for every workflow:

- The map is at the requested country, place, and point.
- The response answers the requested action and exposes no error or incomplete
   status.
- A navigation-only Setup centres the expected region; it does not need a
   collection, date, or STAC source chip.
- A STAC Setup names the expected collection and acquisition date, shows the
   intended **Public PC** or **MPC Pro** source, and lists a visible layer under
   **Map layers**.
- Vision raster evidence names the sampled scene and date and shows the
   **Raster sample** tool. Image Analysis shows the **Vision** tool and describes
   the visible map. Specialized modules may expose their evidence in the
   response instead of a tool chip.
- Monthly climate output contains all 12 months.
- Climate comparison contains both variables under both scenarios.
- Mobility includes both endpoints, at least one corridor waypoint, and source
  coverage rather than only a prose route recommendation.
- Forecast lists succeeded and failed providers and gives ensemble statistics.
- A disabled or sign-in-gated workflow remains blocked until its real
  prerequisite is available.

Stop and restart the workflow if the map shows the wrong place, an observation
date is silently changed, the source indicates the wrong catalog, a required
tool or structured result is absent, or the answer lacks the relevant evidence
above. Static collections such as a DEM can have an acquisition date earlier
than the planning year; the response should state that distinction rather than
inventing a current observation.

## Apply operational safety rules

- Do not use one raster pixel or one screenshot as a regional conclusion.
- Do not interpret model output as an official hazard perimeter, permit,
  engineering assessment, damage inspection, or route clearance.
- Do not bypass sign-in, tenant catalog, or Fabric feature gates.
- Do not repeat a timed-out POST automatically. First determine whether its
  tool ran, especially for operations that can create work or incur cost.
- Foundation Change and other GeoFM mutations require explicit approval and
  can start billed GPU work. This Get Started validation did not approve any
  GeoFM request, and the GeoFM worker remained at zero active replicas.
- Preserve returned scene IDs, dates, provider names, units, and source links
  when sharing a result so another reviewer can reproduce it.

For the separate approval-gated GeoFM workflow, see
[Run Foundation Change with PlanAura](geofm-foundation-change.md). For the
wildfire case study, see
[Analyze the Thunder Bay 36 wildfire](geofm-thunder-bay-fire.md).

## Reproduce the release checks

Use Python 3.11 or later and Node.js 20 or later. From a clean checkout,
install the locked frontend dependencies and the Chromium browser used by the
real-browser gate:

```powershell
npm --prefix planetary-explorer/web-ui ci
npm --prefix planetary-explorer/web-ui exec -- playwright install chromium
```

The inventory command uses the declared `esbuild` dependency to read the
canonical TypeScript scenario configuration. It does not make live requests:

```powershell
python scripts/verify_get_started_scenarios.py --list
```

Live setup and analysis verification requires an explicit API origin and
`--allow-production` for any non-loopback host. The browser verifier requires
Node Playwright and uses the prompts exported from the TypeScript
configuration. Its default origins are loopback, so this command is local-only
and starts each row from another loaded example. Start the API at
`http://127.0.0.1:8000` and the web UI at `http://127.0.0.1:5173` first; see
[Local dev container development](../LOCAL_DEV_CONTAINER_DEVELOPMENT.md).

```powershell
node scripts/verify_get_started_image_analysis.mjs --adversarial-location-query auto
```

For production, also pass both HTTPS origins, `--allow-production`, and the
complete API, weather, frontend, Azure target, and zero-GPU release-binding
arguments. The verifier rejects a remote run when any binding value is absent.

The browser verifier fails when the intended viewport drifts, no raster layer
appears, hiding the named layer does not materially change map pixels, the
submitted image is absent or blank, the request exceeds its deadline, or the
response lacks successful `describe_map_screenshot` evidence. It also verifies
the response's collection and map centre, rejects contradictory coordinate
hemispheres, and requires an honest colour and uniformity description for a
single-colour thematic view.
