import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { isDeepStrictEqual } from 'node:util';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const WEB_UI = join(ROOT, 'planetary-explorer', 'web-ui');
const DEFAULT_APP_URL = 'http://127.0.0.1:5173/';
const DEFAULT_API_URL = 'http://127.0.0.1:8000';
const TORONTO_SETUP_QUERY = 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26';
const CALGARY_SETUP_QUERY = 'Show HLS S30 imagery at Calgary, Canada, latitude 51.0300, longitude -114.0800, from 2026-05-01 to 2026-08-26';
const DEFAULT_OUTPUT_DIR = join(
  ROOT,
  '.copilot-tracking',
  'get-started-validation',
  'image-analysis-browser',
);

function parseArgs(argv) {
  const options = {
    appUrl: DEFAULT_APP_URL,
    apiBaseUrl: DEFAULT_API_URL,
    outputDir: DEFAULT_OUTPUT_DIR,
    allowProduction: false,
    headed: false,
    limit: undefined,
    name: undefined,
    adversarialLocationQuery: undefined,
    proxyApiOrigin: undefined,
    requestTimeoutMs: 150_000,
    apiRevision: undefined,
    apiImageDigest: undefined,
    weatherRevision: undefined,
    weatherImageDigest: undefined,
    frontendDeploymentId: undefined,
    frontendBundle: undefined,
    frontendBundleSha256: undefined,
    azureSubscription: undefined,
    azureTenant: undefined,
    azureResourceGroup: undefined,
    azureContainerApp: undefined,
    azureWeatherApp: undefined,
    azureFrontendApp: undefined,
    azureGeofmResourceGroup: undefined,
    azureGeofmWorker: undefined,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === '--headed') options.headed = true;
    else if (argument === '--allow-production') options.allowProduction = true;
    else if (argument === '--app-url') options.appUrl = argv[++index];
    else if (argument === '--api-base-url') options.apiBaseUrl = argv[++index];
    else if (argument === '--output-dir') options.outputDir = argv[++index];
    else if (argument === '--limit') options.limit = Number(argv[++index]);
    else if (argument === '--name') options.name = argv[++index];
    else if (argument === '--adversarial-location-query') options.adversarialLocationQuery = argv[++index];
    else if (argument === '--proxy-api-origin') options.proxyApiOrigin = argv[++index];
    else if (argument === '--request-timeout-ms') options.requestTimeoutMs = Number(argv[++index]);
    else if (argument === '--api-revision') options.apiRevision = argv[++index];
    else if (argument === '--api-image-digest') options.apiImageDigest = argv[++index];
    else if (argument === '--weather-revision') options.weatherRevision = argv[++index];
    else if (argument === '--weather-image-digest') options.weatherImageDigest = argv[++index];
    else if (argument === '--frontend-deployment-id') options.frontendDeploymentId = argv[++index];
    else if (argument === '--frontend-bundle') options.frontendBundle = argv[++index];
    else if (argument === '--frontend-bundle-sha256') options.frontendBundleSha256 = argv[++index];
    else if (argument === '--azure-subscription') options.azureSubscription = argv[++index];
    else if (argument === '--azure-tenant') options.azureTenant = argv[++index];
    else if (argument === '--azure-resource-group') options.azureResourceGroup = argv[++index];
    else if (argument === '--azure-container-app') options.azureContainerApp = argv[++index];
    else if (argument === '--azure-weather-app') options.azureWeatherApp = argv[++index];
    else if (argument === '--azure-frontend-app') options.azureFrontendApp = argv[++index];
    else if (argument === '--azure-geofm-resource-group') options.azureGeofmResourceGroup = argv[++index];
    else if (argument === '--azure-geofm-worker') options.azureGeofmWorker = argv[++index];
    else throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

function isLoopbackUrl(value) {
  const hostname = new URL(value).hostname.replace(/^\[|\]$/g, '');
  return ['localhost', '127.0.0.1', '::1'].includes(hostname);
}

export function assertProductionAllowed(options) {
  const remoteUrls = [options.appUrl, options.apiBaseUrl, options.proxyApiOrigin]
    .filter(Boolean)
    .filter((value) => !isLoopbackUrl(value));
  if (remoteUrls.length > 0 && !options.allowProduction) {
    throw new Error(
      '--allow-production is required for every non-loopback app, API, or proxy origin.',
    );
  }
  if (remoteUrls.length > 0) {
    const requiredReleaseFields = [
      'apiRevision',
      'apiImageDigest',
      'weatherRevision',
      'weatherImageDigest',
      'frontendDeploymentId',
      'frontendBundle',
      'frontendBundleSha256',
      'azureSubscription',
      'azureTenant',
      'azureResourceGroup',
      'azureContainerApp',
      'azureWeatherApp',
      'azureFrontendApp',
      'azureGeofmResourceGroup',
      'azureGeofmWorker',
    ];
    const missing = requiredReleaseFields.filter((field) => !options[field]);
    if (missing.length > 0) {
      throw new Error(
        `Production verification requires release binding values: ${missing.join(', ')}.`,
      );
    }
  }
}

async function verifyRelease(options) {
  const values = [
    options.apiRevision,
    options.apiImageDigest,
    options.weatherRevision,
    options.weatherImageDigest,
    options.frontendDeploymentId,
    options.frontendBundle,
    options.frontendBundleSha256,
  ];
  if (!values.some(Boolean)) return {};
  const verifier = join(ROOT, 'scripts', 'verify_get_started_scenarios.py');
  const argumentsList = [
    verifier,
    '--verify-release-only',
    '--base-url', options.apiBaseUrl,
    '--allow-production',
    '--api-revision', options.apiRevision || '',
    '--api-image-digest', options.apiImageDigest || '',
    '--weather-revision', options.weatherRevision || '',
    '--weather-image-digest', options.weatherImageDigest || '',
    '--frontend-deployment-id', options.frontendDeploymentId || '',
    '--frontend-bundle', options.frontendBundle || '',
    '--frontend-bundle-sha256', options.frontendBundleSha256 || '',
    '--frontend-url', options.appUrl,
    '--azure-subscription', options.azureSubscription || '',
    '--azure-tenant', options.azureTenant || '',
    '--azure-resource-group', options.azureResourceGroup || '',
    '--azure-container-app', options.azureContainerApp || '',
    '--azure-weather-app', options.azureWeatherApp || '',
    '--azure-frontend-app', options.azureFrontendApp || '',
    '--azure-geofm-resource-group', options.azureGeofmResourceGroup || '',
    '--azure-geofm-worker', options.azureGeofmWorker || '',
  ];
  const output = execFileSync(process.env.PYTHON || 'python', argumentsList, {
    cwd: ROOT,
    encoding: 'utf8',
  });
  return JSON.parse(output);
}

function releaseBindingSnapshot(release) {
  const snapshot = structuredClone(release);
  if (snapshot.verification) {
    delete snapshot.verification.verified_at;
    if (Object.keys(snapshot.verification).length === 0) {
      delete snapshot.verification;
    }
  }
  return snapshot;
}

export function assertReleaseUnchanged(initialRelease, currentRelease) {
  if (!isDeepStrictEqual(
    releaseBindingSnapshot(initialRelease),
    releaseBindingSnapshot(currentRelease),
  )) {
    throw new Error('Release binding changed during browser scenario execution');
  }
}

function loadScenarios() {
  const verifier = join(ROOT, 'scripts', 'verify_get_started_scenarios.py');
  const output = execFileSync(process.env.PYTHON || 'python', [verifier, '--list'], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  return JSON.parse(output)
    .filter((scenario) => (
      (scenario.family.startsWith('Vision -') && scenario.image_query)
      || (scenario.family === 'Building Damage' && scenario.question)
    ))
    .map((scenario) => (
      scenario.family === 'Building Damage'
        ? { ...scenario, image_query: scenario.question }
        : scenario
    ));
}

function slug(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64);
}

function requestQuery(request) {
  try {
    return request.postDataJSON()?.query;
  } catch {
    return undefined;
  }
}

export function isExpectedApiOrigin(requestUrl, apiBaseUrl) {
  return new URL(requestUrl).origin === new URL(apiBaseUrl).origin;
}

function isQueryRequest(request, query, apiBaseUrl) {
  const url = new URL(request.url());
  return request.method() === 'POST'
    && isExpectedApiOrigin(url.href, apiBaseUrl)
    && (url.pathname === '/api/query' || url.pathname === '/api/query/stream')
    && requestQuery(request) === query;
}

export function isBuildingDamageRequest(requestUrl, method, body, query, apiBaseUrl) {
  const url = new URL(requestUrl);
  return method === 'POST'
    && isExpectedApiOrigin(url.href, apiBaseUrl)
    && url.pathname === '/api/geoint/building-damage'
    && body?.user_query === query;
}

function imageMetadata(bytes) {
  if (
    bytes.length >= 24
    && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))
  ) {
    return {
      format: 'png',
      width: bytes.readUInt32BE(16),
      height: bytes.readUInt32BE(20),
    };
  }
  if (bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 0xff) {
        offset += 1;
        continue;
      }
      const marker = bytes[offset + 1];
      if (marker === 0xd8 || marker === 0xd9) {
        offset += 2;
        continue;
      }
      const segmentLength = bytes.readUInt16BE(offset + 2);
      if (
        marker >= 0xc0
        && marker <= 0xcf
        && ![0xc4, 0xc8, 0xcc].includes(marker)
      ) {
        return {
          format: 'jpeg',
          width: bytes.readUInt16BE(offset + 7),
          height: bytes.readUInt16BE(offset + 5),
        };
      }
      if (segmentLength < 2) break;
      offset += segmentLength + 2;
    }
  }
  throw new Error('Screenshot payload is not a decodable PNG or JPEG image');
}

