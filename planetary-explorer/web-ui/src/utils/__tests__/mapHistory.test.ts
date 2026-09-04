import { describe, expect, it } from 'vitest';

import {
  buildExpansionSearchBody,
  resolveLeafletTileSources,
  restoredLayerFromContext,
  restoredSearchDatetime,
  restorableHistoryModule,
} from '../mapHistory';

describe('map history restoration', () => {
  it('rejects disabled modules during restoration', () => {
    expect(restorableHistoryModule('comparison')).toBeNull();
    expect(restorableHistoryModule('mobility')).toBeNull();
    expect(restorableHistoryModule('forecast')).toBe('forecast');
    expect(restorableHistoryModule('timeseries')).toBe('timeseries');
    expect(restorableHistoryModule('terrain')).toBe('terrain');
  });

  it('rejects modules disabled by current deployment features', () => {
    const features = {
      mpcPro: false,
      fabric: false,
      resilience: false,
      weather: false,
    };

    expect(restorableHistoryModule('building_damage', features)).toBeNull();
    expect(restorableHistoryModule('site_audit', features)).toBeNull();
    expect(restorableHistoryModule('resilience', features)).toBeNull();
    expect(restorableHistoryModule('forecast', features)).toBeNull();
    expect(restorableHistoryModule('vision', features)).toBe('vision');
  });

  it('reconstructs a renderable layer from saved map context', () => {
    const layer = restoredLayerFromContext({
      bounds: {
        north: 48,
        south: 47,
        east: -121,
        west: -123,
        center_lat: 47.5,
        center_lng: -122,
      },
      current_collection: 'sentinel-2-l2a',
      stac_mode: 'public',
      imagery_url: 'https://tiles.example/{z}/{x}/{y}.png',
      item_id: 'item-1',
      datetime: '2026-08-26T00:00:00Z',
      tile_urls: [
        {
          tilejson_url: 'https://tiles.example/item-1/tilejson.json',
          item_id: 'item-1',
          stac_mode: 'public',
          bbox: [-123, 47, -122, 48],
        },
        {
          tilejson_url: 'https://tiles.example/item-2/tilejson.json',
          item_id: 'item-2',
          stac_mode: 'public',
          bbox: [-122, 47, -121, 48],
        },
      ],
    });

    expect(layer).toMatchObject({
      bbox: [-123, 47, -121, 48],
      tile_url: 'https://tiles.example/item-1/tilejson.json',
      items: [
        {
          id: 'item-1',
          collection: 'sentinel-2-l2a',
          stac_mode: 'public',
          bbox: [-123, 47, -122, 48],
        },
        {
          id: 'item-2',
          collection: 'sentinel-2-l2a',
          stac_mode: 'public',
          bbox: [-122, 47, -121, 48],
        },
      ],
      all_tile_urls: [
        {
          item_id: 'item-1',
          stac_mode: 'public',
          bbox: [-123, 47, -122, 48],
          tilejson_url: 'https://tiles.example/item-1/tilejson.json',
        },
        {
          item_id: 'item-2',
          stac_mode: 'public',
          bbox: [-122, 47, -121, 48],
          tilejson_url: 'https://tiles.example/item-2/tilejson.json',
        },
      ],
    });
  });

  it('prefers stable TileJSON when the saved imagery URL was redacted', () => {
    const layer = restoredLayerFromContext({
      imagery_url: 'https://storage.example/private.tif?<redacted>',
      current_collection: 'private-dem',
      tile_urls: [
        {
          tilejson_url: '/api/pro/tilejson?collection=private-dem&item=item-1',
          item_id: 'item-1',
          collection: 'private-dem',
        },
      ],
    });

    expect(layer.tile_url).toBe('/api/pro/tilejson?collection=private-dem&item=item-1');
    expect(layer.preview_url).toBe('/api/pro/tilejson?collection=private-dem&item=item-1');
  });

  it('restores each item catalog independently from the current map mode', () => {
    const layer = restoredLayerFromContext({
      stac_mode: 'pro',
      current_collection: 'cop-dem-glo-30',
      tile_urls: [
        {
          tilejson_url: 'https://tiles.example/public-dem.json',
          item_id: 'public-dem',
          collection: 'cop-dem-glo-30',
          stac_mode: 'public',
        },
      ],
    });

    expect(layer.items[0].stac_mode).toBe('public');
    expect(layer.all_tile_urls[0].stac_mode).toBe('public');
  });

  it('restores mosaic item provenance when no per-item tile URLs exist', () => {
    const layer = restoredLayerFromContext({
      stac_mode: 'pro',
      imagery_url: 'https://tiles.example/mosaic/{z}/{x}/{y}.png',
      current_collection: 'sentinel-2-l2a',
      scene_refs: [
        {
          id: 'public-scene',
          collection: 'sentinel-2-l2a',
          stac_mode: 'public',
          bbox: [-80, 43, -79, 44],
          datetime: '2026-06-15T00:00:00Z',
        },
      ],
    });

    expect(layer.items[0]).toMatchObject({
      id: 'public-scene',
      stac_mode: 'public',
      datetime: '2026-06-15T00:00:00Z',
    });
    expect(layer.all_tile_urls).toBeUndefined();
  });

  it('includes Pro mode in restored zoom expansion searches', () => {
    expect(buildExpansionSearchBody(
      'private-dem',
      [-122, 47, -121, 48],
      'pro',
      '2026-03-01/2026-05-31',
    ))
      .toMatchObject({
        collections: ['private-dem'],
        bbox: [-122, 47, -121, 48],
        stac_mode: 'pro',
        datetime: '2026-03-01/2026-05-31',
      });
  });

  it('restores only an explicit search window for zoom expansion', () => {
    expect(restoredSearchDatetime({
      datetime: '2026-05-22T00:00:00Z',
      search_datetime: '2026-03-01/2026-05-31',
    })).toBe('2026-03-01/2026-05-31');
    expect(restoredSearchDatetime({
      datetime: '2026-05-22T00:00:00Z',
    })).toBeNull();
  });

  it('resolves multiple TileJSON endpoints into Leaflet templates with per-tile bounds', async () => {
    // Arrange
    const fetchTileJson = async (url: string) => ({
      success: true,
      originalUrl: url,
      tileTemplate: url.replace('tilejson.json', '{z}/{x}/{y}.png'),
    });

    // Act
    const sources = await resolveLeafletTileSources(
      {
        all_tile_urls: [
          { tilejson_url: 'https://tiles.example/a/tilejson.json', bbox: [0, 1, 2, 3] },
          { tilejson_url: 'https://tiles.example/b/tilejson.json', bbox: [2, 1, 4, 3] },
        ],
      },
      'sentinel-2-l2a',
      fetchTileJson,
    );

    // Assert
    expect(sources).toEqual([
      { tileTemplate: 'https://tiles.example/a/{z}/{x}/{y}.png', bbox: [0, 1, 2, 3] },
      { tileTemplate: 'https://tiles.example/b/{z}/{x}/{y}.png', bbox: [2, 1, 4, 3] },
    ]);
  });
});