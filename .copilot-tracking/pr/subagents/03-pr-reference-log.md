---
title: PR Reference Chunks 15-21 Review
description: Review of PR reference lines 7001-10500 for pull request description generation
---

## Chunks 15-21 Review

### Files Changed

* A boundary-spanning retry test file received additional tests for transient pre-dispatch failures and for suppressing retries after a tool-bearing run. Its path and file change mode appeared before line 7001 and were not visible in the assigned range.
* planetary-explorer/container-app/tests/test_get_started_queries.py was modified to treat its manifest as representative, align Canadian examples with explicit dates and coordinates, and verify cached collection locking.
* planetary-explorer/container-app/tests/test_location_resolver_country.py was modified to verify stored bounds for Calgary, Lake Ontario, Western Canada, and Lytton.
* planetary-explorer/container-app/tests/test_mobility_fast_path.py was added with endpoint, coverage, timeout, concurrency, and STAC-prefetch contracts for two-point mobility analysis.
* planetary-explorer/container-app/tests/test_netcdf_monthly_slices.py was added to verify complete monthly partitioning for 365-day, leap-year, 360-day, and irregular calendars.
* planetary-explorer/container-app/tests/test_raster_sampling_contract.py was added to cover metric inference, numeric-success requirements, provenance parsing, provider-aware item rehydration, and Landsat scale and offset rules.
* planetary-explorer/container-app/tests/test_render_intent_picker.py was modified to lock the Landsat tile scale and MODIS GPP asset and colormap configuration.
* planetary-explorer/container-app/tests/test_stac_inspection.py was added to verify pinned collection and AOI overrides plus collection-scoped asset summaries for public and Pro catalogs.
* planetary-explorer/container-app/tests/test_stac_mode_routing.py was modified to verify deterministic Pro remapping, V2 load ownership, selector bypass for locked collections, and lock preservation through alternative searches.
* planetary-explorer/container-app/tests/test_terrain_chat_fallback.py was added to verify shared Azure OpenAI synthesis after terrain-agent failure.
* planetary-explorer/container-app/tests/test_tile_selector_point_coverage.py was added to verify that point-sized AOIs preferred scenes whose geometry covered the query center without changing regional overlap scoring.
* planetary-explorer/container-app/tests/test_vision_tools_history_restore.py was modified to verify western-longitude formatting in vision context.
* planetary-explorer/container-app/tile_selector.py was modified to prefilter and rank center-covering geometries for small AOIs and retain the prior bbox overlap behavior for larger regions.
* planetary-explorer/weather-stub-server/README.md was modified to describe the service as a provider-contract adapter over operational NWP data, document MAI Weather, and distinguish adapter output from native model inference.
* planetary-explorer/weather-stub-server/app.py was modified to clamp precipitation to nonnegative values and return explicit provider, source, real-variable, fallback-variable, and native-inference provenance.
* planetary-explorer/weather-stub-server/test_app.py was added to verify nonnegative precipitation and the adapter provenance contract.
* planetary-explorer/web-ui/package-lock.json was modified to pin or update Axios 1.20.0, Vitest 4.1.11, Vite 7.3.6, esbuild 0.28.2, Playwright 1.62.1, Rollup 4.63.0, and related transitive packages.

### Technical Details

The Get Started tests moved away from claiming an exhaustive local manifest and pointed to the frontend gallery as the canonical inventory. Queries carried explicit Canadian coordinates and time windows, stored location bounds won over geocoding, and quick-start searches passed a locked collection through direct and alternative STAC paths. Pro collection remapping selected one stable best match per request, independent of inventory order, while V2 locked loads owned the legacy router bridge.

The mobility fast path required both destination coordinates, dispatched the two-point traverse directly, rejected incomplete geospatial coverage with a 503, and returned a 429 only for retry-safe pre-dispatch contention. The traverse tests also prevented empty prefetch results from triggering repeated STAC fanout, enforced an internal deadline, released admission after blocked supplementary work, and excluded known noncovering scenes from point sampling. These contracts supported deterministic execution and avoided duplicate side effects after an agent run had already used tools.

Raster and temporal computations gained explicit correctness contracts. Monthly NetCDF slicing consumed every sample, including the final December days, across common and irregular calendars. Raster sampling succeeded only when numeric values were present, preserved scene and date provenance without joining unrelated output blocks, selected public or Pro item hydration from item origin, and honored catalog or Landsat scale metadata.

Point-AOI tile selection treated geometries covering the query center as authoritative when bbox area was at most 0.1 square degrees. It filtered those scenes before date grouping and ranked them ahead of noncovering scenes, while large AOIs continued to use overlap scoring. STAC inspection summarized only the requested collection's actual assets and reported Pro remaps explicitly, which reduced misleading asset claims.

The weather service made its adapter status machine-readable. Responses always identified the provider contract, set native model inference to false, listed real and synthetic variables, retained the operational NWP source, and clamped perturbed precipitation at zero. The documentation preserved optional bearer-key authentication for local development and warned callers not to present adapter results as native Aurora, Earth-2, or MAI Weather inference.

The lockfile regenerated frontend build and test dependencies and added Playwright as a pinned development dependency. Playwright 1.62.1 declared Node 20 or later; the optional Linux x64 LZMA package declared a narrower Node range beginning at 22.20 or 24.12. Many artifacts changed from the public npm registry with SHA-512 integrity values to internal Microsoft feed URLs with SHA-1 values. Reviewers should confirm that this feed and integrity normalization was intended for reproducible installs.

Verification evidence in the range consisted of added and updated pytest cases for retry safety, quick-start locking, stored location bounds, mobility fast-path responses, NetCDF calendars, raster provenance, render configuration, STAC inspection and routing, terrain fallback, tile coverage, coordinate formatting, and weather provenance. No test command output or frontend test results appeared in lines 7001-10500, so the range evidenced coverage changes but not execution.

### Notable Patterns

* Contract tests were used to lock deterministic routing, collection ownership, provenance, coverage, and retry behavior before or alongside implementation.
* Point-based workflows preferred exact geometry and stored coordinates over broad bbox, cloud-cover, recency, or geocoding heuristics.
* Retry behavior was constrained to failures before dispatch; tool-bearing failed runs were left unretried to avoid repeating side effects.
* Public and Pro STAC handling preserved item origin and requested-to-resolved collection identity throughout search, sampling, and inspection.
* Weather outputs disclosed fallback and non-native status in both response data and documentation, reducing model-provenance ambiguity.
* The assigned range began inside one test diff and ended inside the web UI lockfile diff. The first file path and mode, plus any lockfile changes after line 10500, remained intentionally unresolved outside this review scope.