function parseSseResult(body) {
  let finalResult;
  for (const block of body.replace(/\r\n/g, '\n').split('\n\n')) {
    const lines = block.split('\n');
    const eventName = lines
      .find((line) => line.startsWith('event:'))
      ?.slice(6)
      .trim();
    const data = lines
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n');
    if (!data) continue;
    const payload = JSON.parse(data);
    if (eventName === 'error') throw new Error(payload.error || data);
    if (payload.type === 'query_result') finalResult = payload.payload;
  }
  if (!finalResult) throw new Error('Image Analysis stream has no final query_result');
  return finalResult;
}

function resultBbox(result) {
  const features = result?.data?.stac_results?.features || result?.results?.features || [];
  const candidates = [
    result?.translation_metadata?.stac_query?.bbox,
    result?.data?.search_metadata?.bbox,
    features[0]?.bbox,
  ];
  return candidates.find(
    (candidate) => Array.isArray(candidate)
      && candidate.length === 4
      && candidate.every(Number.isFinite),
  );
}

function requiredZoom(bbox) {
  const span = Math.max(Math.abs(bbox[2] - bbox[0]), Math.abs(bbox[3] - bbox[1]));
  if (span <= 0.03) return 13;
  if (span <= 0.15) return 11;
  if (span <= 0.6) return 9;
  return 7;
}

