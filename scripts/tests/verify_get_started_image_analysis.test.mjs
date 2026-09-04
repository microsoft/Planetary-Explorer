import assert from 'node:assert/strict';
import test from 'node:test';

import {
  adversarialMinimumZoom,
  assertReleaseUnchanged,
  assertProductionAllowed,
  deniesRequestedImagery,
  isBuildingDamageRequest,
  isExpectedApiOrigin,
} from '../verify_get_started_image_analysis.mjs';

test('allows a broad custom adversarial location without a scenario zoom floor', () => {
  const australia = [112, -44, 154, -10];

  assert.equal(adversarialMinimumZoom('Show imagery over Sydney', australia), 0);
  assert.equal(adversarialMinimumZoom('auto', australia), 7);
});

test('requires explicit consent for production browser verification', () => {
  assert.throws(
    () => assertProductionAllowed({
      appUrl: 'https://app.example',
      apiBaseUrl: 'https://api.example',
      allowProduction: false,
    }),
    /--allow-production/,
  );
  assert.doesNotThrow(() => assertProductionAllowed({
    appUrl: 'http://127.0.0.1:5173',
    apiBaseUrl: 'http://localhost:8000',
    allowProduction: false,
  }));
});

test('requires complete release binding for production browser verification', () => {
  assert.throws(
    () => assertProductionAllowed({
      appUrl: 'https://app.example',
      apiBaseUrl: 'https://api.example',
      allowProduction: true,
    }),
    /release binding values/,
  );
  assert.doesNotThrow(() => assertProductionAllowed({
    appUrl: 'https://app.example',
    apiBaseUrl: 'https://api.example',
    allowProduction: true,
    apiRevision: 'api--release-1',
    apiImageDigest: 'sha256:abc',
    weatherRevision: 'weather--release-1',
    weatherImageDigest: 'sha256:def',
    frontendDeploymentId: 'deploy-1',
    frontendBundle: 'index-release.js',
    frontendBundleSha256: '1234',
    azureSubscription: 'subscription-1',
    azureTenant: 'tenant-1',
    azureResourceGroup: 'rg-test',
    azureContainerApp: 'api-test',
    azureWeatherApp: 'weather-test',
    azureFrontendApp: 'web-test',
    azureGeofmResourceGroup: 'rg-geofm',
    azureGeofmWorker: 'worker-test',
  }));
});

test('rejects a response that says the requested MODIS layer is absent', () => {
  assert.equal(
    deniesRequestedImagery(
      'The image does not display any actual snow-cover data or MODIS satellite imagery.',
    ),
    true,
  );
});

test('accepts an observational description of a visible thematic layer', () => {
  assert.equal(
    deniesRequestedImagery(
      'The current MODIS snow-cover image is predominantly dark blue with lighter blue variation.',
    ),
    false,
  );
});

test('accepts no-variation observations about a visible raster', () => {
  assert.equal(
    deniesRequestedImagery(
      'There is no visible variation in the blue thematic field within the MODIS image around Quebec City.',
    ),
    false,
  );
  assert.equal(
    deniesRequestedImagery(
      'There is no noticeable variation in the purple tone in this satellite GPP image.',
    ),
    false,
  );
});

test('accepts an observation that requested features are not visible', () => {
  assert.equal(
    deniesRequestedImagery(
      'The supplied MODIS image contains no visible fire-intensity colours or clusters, only a uniform muted field.',
    ),
    false,
  );
});

test('rejects explicit requested layer absence', () => {
  assert.equal(
    deniesRequestedImagery('The requested MODIS raster layer is not visible in this screenshot.'),
    true,
  );
  assert.equal(
    deniesRequestedImagery('The supplied image does not show the requested raster layer.'),
    true,
  );
});

test('binds observed requests to the declared API origin', () => {
  assert.equal(
    isExpectedApiOrigin(
      'https://api.example/api/query/stream',
      'https://api.example',
    ),
    true,
  );
  assert.equal(
    isExpectedApiOrigin(
      'https://other-api.example/api/query/stream',
      'https://api.example',
    ),
    false,
  );
});

test('rejects release drift after browser scenarios complete', () => {
  const initial = {
    api_revision: 'api--release-1',
    verification: {
      verified_at: '2026-09-03T12:00:00Z',
      api_traffic_weight: 100,
    },
  };
  const changed = {
    api_revision: 'api--release-2',
    verification: {
      verified_at: '2026-09-03T12:30:00Z',
      api_traffic_weight: 100,
    },
  };

  assert.throws(
    () => assertReleaseUnchanged(initial, changed),
    /changed during browser scenario execution/,
  );
});

test('accepts a stable release with a newer verification timestamp', () => {
  const initial = {
    api_revision: 'api--release-1',
    verification: {
      verified_at: '2026-09-03T12:00:00Z',
      api_traffic_weight: 100,
    },
  };
  const current = structuredClone(initial);
  current.verification.verified_at = '2026-09-03T12:30:00Z';

  assert.doesNotThrow(() => assertReleaseUnchanged(initial, current));
});

test('matches Building Damage requests only on the declared API origin', () => {
  const body = { user_query: 'Assess potential building damage.' };

  assert.equal(
    isBuildingDamageRequest(
      'https://api.example/api/geoint/building-damage',
      'POST',
      body,
      body.user_query,
      'https://api.example',
    ),
    true,
  );
  assert.equal(
    isBuildingDamageRequest(
      'https://other.example/api/geoint/building-damage',
      'POST',
      body,
      body.user_query,
      'https://api.example',
    ),
    false,
  );
});