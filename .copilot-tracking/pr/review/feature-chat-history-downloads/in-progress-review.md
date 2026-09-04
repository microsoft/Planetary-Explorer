<!-- markdownlint-disable-file -->
# PR Review Status: feature-chat-history-downloads

## Review Status

* Phase: 4 - Finalize Handoff
* Last Updated: 2026-08-26T13:47:29.0237138-04:00
* Summary: Changes requested for two MEDIUM history-transition correctness and data-loss issues

## Branch and Metadata

* Normalized Branch: `feature-chat-history-downloads`
* Source Branch: `feature/chat-history-downloads`
* Target Commit: `21cf7e68cd7e0797e33e6ae38d9e3fce82fadcbd`
* Base Branch: `719044a74b5ca13b2a527aac3d10ef5520cc95d9`
* Direct Parent: `719044a74b5ca13b2a527aac3d10ef5520cc95d9`
* Target Tree: `c2771d31d7a0ca41d3aad3308828a12cd6d44cb7`
* Worktree: `C:\Users\chenalex\Planetary-Explorer-chat-history-pr`
* Worktree State: Clean at review initialization
* Linked Work Items: None supplied

## Author-Declared Intent

Persist owner-scoped sessions in Cosmos DB, store attachments in Blob Storage,
export replayable ZIP bundles, and add a responsive chat-history experience.
The gate specifically calls out ordered retries with idempotent mutation IDs,
deletion tombstones with ETags, Blob cleanup and activity renewal, 100 MB
threaded ZIP export, full transient/map/vector cleanup, complete multi-tile
render signatures, and generation-safe Leaflet TileJSON resolution with
per-tile bounds.

## Gate Criteria

* Review only correctness, security, data-loss, concurrency, and deployment issues
* Report only HIGH or MEDIUM severity findings
* Return `APPROVE` when no qualifying finding remains
* Treat the literal target and base SHAs as authoritative
* Do not modify product files in the reviewed worktree

## PR Overview

The one-commit change adds 11 files and modifies 16 files. The exact diff has
3,929 insertions and 57 deletions. Primary risk areas are owner isolation,
optimistic concurrency and retry ordering, deletion and Blob lifecycle,
streaming export limits, Azure private networking and RBAC, and deterministic
restoration of map state across overlapping asynchronous generations.

## Diff Mapping

