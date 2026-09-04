---
title: Get Started String Synchronization Research
description: Compares canonical Get Started strings with backend, test, verification, chat, and README copies.
ms.date: 2026-09-02
ms.topic: reference
---

## Research Scope

* Compare canonical source strings in `planetary-explorer/web-ui/src/config/canadianExamples.ts` against `quickstart_cache.py`, Chat examples, `tests/test_get_started_queries.py`, the relevant README content, and `scripts/verify_get_started_scenarios.py`.
* Identify exact stale or mismatched strings that require synchronization for functional correctness or documentation.
* Make no product-code or documentation edits.

## Working Hypothesis

Named consumers duplicate canonical query literals and may have drifted after current edits. An exact set comparison of exported canonical prompts against literals and assertions in each consumer will distinguish stale copies from intentional variants.

## Findings

### Canonical inventory

The canonical TypeScript exports contain 30 unique setup strings and 74 unique
prompt strings across setup, raster, screenshot, and specialized analysis
actions. Two setup strings are reused by different scenario families.

### Quick-start cache

`planetary-explorer/container-app/quickstart_cache.py` has all 12 canonical
Vision setup queries after case normalization, with no missing or extra keys.
The snow query uses February 2025 and the Mackenzie River query names Norman
Wells. No query-string synchronization is required for functional cache
matching.

Nine returned description labels remain shorter or different from the
canonical UI descriptions. These do not affect lookup, but they should be
synchronized if backend classifications must present the same descriptive
copy as the Get Started modal.

```text
Cache:     10m surface-reflectance imagery for Greater Toronto
Canonical: 10m surface-reflectance imagery for the Greater Toronto Area

Cache:     30m harmonized Sentinel-2 imagery over Calgary
Canonical: 30m harmonized Landsat and Sentinel-2 imagery over Calgary

Cache:     Landsat surface reflectance over coastal Nova Scotia
Canonical: Landsat Collection 2 surface reflectance over coastal Nova Scotia

Cache:     Daily active-fire and thermal-anomaly observations
Canonical: Daily 1km active-fire and thermal-anomaly observations

Cache:     8-day vegetation productivity composites
Canonical: 8-day vegetation productivity composites over British Columbia

Cache:     500m daily snow cover and NDSI
Canonical: 500m archived daily snow cover and normalized-difference snow index

Cache:     30m terrain elevation for current-year analysis
Canonical: 30m elevation used for current-year terrain analysis

Cache:     10m terrain-corrected radar backscatter
Canonical: 10m terrain-corrected radar backscatter for Metro Vancouver

Cache:     All-weather spring flood observations
Canonical: All-weather radar observations for spring flood monitoring
```

### Chat examples

The three default suggestions and the four MODIS suggestions in
`planetary-explorer/web-ui/src/components/Chat.tsx` are exact canonical setup
strings after the February 2025 edit. Seven dataset-specific suggestions are
stale paraphrases of canonical setup strings.

```text
Stale:     Show Landsat imagery over Halifax from 2026-01-01 to 2026-08-26
Canonical: Show Landsat imagery over Halifax, Canada from 2026-01-01 to 2026-08-26

Stale:     Find Landsat scenes over Hudson Bay from 2026-06-01 to 2026-08-26
Canonical: Show Landsat imagery of Hudson Bay, Canada from 2026-06-01 to 2026-08-26

Stale:     Show Sentinel-2 imagery over Toronto from 2026-06-01 to 2026-08-26
Canonical: Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26

Stale:     Show Halifax coastal patterns from 2026-06-01 to 2026-08-26
Canonical: Show Sentinel-2 imagery over Halifax, Canada from 2026-06-01 to 2026-08-26

Stale:     Show Sentinel-1 RTC over Vancouver from 2026-01-01 to 2026-08-26
Canonical: Show Sentinel-1 RTC radar imagery over Vancouver, Canada from 2026-01-01 to 2026-08-26

Stale:     Map Red River flooding from 2026-03-01 to 2026-05-31 using Sentinel-1
Canonical: Show Sentinel-1 RTC radar imagery over the Red River, Manitoba from 2026-03-01 to 2026-05-31

Stale:     Show Banff terrain analysis for 2026 infrastructure planning
Canonical: Show Copernicus DEM terrain around Banff, Canada for 2026 analysis
```

Other Chat suggestions are dataset-specific supplemental examples, not stale
copies of a canonical row. The component currently computes `examples` but
does not render it because the example block was removed. These seven strings
therefore have no current runtime effect, but should be synchronized before
the suggestions are displayed again or the dormant code is retained as
documentation.

### Backend Get Started tests

