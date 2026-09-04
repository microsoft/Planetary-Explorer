<!-- markdownlint-disable-file -->
# PR Review Handoff: feature-chat-history-downloads

## PR Overview

This exact clean-commit review covers durable owner-scoped chat history,
attachments, replayable ZIP export, Azure deployment wiring, and map-state
restoration.

* Branch: `feature/chat-history-downloads`
* Target Commit: `21cf7e68cd7e0797e33e6ae38d9e3fce82fadcbd`
* Base Branch: `719044a74b5ca13b2a527aac3d10ef5520cc95d9`
* Target Tree: `c2771d31d7a0ca41d3aad3308828a12cd6d44cb7`
* Total Files Changed: 27
* Total Review Comments: 2
* Verdict: CHANGES REQUESTED

## PR Comments Ready for Submission

### File: MapView.tsx

#### Comment 1 (Lines 310 through 327)

* Category: Correctness, Concurrency
* Severity: MEDIUM

History restoration only invalidates Leaflet work. The Azure provider's
GeoJSON layers/sources are not tracked by this cleanup, and its delayed
GeoJSON and asynchronous multi-tile callbacks have no generation check. An
outgoing session's vectors can remain on the restored map, or an older render
can finish after cleanup and re-add stale layers. Track and remove Azure
vector layers plus sources, and use one generation token across both map
providers before any post-await/timer mutation.

**Suggested Change**

```typescript
const restoreGeneration = ++mapRenderGenerationRef.current;
removeTrackedAzureVectorLayersAndSources();

const results = await Promise.all(tilePromises);
if (restoreGeneration !== mapRenderGenerationRef.current) return;
```

### File: Chat.tsx

#### Comment 2 (Lines 2522 through 2574)

* Category: Data Loss, Concurrency
* Severity: MEDIUM

During retry backoff, the failed snapshot exists only in
`retryHistorySaveRef`. Component teardown clears its sole retry timer, while
the global Restart and landing controls can unmount `Chat` without waiting
for `historySaveState`. Restarting after a transient failure silently loses
that snapshot and any newer queued state. Keep the ordered queue outside the
component lifetime or block navigation until it drains; add an unmount-during-
backoff test that verifies the same mutation ID is retried.

**Suggested Change**

```typescript
await historySaveQueue.drain();
onRestartSession?.();
```

## Review Summary by Category

* Security Issues: 0
* Correctness and Concurrency: 1
* Data Loss: 1
* Deployment: 0
* Documentation: 0

## Validation

* ✅ Exact target, parent, tree, and clean worktree verified
* ✅ `git diff --check` passed
* ✅ Backend focused tests: 14 passed
* ✅ Frontend focused tests: 12 passed
* ✅ Production Vite bundle passed
* ✅ Bicep compilation passed
* ⚠️ Strict project TypeScript diagnostics remain nonzero; production bundling succeeds and the gate findings above are runtime issues independent of those diagnostics

## Instruction Compliance

* ✅ `python-script.instructions.md`: Changed runtime modules reviewed against applicable guidance
* ✅ `python-tests.instructions.md`: Changed tests reviewed and focused suites executed
* ✅ `markdown.instructions.md`: Tracking artifacts use the review-mode lint-disable convention
* ✅ `writing-style.instructions.md`: Findings are scoped, direct, and actionable