| File | Type | Old Lines | New Lines | Focus Area |
|---|---|---|---|---|
| [chat_history_api.py](../../../../planetary-explorer/container-app/chat_history_api.py) | Added | none | 1-333 | Auth, upload, export, status mapping |
| [chat_history_store.py](../../../../planetary-explorer/container-app/chat_history_store.py) | Added | none | 1-930 | Ownership, ETag, retry, tombstone, Blob lifecycle |
| [fastapi_app.py](../../../../planetary-explorer/container-app/fastapi_app.py) | Modified | 349-354, 2682-2687 | 349-358, 2686-2692 | Router and feature wiring |
| [requirements.txt](../../../../planetary-explorer/container-app/requirements.txt) | Modified | 18-23 | 18-25 | Azure SDK runtime dependencies |
| [test_chat_history_api.py](../../../../planetary-explorer/container-app/tests/test_chat_history_api.py) | Added | none | 1-239 | API failure and ownership coverage |
| [test_chat_history_store.py](../../../../planetary-explorer/container-app/tests/test_chat_history_store.py) | Added | none | 1-268 | Store concurrency and lifecycle coverage |
| [web.bicep](../../../../planetary-explorer/infra/app/web.bicep) | Modified | 61-66, 87-92, 263-268, 318-323 | 61-84, 105-116, 287-324, 374-387 | Runtime settings, secrets, identity |
| [main.bicep](../../../../planetary-explorer/infra/main.bicep) | Modified | 51-56, 352-358, 361-366, 446-452, 460-465, 601-606, 641-646, 756-761 | 51-59, 355-361, 364-381, 461-467, 475-494, 630-641, 676-694, 804-810 | Module wiring, private endpoints, outputs |
| [chat-history-access.bicep](../../../../planetary-explorer/infra/shared/chat-history-access.bicep) | Added | none | 1-64 | Data-plane RBAC |
| [cosmos-chat-history.bicep](../../../../planetary-explorer/infra/shared/cosmos-chat-history.bicep) | Added | none | 1-119 | Cosmos account, database, container schema |
| [private-dns-zones.bicep](../../../../planetary-explorer/infra/shared/private-dns-zones.bicep) | Modified | 11-16, 23-28, 39-44, 220-225 | 11-17, 24-30, 41-62, 238-244 | Cosmos private DNS |
| [storage.bicep](../../../../planetary-explorer/infra/shared/storage.bicep) | Modified | 12-17, 45-50, 76-78 | 12-24, 52-98, 124-127 | Blob container and lifecycle policy |
| [package-lock.json](../../../../planetary-explorer/web-ui/package-lock.json) | Modified | 10-15, 2931-2936 | 10-16, 2932-2946 | ZIP dependency lock |
| [package.json](../../../../planetary-explorer/web-ui/package.json) | Modified | 19-24 | 19-25 | ZIP dependency declaration |
| [App.tsx](../../../../planetary-explorer/web-ui/src/App.tsx) | Modified | 8-13, 29-40, 81-86, 152-157, 189-194 | 8-14, 30-43, 84-90, 156-175, 207-214 | Feature flag propagation |
| [ChatHistoryDrawer.test.tsx](../../../../planetary-explorer/web-ui/src/components/__tests__/ChatHistoryDrawer.test.tsx) | Added | none | 1-121 | Drawer interaction coverage |
| [Chat.tsx](../../../../planetary-explorer/web-ui/src/components/Chat.tsx) | Modified | 2-14, 211-216, 237-242, 326-332, 368-373, 2482-2487, 2580-2588 | 2-22, 219-227, 248-256, 340-362, 398-410, 2519-2696, 2789-2827 | Autosave, retries, load/delete/export flow |
| [ChatHistoryDrawer.tsx](../../../../planetary-explorer/web-ui/src/components/ChatHistoryDrawer.tsx) | Added | none | 1-327 | Session operations and export UX |
| [MainApp.tsx](../../../../planetary-explorer/web-ui/src/components/MainApp.tsx) | Modified | 3-14, 19-29, 38-43, 127-132, 410-415, 442-447 | 3-15, 20-32, 41-48, 132-156, 434-441, 468-476 | State restoration and cleanup wiring |
| [MapView.tsx](../../../../planetary-explorer/web-ui/src/components/MapView.tsx) | Modified | 5-10, 79-84, 129-135, 245-250, 3282-3295, 4601-4653, 4665-4670, 5831-5839, 5853-5858 | 5-12, 81-88, 133-141, 251-418, 3450-3470, 4776-4840, 4852-4858, 6019-6028, 6042-6048 | Generation-safe map restore and cleanup |
| [api.chatHistory.test.ts](../../../../planetary-explorer/web-ui/src/services/__tests__/api.chatHistory.test.ts) | Added | none | 1-68 | Client protocol coverage |
| [api.ts](../../../../planetary-explorer/web-ui/src/services/api.ts) | Modified | 90-95, 101-111, 1127-1132 | 90-142, 148-162, 1178-1256 | Wire types and API methods |
| [GlobalStyles.tsx](../../../../planetary-explorer/web-ui/src/styles/GlobalStyles.tsx) | Modified | 922-927, 939-944 | 922-928, 940-1285 | Responsive drawer styling |
| [chatHistory.test.ts](../../../../planetary-explorer/web-ui/src/utils/__tests__/chatHistory.test.ts) | Added | none | 1-45 | Mutation ordering coverage |
| [mapHistory.test.ts](../../../../planetary-explorer/web-ui/src/utils/__tests__/mapHistory.test.ts) | Added | none | 1-91 | Render signature coverage |
| [chatHistory.ts](../../../../planetary-explorer/web-ui/src/utils/chatHistory.ts) | Added | none | 1-24 | Mutation queue ordering utility |
| [mapHistory.ts](../../../../planetary-explorer/web-ui/src/utils/mapHistory.ts) | Added | none | 1-101 | Map snapshot and render signatures |

## Instruction Files Reviewed

* `python-script.instructions.md`: Applies to all changed Python modules and tests
* `python-tests.instructions.md`: Applies cumulatively to all changed Python modules and tests
* `markdown.instructions.md`: Applies to this tracking document; review-mode template disables lint for the audit artifact
* `writing-style.instructions.md`: Applies to this tracking document
* No listed Bicep instruction matched these paths because its `applyTo` pattern is limited to `**/bicep/**`

## Review Plan

* [x] Backend API ownership, upload, status, and ZIP-export behavior
* [x] Cosmos/Blob persistence, optimistic concurrency, retries, and deletion lifecycle
* [x] Azure deployment topology, private DNS, lifecycle policy, identity, and RBAC
* [x] Frontend mutation queue, snapshot persistence, load/delete/export behavior
* [x] Map cleanup, TileJSON generation guards, bounds, and render signatures
* [x] Focused test execution and deployment-template validation

## Review Items

### 🔍 In Review

* None

### ✅ Approved for PR Comment

#### RI-01: Azure overlays survive or reappear after history restoration