`planetary-explorer/container-app/tests/test_get_started_queries.py` contains
30 query literals. Nine are exact canonical prompts, 19 Get Started-like
literals are noncanonical, and two are intentional special cases. The special
cases are `tell me about this area` and
`Compare NDVI in Toronto between June 1 and August 26, 2026.`.

Sixteen stale literals have direct current replacements.

```text
Stale:     Sample the 2026 coastal surface-reflectance bands at this Halifax location.
Canonical: Sample the 2026 coastal surface-reflectance bands at this location.

Stale:     Sample the NDSI (snow index) value at this point.
Canonical: Sample the February 2025 NDSI value at this Quebec location.

Stale:     What is the elevation in metres at this Banff point for 2026 analysis?
Canonical: Sample the exact Copernicus DEM pixel elevation in metres at this Banff pin; do not return an area mean or range.

Stale:     What are the VV and VH backscatter values in dB?
Canonical: What are the 2026 VV and VH backscatter values in dB?

Stale:     Describe what you see in this satellite image. What land cover types are visible?
Canonical: Describe urban growth and vegetation patterns visible around Calgary in 2026.

Stale:     Can you see any active fire hotspots or burn scars in this thermal imagery?
Canonical: Explain the fire-intensity colours and identify clusters visible in Alberta.

Stale:     Describe the water bodies and flood patterns visible in this water occurrence map.
Canonical: Identify water, urban, forest, and shoreline features in this 2026 Halifax image.

Stale:     Describe the 2026 Banff terrain view, including valleys, ridges, and steep slopes.
Canonical: Explain the elevation colours and identify valleys, slopes, and peaks.

Stale:     Assess 2026 coastal flood exposure and environmental sensitivity for this Halifax site. What is the permitting recommendation?
Canonical: Assess 2026 coastal flood exposure, environmental sensitivity, and permitting constraints for this Halifax site.

Stale:     For 2026 planning, which direction do the Calgary-area slopes face? What is the sun exposure rating for solar installation?
Canonical: Analyze 2026 terrain elevation, slope, and line-of-sight near Calgary at 51.0447N, 114.0719W.

Stale:     For 2026 planning, can vehicles traverse this Kananaskis route? Assess terrain obstacles, steep slopes, and ground-vehicle feasibility.
Canonical: Using 2026 conditions, classify vehicle traversability between these pins across five elevation layers and identify steep terrain barriers.

Stale:     For a 2026 search-and-rescue plan, can a helicopter land safely in the North Shore Mountains? Analyze slopes, flat landing zones, and vegetation density.
Canonical: For a 2026 search-and-rescue plan, identify flat helicopter landing zones between these pins and explain slope and vegetation constraints.

Stale:     Assess this 2026 Yukon emergency-supply route. Identify water crossings, wildfire exposure, steep slopes, and terrain barriers.
Canonical: Assess this 2026 emergency-supply route for water crossings, wildfire exposure, steep slopes, and ground-vehicle feasibility.

Stale:     What are the projected daily maximum and minimum temperatures for Toronto during 2026 under SSP585? Is extreme heat increasing?
Canonical: Show monthly projected precipitation for Toronto in 2026 and identify the wettest month.

Stale:     What is the projected annual precipitation and peak daily rainfall for Vancouver in 2026? How does this relate to coastal and Fraser River flood risk?
Canonical: What are the projected annual precipitation and peak daily rainfall values for Vancouver in 2026?

Stale:     What are the projected 2026 precipitation levels for Montreal? Is peak daily rainfall increasing, and what does this mean for urban flooding?
Canonical: What are the projected temperature and precipitation trends for Montreal during 2026 under SSP245 and SSP585?
```

Three stale test literals have no current canonical counterpart and should not
be represented as Get Started coverage unless intentionally retained as
non-gallery contract tests.

```text
What is the elevation range and slope distribution at this location?
Is this Winnipeg-area site suitable for a solar farm in 2026? Check flat areas, water proximity, and setback requirements.
Compare the moderate (SSP245) and worst-case (SSP585) climate scenarios for Halifax during 2026. How do temperature and precipitation projections differ for this Atlantic coast?
```

The test header calls this manifest the single source of truth and says each
query is an exact string from `GetStartedButton.tsx`. Both claims are stale:
the source is `web-ui/src/config/canadianExamples.ts`, and most test literals
do not match it. Coverage also omits six of 12 Vision setup prompts, six of 12
Vision raster prompts, eight of 12 Vision screenshot prompts, and every Site
Intel, Resilience, Forecast, and Building Damage analysis prompt. Importing or
generating from the canonical registry would prevent recurring string drift.

### Root README

The root `README.md` presents these rows as query examples. Fourteen rows are
stale or shortened counterparts of current Get Started prompts.