function haversineKm(left, right) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const deltaLatitude = radians(right.lat - left.lat);
  const deltaLongitude = radians(right.lng - left.lng);
  const latitudeA = radians(left.lat);
  const latitudeB = radians(right.lat);
  const haversine = Math.sin(deltaLatitude / 2) ** 2
    + Math.cos(latitudeA) * Math.cos(latitudeB) * Math.sin(deltaLongitude / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

async function waitForMapZoom(page, minimumZoom) {
  await page.waitForFunction((target) => (
    [...document.querySelectorAll('div, span')].some((element) => {
      const match = element.textContent?.trim().match(/^Z(\d+)$/);
      return match && Number(match[1]) >= target;
    })
  ), minimumZoom, { timeout: 60_000 });
  return page.evaluate(() => {
    for (const element of document.querySelectorAll('div, span')) {
      const match = element.textContent?.trim().match(/^Z(\d+)$/);
      if (match) return Number(match[1]);
    }
    return null;
  });
}

async function pixelEvidence(page, base64, format) {
  return page.evaluate(async ({ imageBase64, imageFormat }) => {
    const image = new Image();
    image.src = `data:image/${imageFormat};base64,${imageBase64}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    const colors = new Set();
    let redSum = 0;
    let greenSum = 0;
    let blueSum = 0;
    let luminanceSum = 0;
    let luminanceSquaredSum = 0;
    for (let index = 0; index < pixels.length; index += 4) {
      const red = pixels[index];
      const green = pixels[index + 1];
      const blue = pixels[index + 2];
      redSum += red;
      greenSum += green;
      blueSum += blue;
      const luminance = (0.2126 * red) + (0.7152 * green) + (0.0722 * blue);
      luminanceSum += luminance;
      luminanceSquaredSum += luminance * luminance;
      colors.add(`${red >> 3},${green >> 3},${blue >> 3}`);
    }
    const count = pixels.length / 4;
    const mean = luminanceSum / count;
    return {
      decodedWidth: image.naturalWidth,
      decodedHeight: image.naturalHeight,
      sampledColorBins: colors.size,
      meanRgb: [redSum, greenSum, blueSum].map((sum) => Number((sum / count).toFixed(2))),
      meanLuminance: Number(mean.toFixed(2)),
      luminanceVariance: Number((luminanceSquaredSum / count - mean * mean).toFixed(2)),
    };
  }, { imageBase64: base64, imageFormat: format });
}

function uniformColorTerms(pixels) {
  const [red, green, blue] = pixels.meanRgb;
  const maximum = Math.max(red, green, blue);
  const minimum = Math.min(red, green, blue);
  if (pixels.meanLuminance < 12) return ['black', 'dark'];
  if (pixels.meanLuminance > 242) return ['white', 'light'];
  if (maximum - minimum < 15) return ['gray', 'grey', 'neutral'];
  if (blue === maximum && red > green * 1.15) {
    return ['purple', 'violet', 'magenta', 'blue'];
  }
  if (blue === maximum) return ['blue', 'cyan'];
  if (green === maximum) return ['green'];
  if (green > blue * 1.15) return ['yellow', 'orange', 'brown', 'red'];
  return ['red', 'pink', 'magenta', 'brown'];
}

function uniformImageGroundingSentence(responseText, pixels) {
  const colorTerms = uniformColorTerms(pixels);
  const sentences = responseText.split(/(?<=[.!?])\s+|\n+/).filter(Boolean);
  return sentences.find((sentence) => {
    const normalized = sentence.toLowerCase();
    const namesCurrentImage = /\b(image|view|map|screenshot|visible|shown|appears)\b/i.test(sentence);
    const namesColor = colorTerms.some((term) => normalized.includes(term));
    const namesUniformity = /\b(uniform(?:ly)?|solid|single[- ]colou?r|only one colou?r|no visible variation|no variation)\b/i.test(sentence);
    return namesCurrentImage && namesColor && namesUniformity;
  });
}

function coordinateContradiction(text, pin) {
  const pattern = /(-?\d+(?:\.\d+)?)\s*(?:\u00b0|degrees?)?\s*([NSEW])\b/gi;
  for (const match of text.matchAll(pattern)) {
    const magnitude = Math.abs(Number(match[1]));
    const direction = match[2].toUpperCase();
    if ('EW'.includes(direction) && Math.abs(magnitude - Math.abs(pin.lng)) <= 1) {
      const interpreted = direction === 'E' ? magnitude : -magnitude;
      if (Math.abs(interpreted - pin.lng) > 1) return match[0];
    }
    if ('NS'.includes(direction) && Math.abs(magnitude - Math.abs(pin.lat)) <= 1) {
      const interpreted = direction === 'N' ? magnitude : -magnitude;
      if (Math.abs(interpreted - pin.lat) > 1) return match[0];
    }
  }
  return null;
}

async function imageDifference(page, visibleBytes, hiddenBytes) {
  return page.evaluate(async ({ visibleBase64, hiddenBase64 }) => {
    const decode = async (base64) => {
      const image = new Image();
      image.src = `data:image/png;base64,${base64}`;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = 96;
      canvas.height = 96;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      return context.getImageData(0, 0, canvas.width, canvas.height).data;
    };
    const visible = await decode(visibleBase64);
    const hidden = await decode(hiddenBase64);
    let changedPixels = 0;
    let absoluteDifference = 0;
    for (let index = 0; index < visible.length; index += 4) {
      const difference = (
        Math.abs(visible[index] - hidden[index])
        + Math.abs(visible[index + 1] - hidden[index + 1])
        + Math.abs(visible[index + 2] - hidden[index + 2])
      ) / 3;
      absoluteDifference += difference;
      if (difference >= 3) changedPixels += 1;
    }
    const pixelCount = visible.length / 4;
    return {
      changedPixelRatio: Number((changedPixels / pixelCount).toFixed(4)),
      meanAbsoluteDifference: Number((absoluteDifference / pixelCount).toFixed(2)),
    };
  }, {
    visibleBase64: visibleBytes.toString('base64'),
    hiddenBase64: hiddenBytes.toString('base64'),
  });
}

async function withTimeout(promise, timeoutMs, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(
      () => reject(new Error(`${label} timed out after ${timeoutMs} ms`)),
      timeoutMs,
    );
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    clearTimeout(timer);
  }
}

function toolNames(result) {
  return (result.tools_used || []).map((tool) => (
    typeof tool === 'string' ? tool : tool?.tool || tool?.name
  )).filter(Boolean);
}

export function deniesRequestedImagery(responseText) {
  const sentences = String(responseText || '')
    .split(/(?<=[.!?])\s+|\n+/)
    .map((sentence) => sentence.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const requestedImagery = '(?:requested|actual|satellite|MODIS|Landsat|Sentinel|HLS|snow-cover|radar|GPP|vegetation)';
  const imageryObject = '(?:imagery|image|data|layer|overlay|raster)';
  const requestedObject = `${requestedImagery}.{0,30}${imageryObject}`;
  const patterns = [
    new RegExp(
      `${requestedObject}.{0,40}(?:is|are|was|were)?\\s*`
        + '(?:not\\s+(?:visible|present|displayed|shown|rendered|included|available)|absent|missing|unavailable)',
      'i',
    ),
    new RegExp(
      `(?:no|without|lacks?)\\s+(?:actual\\s+|requested\\s+)?${requestedObject}`,
      'i',
    ),
    new RegExp(
      `(?:(?:provided|shown|supplied)\\s+)?${imageryObject}`
        + `(?:\\s+(?:provided|shown|supplied))?.{0,20}`
        + "(?:does not|doesn't|did not)\\s+(?:display|show|contain|include|render)\\s+"
        + `(?:(?:any|the)\\s+)?${requestedObject}`,
      'i',
    ),
  ];
  return sentences.some((sentence) => patterns.some((pattern) => pattern.test(sentence)));
}

async function waitForQuery(page, query, action, apiBaseUrl, timeout = 150_000) {
  const requestPromise = page.waitForRequest(
    (request) => isQueryRequest(request, query, apiBaseUrl),
    { timeout },
  );
  await action();
  const request = await requestPromise;
  const response = await withTimeout(
    request.response(),
    30_000,
    `Response headers for ${query}`,
  );
  if (!response) throw new Error(`No HTTP response for query: ${query}`);
  await withTimeout(response.finished(), timeout, `Response body for ${query}`);
  if (response.status() !== 200) {
    throw new Error(`Query returned HTTP ${response.status()}: ${query}`);
  }
  return { request, response };
}

async function waitForBuildingDamage(
  page,
  query,
  action,
  apiBaseUrl,
  timeout = 150_000,
) {
  const requestPromise = page.waitForRequest((request) => {
    let body;
    try {
      body = request.postDataJSON();
    } catch {
      return false;
    }
    return isBuildingDamageRequest(
      request.url(),
      request.method(),
      body,
      query,
      apiBaseUrl,
    );
  }, { timeout });
  await action();
  const request = await requestPromise;
  const response = await withTimeout(
    request.response(),
    30_000,
    `Response headers for ${query}`,
  );
  if (!response) throw new Error(`No HTTP response for query: ${query}`);
  await withTimeout(response.finished(), timeout, `Response body for ${query}`);
  if (response.status() !== 200) {
    throw new Error(`Building Damage returned HTTP ${response.status()}: ${query}`);
  }
  return { request, response };
}

async function openVisionTab(modal) {
  const selector = modal.locator('.vision-selector');
  if (!await selector.evaluate((element) => element.classList.contains('active'))) {
    await selector.click();
  }
}

async function openScenarioTab(modal, scenario) {
  if (scenario.family === 'Building Damage') {
    const selector = modal.locator('.damage-selector');
    if (await selector.isDisabled()) return false;
    if (!await selector.evaluate((element) => element.classList.contains('active'))) {
      await selector.click();
    }
    return true;
  }
  await openVisionTab(modal);
  return true;
}

async function ensureMinimumMapZoom(page, minimumZoom) {
  let zoom = await page.evaluate(() => {
    for (const element of document.querySelectorAll('div, span')) {
      const match = element.textContent?.trim().match(/^Z(\d+)$/);
      if (match) return Number(match[1]);
    }
    return null;
  });
  const zoomIn = page.getByTitle('Zoom In');
  for (let attempts = 0; Number(zoom) < minimumZoom && attempts < 20; attempts += 1) {
    await zoomIn.click();
    await page.waitForTimeout(150);
    zoom = await page.evaluate(() => {
      for (const element of document.querySelectorAll('div, span')) {
        const match = element.textContent?.trim().match(/^Z(\d+)$/);
        if (match) return Number(match[1]);
      }
      return null;
    });
  }
  return waitForMapZoom(page, minimumZoom);
}

function adversarialQueryForScenario(configuredQuery, scenario) {
  if (configuredQuery !== 'auto') return configuredQuery;
  return scenario.setup_query === TORONTO_SETUP_QUERY
    ? CALGARY_SETUP_QUERY
    : TORONTO_SETUP_QUERY;
}

export function adversarialMinimumZoom(configuredQuery, bbox) {
  return configuredQuery === 'auto' ? requiredZoom(bbox) : 0;
}

async function runScenario(browser, scenario, index, options) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  if (options.proxyApiOrigin) {
    const apiOrigin = new URL(options.proxyApiOrigin).origin;
    await context.route(`${apiOrigin}/**`, async (route) => {
      try {
        const response = await route.fetch({
          maxRetries: 0,
          timeout: options.requestTimeoutMs,
        });
        await route.fulfill({ response });
      } catch {
        await route.abort('connectionfailed');
      }
    });
  }
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  const scenarioSlug = `${String(index + 1).padStart(2, '0')}-${slug(scenario.location)}`;
  const started = Date.now();
  const diagnostics = {};
  const isBuildingDamage = scenario.family === 'Building Damage';

  try {
    await page.goto(options.appUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.locator('.get-started-button').waitFor({ state: 'visible', timeout: 60_000 });
    if (options.adversarialLocationQuery) {
      const staleQuery = adversarialQueryForScenario(
        options.adversarialLocationQuery,
        scenario,
      );
      const staleTurn = await waitForQuery(
        page,
        staleQuery,
        async () => {
          const textbox = page.getByRole('textbox');
          await textbox.fill(staleQuery);
          await page.getByRole('button', { name: 'Send', exact: true }).click();
        },
        options.apiBaseUrl,
        options.requestTimeoutMs,
      );
      const staleResult = parseSseResult((await staleTurn.response.body()).toString('utf8'));
      const staleNavigate = staleResult.navigate_to;
      const staleBbox = resultBbox(staleResult);
      const staleLatitude = Number.isFinite(staleNavigate?.latitude)
        ? staleNavigate.latitude
        : staleBbox
          ? (staleBbox[1] + staleBbox[3]) / 2
          : undefined;
      const staleLongitude = Number.isFinite(staleNavigate?.longitude)
        ? staleNavigate.longitude
        : staleBbox
          ? (staleBbox[0] + staleBbox[2]) / 2
          : undefined;
      if (
        !Number.isFinite(staleLatitude)
        || !Number.isFinite(staleLongitude)
      ) {
        throw new Error(`Adversarial location did not navigate: ${staleQuery}`);
      }
      diagnostics.adversarial_location = {
        query: staleQuery,
        latitude: staleLatitude,
        longitude: staleLongitude,
        session_id: staleTurn.request.postDataJSON()?.session_id,
      };
      await page.locator('[title="Geointelligence Modules"]').waitFor({
        state: 'visible',
        timeout: 60_000,
      });
      if (staleBbox) {
        await waitForMapZoom(
          page,
          adversarialMinimumZoom(options.adversarialLocationQuery, staleBbox),
        );
        await page.waitForTimeout(2_500);
      }
      await page.locator('[title="Geointelligence Modules"]').click();
      await page.getByText('Vision Analysis', { exact: true }).click();
      const staleMap = page.getByRole('region', { name: 'Interactive map' });
      const staleMapBox = await staleMap.boundingBox();
      if (!staleMapBox) throw new Error('Adversarial map has no clickable bounding box');
      await staleMap.click({
        position: { x: staleMapBox.width * 0.5, y: staleMapBox.height * 0.5 },
      });
      await page.locator('.row.assistant').filter({ hasText: 'Pin Placed' }).last().waitFor({
        state: 'visible',
        timeout: 60_000,
      });
    }
    await page.locator('.get-started-button').click();
    const modal = page.locator('.get-started-modal-content');
    await modal.waitFor({ state: 'visible' });
    if (!await openScenarioTab(modal, scenario)) {
      return {
        family: scenario.family,
        location: scenario.location,
        setup_query: scenario.setup_query,
        image_query: scenario.image_query,
        outcome: 'blocked',
        elapsed_ms: Date.now() - started,
        blocked_reason: 'MPC Pro tenant imagery is disabled in this deployment.',
      };
    }

    const setupCard = modal
      .locator(isBuildingDamage ? '.building-damage-card' : '.stac-card')
      .filter({ hasText: scenario.setup_query })
      .first();
    await setupCard.waitFor({ state: 'visible' });
    const setup = await waitForQuery(
      page,
      scenario.setup_query,
      () => (
        isBuildingDamage
          ? setupCard.locator('.setup-query').getByRole('button', { name: 'Go', exact: true }).click()
          : setupCard.getByRole('button', { name: 'Go', exact: true }).click()
      ),
      options.apiBaseUrl,
      options.requestTimeoutMs,
    );
    const setupResult = parseSseResult((await setup.response.body()).toString('utf8'));
    if (options.adversarialLocationQuery) {
      const setupRequest = setup.request.postDataJSON();
      const staleFields = [
        'pin',
        'vision_pin',
        'map_bounds',
        'current_collection',
        'loaded_collections',
        'stac_items',
        'tile_urls',
        'imagery_base64',
        'geoint_module',
        'conversation_history',
      ].filter((field) => setupRequest[field] !== undefined);
      diagnostics.setup_context_reset = {
        stale_fields: staleFields,
        geoint_mode: setupRequest.geoint_mode,
        session_changed: setupRequest.session_id !== diagnostics.adversarial_location.session_id,
      };
      if (staleFields.length > 0) {
        throw new Error(`Setup request retained stale context fields: ${staleFields.join(', ')}`);
      }
      if (setupRequest.geoint_mode !== false) {
        throw new Error(`Setup request retained GEOINT mode: ${setupRequest.geoint_mode}`);
      }
      if (!diagnostics.setup_context_reset.session_changed) {
        throw new Error('Setup request reused the adversarial location session');
      }
    }
    const bbox = resultBbox(setupResult);
    if (!bbox) throw new Error('Setup response has no usable map viewport');
    const expectedPin = {
      lat: (bbox[1] + bbox[3]) / 2,
      lng: (bbox[0] + bbox[2]) / 2,
    };
    diagnostics.setup_bbox = bbox;
    diagnostics.expected_pin = expectedPin;
    await page.locator('.row.user').filter({ hasText: scenario.setup_query }).waitFor({
      state: 'visible',
      timeout: 60_000,
    });
    await page.locator('[title="Geointelligence Modules"]').waitFor({
      state: 'visible',
      timeout: 60_000,
    });
    diagnostics.map_zoom = await waitForMapZoom(page, requiredZoom(bbox));
    await page.waitForTimeout(2_500);

    const layersButton = page.getByRole('button', { name: 'Map layers' });
    await layersButton.waitFor({ state: 'visible', timeout: 60_000 });
    await layersButton.click();
    const imageryRow = page.locator('[data-layer-id="imagery"]');
    await imageryRow.waitFor({ state: 'visible' });
    diagnostics.imagery_layer = await imageryRow.locator('.map-layer-selector__label').innerText();
    const visibilityButton = imageryRow.getByRole('button', { name: / visibility$/ });
    if (await visibilityButton.getAttribute('aria-pressed') !== 'true') {
      throw new Error('Requested imagery layer is not visible');
    }
    await layersButton.click();
    const map = page.getByRole('region', { name: 'Interactive map' });
    const paintDeadline = Date.now() + 25_000;
    do {
      await page.waitForTimeout(2_500);
      const visibleMap = await map.screenshot();
      await layersButton.click();
      await visibilityButton.click();
      await layersButton.click();
      await page.waitForTimeout(750);
      const hiddenMap = await map.screenshot();
      diagnostics.imagery_difference = await imageDifference(page, visibleMap, hiddenMap);
      await layersButton.click();
      await visibilityButton.click();
      await layersButton.click();
      if (
        diagnostics.imagery_difference.changedPixelRatio >= 0.01
        && diagnostics.imagery_difference.meanAbsoluteDifference >= 0.5
      ) break;
    } while (Date.now() < paintDeadline);
    if (
      diagnostics.imagery_difference.changedPixelRatio < 0.01
      || diagnostics.imagery_difference.meanAbsoluteDifference < 0.5
    ) {
      throw new Error(
        `Requested imagery layer does not materially change map pixels: ${JSON.stringify(diagnostics.imagery_difference)}`,
      );
    }
    await page.waitForTimeout(1_000);

    if (isBuildingDamage) {
      diagnostics.map_zoom = await ensureMinimumMapZoom(page, 16);
    }
    await page.locator('[title="Geointelligence Modules"]').click();
    await page.getByText(
      isBuildingDamage ? 'Building Damage' : 'Vision Analysis',
      { exact: true },
    ).click();
    const mapBox = await map.boundingBox();
    if (!mapBox) throw new Error('Interactive map has no clickable bounding box');
    await map.click({ position: { x: mapBox.width * 0.5, y: mapBox.height * 0.5 } });
    await page.locator('.row.assistant').filter({ hasText: 'Pin Placed' }).last().waitFor({
      state: 'visible',
      timeout: 60_000,
    });

    await page.locator('.get-started-button').click();
    await modal.waitFor({ state: 'visible' });
    await openScenarioTab(modal, scenario);
    const imageCard = modal
      .locator(isBuildingDamage ? '.building-damage-card' : '.screenshot-card')
      .filter({ hasText: scenario.image_query })
      .first();
    await imageCard.waitFor({ state: 'visible' });
    const analysisAction = () => (
      isBuildingDamage
        ? imageCard.locator('.building-damage-question').getByRole('button', { name: 'Go', exact: true }).click()
        : imageCard.getByRole('button', { name: 'Go', exact: true }).click()
    );
    const analysis = isBuildingDamage
      ? await waitForBuildingDamage(
        page,
        scenario.image_query,
        analysisAction,
        options.apiBaseUrl,
        options.requestTimeoutMs,
      )
      : await waitForQuery(
        page,
        scenario.image_query,
        analysisAction,
        options.apiBaseUrl,
        options.requestTimeoutMs,
      );

    const requestBody = analysis.request.postDataJSON();
      const imageBase64 = isBuildingDamage
        ? requestBody.screenshot
        : requestBody.imagery_base64;
    diagnostics.submitted_pin = isBuildingDamage
      ? { lat: requestBody.latitude, lng: requestBody.longitude }
      : requestBody.vision_pin || requestBody.pin;
    if (!diagnostics.submitted_pin) {
      throw new Error('Image Analysis request has no submitted pin');
    }
    diagnostics.pin_distance_km = Number(
      haversineKm(expectedPin, diagnostics.submitted_pin).toFixed(2),
    );
    if (diagnostics.pin_distance_km > 15) {
      throw new Error(
        `Submitted pin is ${diagnostics.pin_distance_km} km from the intended viewport center`,
      );
    }
    if (typeof imageBase64 !== 'string' || imageBase64.length < 1_000) {
      throw new Error(`Image Analysis request has no substantive screenshot (${imageBase64?.length || 0} chars)`);
    }
    const imageBytes = Buffer.from(imageBase64, 'base64');
    const metadata = imageMetadata(imageBytes);
    if (metadata.width < 100 || metadata.height < 100) {
      throw new Error(`Screenshot dimensions are too small: ${metadata.width}x${metadata.height}`);
    }
    const pixels = await pixelEvidence(page, imageBase64, metadata.format);
    const uniformBlank = pixels.sampledColorBins < 8
      && (pixels.meanLuminance < 3 || pixels.meanLuminance > 248);
    if (uniformBlank) {
      throw new Error(`Screenshot appears blank: ${JSON.stringify(pixels)}`);
    }
    const imagePath = join(options.outputDir, 'payload-images', `${scenarioSlug}.${metadata.format === 'jpeg' ? 'jpg' : 'png'}`);
    mkdirSync(dirname(imagePath), { recursive: true });
    writeFileSync(imagePath, imageBytes);

    const responseBody = (await analysis.response.body()).toString('utf8');
    if (isBuildingDamage) {
      if (requestBody.stac_mode !== 'pro') {
        throw new Error(`Building Damage request used ${requestBody.stac_mode || '(missing)'} mode`);
      }
      if (!Array.isArray(requestBody.stac_items) || requestBody.stac_items.length === 0) {
        throw new Error('Building Damage request has no MPC Pro scene references');
      }
      const result = JSON.parse(responseBody);
      const analysisResult = result?.result || {};
      const imageryMetadata = analysisResult.imagery_metadata || {};
      const responseText = String(analysisResult.response || analysisResult.summary || '');
      const requestedSceneIds = requestBody.stac_items
        .map((item) => item?.id)
        .filter(Boolean);
      const tools = (analysisResult.tool_calls || [])
        .map((tool) => tool?.tool || tool?.name)
        .filter(Boolean);
      diagnostics.tools_used = tools;
      diagnostics.structured_evidence = imageryMetadata;
      diagnostics.response_excerpt = responseText.slice(0, 1000);
      if (result.status !== 'success' || analysisResult.agent !== 'building_damage_vision') {
        throw new Error(`Building Damage response is incomplete: ${responseBody.slice(0, 1000)}`);
      }
      if (imageryMetadata.source !== 'MPC Pro server-rendered tile') {
        throw new Error(`Building Damage used untrusted imagery: ${imageryMetadata.source || '(missing)'}`);
      }
      if (!requestedSceneIds.includes(imageryMetadata.item_id)) {
        throw new Error(
          `Building Damage analyzed an unsubmitted scene: ${imageryMetadata.item_id || '(missing)'}`,
        );
      }
      if (!responseText) {
        throw new Error('Building Damage returned no assessment text');
      }
      const contradiction = coordinateContradiction(responseText, diagnostics.submitted_pin);
      if (contradiction) {
        throw new Error(`Building Damage response contradicts the submitted coordinates: ${contradiction}`);
      }
      await page.locator('.row.assistant').last().waitFor({
        state: 'visible',
        timeout: 30_000,
      });
      const browserPath = join(options.outputDir, 'browser-screenshots', `${scenarioSlug}.png`);
      mkdirSync(dirname(browserPath), { recursive: true });
      await page.screenshot({ path: browserPath, fullPage: false });
      if (pageErrors.length > 0) {
        throw new Error(`Browser page errors: ${pageErrors.join(' | ')}`);
      }
      return {
        family: scenario.family,
        location: scenario.location,
        setup_query: scenario.setup_query,
        image_query: scenario.image_query,
        outcome: 'pass',
        elapsed_ms: Date.now() - started,
        setup_http_status: setup.response.status(),
        analysis_http_status: analysis.response.status(),
        setup_bbox: bbox,
        expected_pin: expectedPin,
        submitted_pin: diagnostics.submitted_pin,
        pin_distance_km: diagnostics.pin_distance_km,
        map_zoom: diagnostics.map_zoom,
        imagery_layer: diagnostics.imagery_layer,
        imagery_difference: diagnostics.imagery_difference,
        screenshot: {
          format: metadata.format,
          byte_length: imageBytes.length,
          width: metadata.width,
          height: metadata.height,
          ...pixels,
          path: imagePath,
        },
        tools_used: tools,
        structured_success: true,
        evidence_collection: imageryMetadata.collection,
        evidence_item_id: imageryMetadata.item_id,
        evidence_source: imageryMetadata.source,
        response_excerpt: responseText.slice(0, 1000),
        browser_screenshot: browserPath,
      };
    }
    const result = parseSseResult(responseBody);
    const tools = toolNames(result);
    const evidence = result.structured?.describe_map_screenshot;
    const responseText = String(result.response || evidence?.answer || '');
    diagnostics.tools_used = tools;
    diagnostics.structured_evidence = evidence;
    diagnostics.response_excerpt = responseText.slice(0, 1000);
    if (!tools.includes('describe_map_screenshot')) {
      throw new Error(`Image Analysis did not report describe_map_screenshot: ${JSON.stringify(tools)}`);
    }
    if (evidence?.success !== true || evidence?.error) {
      throw new Error(`Image Analysis structured evidence is incomplete: ${JSON.stringify(evidence)}`);
    }
    if (deniesRequestedImagery(responseText)) {
      throw new Error('Image Analysis response says the requested imagery is not visible');
    }
    const imageryMetadata = evidence?.structured?.imagery_metadata;
    const evidenceBounds = imageryMetadata?.bounds;
    const evidencePin = {
      lat: evidenceBounds?.center_lat,
      lng: evidenceBounds?.center_lng,
    };
    if (!Number.isFinite(evidencePin.lat) || !Number.isFinite(evidencePin.lng)) {
      throw new Error('Image Analysis evidence has no grounded map center');
    }
    diagnostics.evidence_pin_distance_km = Number(
      haversineKm(diagnostics.submitted_pin, evidencePin).toFixed(2),
    );
    if (diagnostics.evidence_pin_distance_km > 15) {
      throw new Error(
        `Image Analysis evidence center is ${diagnostics.evidence_pin_distance_km} km from the submitted pin`,
      );
    }
    if (imageryMetadata?.collection !== requestBody.current_collection) {
      throw new Error(
        `Image Analysis evidence collection mismatch: ${imageryMetadata?.collection || '(missing)'}`,
      );
    }
    const contradiction = coordinateContradiction(responseText, diagnostics.submitted_pin);
    if (contradiction) {
      throw new Error(`Image Analysis response contradicts the submitted coordinates: ${contradiction}`);
    }
    const uniformThematicImage = pixels.sampledColorBins < 8
      && pixels.luminanceVariance < 1;
    if (uniformThematicImage) {
      diagnostics.uniform_grounding_sentence = uniformImageGroundingSentence(
        responseText,
        pixels,
      );
      if (!diagnostics.uniform_grounding_sentence) {
        throw new Error(
          `No sentence describes the current uniform image with its visible colour: ${JSON.stringify(pixels)}`,
        );
      }
    }
    if (requestBody.current_collection === 'modis-17A2H-061') {
      if (!/\bGPP\b|gross primary productivity/i.test(responseText)) {
        throw new Error('MODIS 17A2H response does not identify Gross Primary Productivity (GPP)');
      }
      if (/\bNPP\b|net primary productivity/i.test(responseText)) {
        throw new Error('MODIS 17A2H response incorrectly identifies the GPP product as NPP');
      }
    }
    await page.locator('[title*="describe_map_screenshot"]').last().waitFor({
      state: 'visible',
      timeout: 30_000,
    });
    const browserPath = join(options.outputDir, 'browser-screenshots', `${scenarioSlug}.png`);
    mkdirSync(dirname(browserPath), { recursive: true });
    await page.screenshot({ path: browserPath, fullPage: false });

    if (pageErrors.length > 0) {
      throw new Error(`Browser page errors: ${pageErrors.join(' | ')}`);
    }
    return {
      family: scenario.family,
      location: scenario.location,
      setup_query: scenario.setup_query,
      image_query: scenario.image_query,
      outcome: 'pass',
      elapsed_ms: Date.now() - started,
      setup_http_status: setup.response.status(),
      analysis_http_status: analysis.response.status(),
      adversarial_location: diagnostics.adversarial_location,
      setup_context_reset: diagnostics.setup_context_reset,
      setup_bbox: bbox,
      expected_pin: expectedPin,
      submitted_pin: diagnostics.submitted_pin,
      pin_distance_km: diagnostics.pin_distance_km,
      map_zoom: diagnostics.map_zoom,
      imagery_layer: diagnostics.imagery_layer,
      imagery_difference: diagnostics.imagery_difference,
      screenshot: {
        format: metadata.format,
        byte_length: imageBytes.length,
        width: metadata.width,
        height: metadata.height,
        ...pixels,
        path: imagePath,
      },
      tools_used: tools,
      structured_success: evidence.success,
      evidence_pin_distance_km: diagnostics.evidence_pin_distance_km,
      evidence_collection: imageryMetadata.collection,
      uniform_image_grounded: uniformThematicImage ? true : undefined,
      uniform_grounding_sentence: diagnostics.uniform_grounding_sentence,
      response_excerpt: responseText.slice(0, 1000),
      browser_screenshot: browserPath,
    };
  } catch (error) {
    const failurePath = join(options.outputDir, 'failures', `${scenarioSlug}.png`);
    mkdirSync(dirname(failurePath), { recursive: true });
    await page.screenshot({ path: failurePath, fullPage: false }).catch(() => undefined);
    return {
      family: scenario.family,
      location: scenario.location,
      setup_query: scenario.setup_query,
      image_query: scenario.image_query,
      outcome: 'fail',
      elapsed_ms: Date.now() - started,
      error: error instanceof Error ? error.stack || error.message : String(error),
      diagnostics,
      page_errors: pageErrors,
      failure_screenshot: failurePath,
    };
  } finally {
    await context.close();
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  assertProductionAllowed(options);
  const release = await verifyRelease(options);
  let scenarios = loadScenarios();
  if (options.name) {
    const needle = options.name.toLowerCase();
    scenarios = scenarios.filter((scenario) => (
      scenario.location.toLowerCase().includes(needle)
      || scenario.setup_query.toLowerCase().includes(needle)
    ));
  }
  if (options.limit !== undefined) scenarios = scenarios.slice(0, options.limit);
  if (scenarios.length === 0) throw new Error('No matching Image Analysis scenarios');

  const requireFromWebUi = createRequire(join(WEB_UI, 'package.json'));
  let chromium;
  try {
    ({ chromium } = requireFromWebUi('playwright'));
  } catch {
    throw new Error(
      'Playwright is unavailable. Run `npm install --no-save --package-lock=false playwright@1.62.1` in planetary-explorer/web-ui.',
    );
  }

  mkdirSync(options.outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: !options.headed });
  const results = [];
  try {
    for (let index = 0; index < scenarios.length; index += 1) {
      const scenario = scenarios[index];
      process.stderr.write(`[${index + 1}/${scenarios.length}] ${scenario.location} ... `);
      const result = await runScenario(browser, scenario, index, options);
      results.push(result);
      process.stderr.write(`${result.outcome.toUpperCase()} (${result.elapsed_ms} ms)\n`);
      writeFileSync(
        join(options.outputDir, 'results.json'),
        `${JSON.stringify({ generated_at: new Date().toISOString(), app_url: options.appUrl, release, release_verification_complete: false, results }, null, 2)}\n`,
      );
    }
  } finally {
    await browser.close();
  }
  const currentRelease = await verifyRelease(options);
  assertReleaseUnchanged(release, currentRelease);
  writeFileSync(
    join(options.outputDir, 'results.json'),
    `${JSON.stringify({ generated_at: new Date().toISOString(), app_url: options.appUrl, release: currentRelease, release_verification_complete: true, results }, null, 2)}\n`,
  );
  const failed = results.filter((result) => result.outcome === 'fail');
  console.log(JSON.stringify({ total: results.length, passed: results.length - failed.length, failed: failed.length }, null, 2));
  process.exitCode = failed.length > 0 ? 1 : 0;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}