* File: [MapView.tsx diff](pr-reference.xml#L3311-L3327)
* Lines: 310 through 327
* Category: Correctness, Concurrency
* Severity: MEDIUM

**Description**

The restore cleanup removes `currentLayer`, `activeTileLayersRef`, and
`leafletVectorLayersRef`, then invalidates only
`leafletRenderGenerationRef`. The Azure provider creates GeoJSON sources,
polygon layers, and line layers without storing them in any cleanup ref. It
also completes multi-tile `Promise.all` and delayed GeoJSON callbacks without
a generation check. Loading a saved session can therefore leave the outgoing
session's vector overlay on the map or allow an older tile/vector callback to
re-add stale layers after cleanup and overwrite the active-layer refs.

**Current Code**

```typescript
const staleLayers = new Set<any>([
	...(currentLayer ? [currentLayer] : []),
	...activeTileLayersRef.current,
	...leafletVectorLayersRef.current,
]);
// ...
leafletRenderGenerationRef.current += 1;
```

**Suggested Resolution**

Track Azure vector layers and their data sources, remove layers before their
sources during history restoration, and use one render-generation token for
both Azure and Leaflet paths. Every callback after an `await` or timer must
verify the generation before adding layers, updating refs, or moving the
camera. Add a test with a deferred TileJSON promise and fake Azure map that
loads history before the old render resolves.

**Applicable Instructions**

* Definitive gate scope: correctness and concurrency issues at MEDIUM or higher

**User Decision**: Reviewer-approved for definitive gate output

**Follow-up Notes**: Focused helper tests do not mount the Azure provider or exercise delayed callbacks.

#### RI-02: Restart silently discards an autosave waiting for retry

* File: [Chat.tsx diff](pr-reference.xml#L2629-L2631)
* Lines: 2522 through 2574
* Category: Data Loss, Concurrency
* Severity: MEDIUM

**Description**

After a transient save failure, the only copy of the failed snapshot remains
in `retryHistorySaveRef` and a timer owns the next attempt. The cleanup clears
that timer on unmount, while the global Restart and return-to-landing controls
can remount or unmount `Chat` without consulting `historySaveState`. Restarting
during the one-to-three-second backoff silently abandons the retry and any
newer coalesced snapshot, so the transcript shown before restart is not stored
despite the ordered retry design and stable mutation ID.

**Current Code**

```typescript
useEffect(() => () => {
	if (historyRetryTimerRef.current !== null) {
		window.clearTimeout(historyRetryTimerRef.current);
	}
}, []);
```

**Suggested Resolution**

Move the ordered queue to a service or provider whose lifetime exceeds the
`Chat` component, or gate restart/navigation until `drainHistorySaves`
settles. Teardown must not cancel the sole scheduled retry without durably
handing off its snapshot. Add a test that fails the first save, triggers
restart during backoff, and verifies the same mutation ID is retried before
the old session is released.

**Applicable Instructions**

* Definitive gate scope: data-loss and concurrency issues at MEDIUM or higher

**User Decision**: Reviewer-approved for definitive gate output

**Follow-up Notes**: The drawer blocks switching while saving, but the global Restart and landing navigation controls do not.

### ❌ Rejected / No Action

* The strict project-wide TypeScript check reports existing errors plus two new type-predicate shape errors in `mapHistory.ts`; the production Vite bundle succeeds, so these do not meet the requested HIGH/MEDIUM runtime or deployment threshold.
* Bicep compilation succeeds. Reported warnings are outside the changed chat-history resources or predate this commit.
* Azure Cosmos DB serverless availability was reviewed against current Microsoft documentation; no supported-region deployment defect was established.

## Action Log

* Verified `HEAD` equals the requested target SHA
* Verified the target has the requested base SHA as its sole parent
* Verified the requested base is the exact merge base
* Verified the target worktree is clean
* Cancelled one PowerShell parser continuation before it executed repository operations
* Generated `pr-reference.xml` with the literal base SHA and target `HEAD`
* Confirmed the target worktree remained clean after reference generation
* Parsed change types with `list-changed-files.ps1`
* Parsed reference size and chunk boundaries with `read-diff.ps1`
* Parsed all unified-diff hunk headers into exact old/new line mappings
* Reviewed authenticated owner resolution in `auth_middleware.py`
* Reviewed all changed backend persistence, API, tests, infrastructure, and frontend history/map control paths
* Ran 14 focused backend tests successfully with Python 3.11.9
* Ran 12 focused frontend tests successfully with Vitest 4.0.17
* Ran strict TypeScript diagnostics and separated existing/non-gating errors from release findings
* Removed JavaScript files accidentally emitted by an `npm exec` argument-forwarding error and restored the sole overwritten tracked file to the target SHA
* Reconfirmed the target worktree was clean immediately after cleanup
* Built the production frontend successfully with Vite 7.3.1 into a temporary directory
* Compiled `infra/main.bicep` successfully with Bicep 0.46.1
* Ran `git diff --check` successfully for the exact SHA pair
* Reconfirmed final `HEAD`, tree hash, sole parent, and clean target worktree

## Next Steps

* [x] Inspect backend controlling paths and their focused tests
* [x] Inspect infrastructure controlling paths and compile the Bicep entry point
* [x] Inspect frontend queue and map restoration controlling paths and run focused tests
* [x] Promote only HIGH or MEDIUM findings into the final handoff