```text
Stale:     Show MODIS daily snow cover over Quebec from 2026-02-01 to 2026-02-28
Canonical: Show MODIS daily snow cover over Quebec from 2025-02-01 to 2025-02-28

Stale:     Analyze this 2026 Toronto satellite image. Identify land cover and explain the natural-colour legend.
Canonical: Explain the colours in this 2026 Toronto image and identify visible land-cover types.

Stale:     Analyze 2026 elevation, slope, and line-of-sight near Calgary at 51.0447N, 114.0719W.
Canonical: Analyze 2026 terrain elevation, slope, and line-of-sight near Calgary at 51.0447N, 114.0719W.

Stale:     Classify 2026 terrain traversability between two Kananaskis pins across five elevation layers.
Canonical: Using 2026 conditions, classify vehicle traversability between these pins across five elevation layers and identify steep terrain barriers.

Stale:     Use my MPC Pro 2026 before-and-after aerial collection to assess building damage in Jasper, Alberta.
Canonical: Using the 2026 before-and-after tenant imagery, assess potential building damage and distinguish destroyed, major-damage, and unaffected structures.

Stale:     Compute the 2026 precipitation trend for Toronto and identify the wettest projected period.
Canonical: Show monthly projected precipitation for Toronto in 2026 and identify the wettest month.

Stale:     Compare Montreal temperature and precipitation during 2026 under SSP245 and SSP585.
Canonical: What are the projected temperature and precipitation trends for Montreal during 2026 under SSP245 and SSP585?

Stale:     Give me an August 26-31, 2026 five-day ensemble forecast over Lake Ontario.
Canonical: Give me a 120-hour (five-day) forecast over Lake Ontario using every available model and summarize ensemble spread.

Stale:     Forecast 2m temperature and 10m wind across southern Saskatchewan for August 26-28, 2026.
Canonical: Forecast 2m temperature and 10m wind across southern Saskatchewan for the next 72 hours.

Stale:     Compare Aurora and Earth-2 FCN precipitation over Nova Scotia for August 27, 2026.
Canonical: Compare Aurora and Earth-2 FCN precipitation over Nova Scotia for the next 24 hours and explain model disagreement.

Stale:     For 2026, score candidate data-centre sites near Calgary for power, water, competition, and hazard.
Canonical: For 2026, score our candidate data-centre sites near Calgary for power, water, competition, wildfire, flood, and heat exposure.

Stale:     For the week of August 26, 2026, which Canadian facilities are at risk and what is the supply-chain blast radius?
Canonical: Over the next seven days, which Canadian facilities are most at risk and what is the supply-chain blast radius?

Stale:     If our Vancouver distribution centre goes offline for 48 hours in 2026, which downstream facilities are exposed?
Canonical: If our Vancouver distribution centre goes offline for 48 hours in 2026, which downstream Canadian facilities are exposed?

Stale:     Show 2026 heat and wildfire risk for all Western Canada facilities this week, ranked by severity.
Canonical: Show 2026 heat and wildfire risk for all Western Canada facilities this week, ranked by severity with a response playbook.
```

The generic Raster, Comparison, and Foundation Change rows describe broader
features and do not have direct canonical Get Started counterparts. They are
not classified as stale string copies in this comparison.

### Scenario verifier

`scripts/verify_get_started_scenarios.py` dynamically compiles and loads the
TypeScript exports for every prompt. Its only duplicated prompt contract is
the `EXPECTED_SETUP` key set. It contains exactly the same 30 unique setup
strings as the canonical source, with no missing or extra keys. No string
synchronization is required.

## Evidence

* Canonical registry: `planetary-explorer/web-ui/src/config/canadianExamples.ts`
* Cache keys and descriptions: `planetary-explorer/container-app/quickstart_cache.py`
* Dormant dataset suggestions: `planetary-explorer/web-ui/src/components/Chat.tsx`
* Independent test manifest: `planetary-explorer/container-app/tests/test_get_started_queries.py`
* Documentation examples: `README.md`
* Dynamic verifier and setup contract: `scripts/verify_get_started_scenarios.py`
* Exact set check result: 30 canonical unique setup strings, 30 verifier keys, zero missing, zero extra; 12 canonical Vision setup strings, 12 normalized cache keys, zero missing, zero extra
* Exact test check result: 30 test query literals, nine exact canonical prompts, 19 noncanonical Get Started-like prompts, and two intentional non-gallery special cases

## Follow-On Questions

* Decide whether backend cache descriptions are intended to be byte-for-byte UI copy or deliberately concise API metadata.
* Decide whether dormant Chat suggestions should import canonical setup strings or be removed until that UI is restored.
* Replace the manually duplicated backend test manifest with a generated or shared fixture if exact gallery coverage remains a test requirement.

## Clarifying Questions

None.
