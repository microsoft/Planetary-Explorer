import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MapView from '../MapView';

const analysisResult = {
  result: {
    analysis: 'Canadian 2026 terrain analysis',
    features_identified: ['ridge', 'valley', 'water'],
    imagery_metadata: { source: 'Sentinel-2', date: '2026-08-26' },
  },
};

const createHlsFireResponse = (): any => {
  const tilejsonUrl = (
    'https://example.test/tilejson.json?assets=B12&assets=B8A&assets=B04'
    + '&rescale=3,3486&rescale=0,4950&rescale=0,3320'
  );
  return {
    data: {
      stac_results: {
        features: [{
          id: 'HLS.S30.T15UYR.2026185T165839.v2.0',
          collection: 'hls2-s30',
          bbox: [-89.8672, 50.258, -89.8472, 50.278],
          properties: { datetime: '2026-07-04T17:09:44Z' },
          assets: {},
        }],
      },
    },
    translation_metadata: {
      original_query: 'Show HLS S30 fire false-colour imagery',
      stac_query: { bbox: [-89.8672, 50.258, -89.8472, 50.278] },
      render_profile: { id: 'hls-s30-fire-false-colour' },
      all_tile_urls: [{
        item_id: 'HLS.S30.T15UYR.2026185T165839.v2.0',
        bbox: [-89.8672, 50.258, -89.8472, 50.278],
        tilejson_url: tilejsonUrl,
      }],
      mosaic_tilejson: null,
    },
  };
};

const createTilelessResponse = () => ({
  data: {
    stac_results: {
      features: [{
        id: 'GOES-GLM-no-raster',
        collection: 'goes-glm',
        bbox: [-90, 50, -89, 51],
        properties: { datetime: '2026-07-05T00:00:00Z' },
        assets: {},
      }],
    },
  },
  translation_metadata: {
    stac_query: { bbox: [-90, 50, -89, 51] },
    all_tile_urls: [],
  },
});

const apiMocks = vi.hoisted(() => ({
  triggerGeointAnalysis: vi.fn(),
}));

const tileJsonMocks = vi.hoisted(() => ({
  fetchAndSignTileJSON: vi.fn(),
}));

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return { ...actual, triggerGeointAnalysis: apiMocks.triggerGeointAnalysis };
});

vi.mock('../../services/authHelper', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/authHelper')>();
  return {
    ...actual,
    authenticatedFetch: vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        azureMaps: {
          subscriptionKey: 'DEVELOPMENT_MODE_NO_KEY',
          developmentMode: true,
        },
      }),
    }),
  };
});

vi.mock('../../utils/tileJsonFetcher', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../utils/tileJsonFetcher')>();
  return { ...actual, fetchAndSignTileJSON: tileJsonMocks.fetchAndSignTileJSON };
});

const createMapInstance = () => {
  const instance = {
    events: {
      add: vi.fn((event: string, handler: () => void) => {
        if (event === 'ready') handler();
      }),
      remove: vi.fn(),
    },
    markers: { add: vi.fn(), remove: vi.fn() },
    sources: { add: vi.fn(), remove: vi.fn(), getById: vi.fn() },
    layers: {
      add: vi.fn(),
      remove: vi.fn(),
      getLayerById: vi.fn(),
      getLayers: vi.fn().mockReturnValue([]),
      move: vi.fn(),
    },
    setCamera: vi.fn(),
    getCamera: vi.fn().mockReturnValue({
      center: [-106.3468, 56.1304],
      zoom: 3,
      bounds: [-110, 50, -100, 60],
    }),
    setStyle: vi.fn(),
    dispose: vi.fn(),
  };
  return instance;
};

const atlasMock: any = {
  Map: vi.fn().mockImplementation(function MockMap() {
    return createMapInstance();
  }),
  HtmlMarker: vi.fn().mockImplementation(function MockHtmlMarker(options) {
    return { options, setOptions: vi.fn() };
  }),
  AuthenticationType: { subscriptionKey: 'subscriptionKey' },
  data: { Position: vi.fn((longitude, latitude) => [longitude, latitude]) },
};

const leafletMock = {
  map: vi.fn(),
  tileLayer: vi.fn(),
  marker: vi.fn(),
  icon: vi.fn(),
  latLng: vi.fn((latitude, longitude) => ({ lat: latitude, lng: longitude })),
  latLngBounds: vi.fn((southWest, northEast) => ({ southWest, northEast })),
};

const geoFmPolygonSetOptions = vi.fn();
const geoFmLineSetOptions = vi.fn();
const imageryLayerSetOptions = vi.fn();

Object.assign(atlasMock, {
  source: {
    DataSource: vi.fn().mockImplementation(function MockDataSource() {
      return { add: vi.fn() };
    }),
  },
  layer: {
    PolygonLayer: vi.fn().mockImplementation(function MockPolygonLayer() {
      return { setOptions: geoFmPolygonSetOptions };
    }),
    LineLayer: vi.fn().mockImplementation(function MockLineLayer() {
      return { setOptions: geoFmLineSetOptions };
    }),
    TileLayer: vi.fn().mockImplementation(function MockTileLayer() {
      return {
        getId: vi.fn().mockReturnValue('planetary-explorer-tiles-test'),
        setOptions: imageryLayerSetOptions,
      };
    }),
  },
});

const renderMap = (props: React.ComponentProps<typeof MapView> = { selectedDataset: null }) =>
  render(<MapView {...props} />);

const lastMockValue = (mock: { mock: { results: Array<{ value: any }> } }) => (
  mock.mock.results[mock.mock.results.length - 1]?.value
);

const openModulePicker = async () => {
  const button = await screen.findByTitle('Geointelligence Modules');
  fireEvent.click(button);
  await screen.findByText('Geointelligence Modules');
};

describe('GEOINT module flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.triggerGeointAnalysis.mockResolvedValue(analysisResult);
    tileJsonMocks.fetchAndSignTileJSON.mockResolvedValue({
      success: true,
      tileTemplate: 'https://example.test/{z}/{x}/{y}.png',
      tilejson: { tilejson: '3.0.0', tiles: ['https://example.test/{z}/{x}/{y}.png'] },
      originalUrl: 'https://example.test/tilejson.json',
    });
    (globalThis as any).atlas = atlasMock;
    (globalThis as any).L = leafletMock;
  });

  it('opens the current module picker after the map is ready', async () => {
    renderMap();

    await openModulePicker();

    expect(atlasMock.Map).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ center: [-106.3468, 56.1304], zoom: 3 }),
    );
    expect(screen.getByText('Terrain Analysis')).toBeInTheDocument();
    expect(screen.getByText('Mobility Assessment')).toBeInTheDocument();
    expect(screen.getByText('Resilience')).toBeInTheDocument();
  });

  it('selects terrain and enables its pin workflow in one action', async () => {
    const onGeointAnalysis = vi.fn();
    const onModuleSelected = vi.fn();
    renderMap({ selectedDataset: null, onGeointAnalysis, onModuleSelected });
    await openModulePicker();

    fireEvent.click(screen.getByText('Terrain Analysis'));

    expect(onModuleSelected).toHaveBeenCalledWith('terrain');
    expect(onGeointAnalysis).toHaveBeenCalledWith({
      type: 'module_selected',
      message: '**Terrain selected.**',
    });
    expect(screen.queryByText('Geointelligence Modules')).not.toBeInTheDocument();
  });

  it('clears map-owned module and pin state before a Get Started Setup', async () => {
    const onPinChange = vi.fn();
    const onModuleSelected = vi.fn();
    renderMap({ selectedDataset: null, onPinChange, onModuleSelected });
    await openModulePicker();
    fireEvent.click(screen.getByText('Mobility Assessment'));

    const map = lastMockValue(atlasMock.Map);
    const clickHandler = await waitFor(() => {
      const handler = map.events.add.mock.calls
        .filter(([event]: [string]) => event === 'click')
        .at(-1)?.[1];
      expect(handler).toBeTypeOf('function');
      return handler;
    });
    act(() => clickHandler({ position: [-115, 50.7] }));

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query: 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26',
        clearSessions: true,
        resetContext: true,
      },
    })));

    await waitFor(() => {
      expect(onModuleSelected).toHaveBeenLastCalledWith(null);
      expect(onPinChange).toHaveBeenLastCalledWith(null);
    });
    expect(map.markers.remove).toHaveBeenCalled();
  });

  it('does not emit stale terrain output after a Get Started Setup', async () => {
    const onGeointAnalysis = vi.fn();
    renderMap({ selectedDataset: null, onGeointAnalysis });
    await openModulePicker();
    fireEvent.click(screen.getByText('Terrain Analysis'));

    const map = lastMockValue(atlasMock.Map);
    map.getCamera.mockReturnValue({
      center: [-106.3468, 56.1304],
      zoom: 10,
      bounds: [-110, 50, -100, 60],
    });
    const clickHandler = await waitFor(() => {
      const handler = map.events.add.mock.calls
        .filter(([event]: [string]) => event === 'click')
        .at(-1)?.[1];
      expect(handler).toBeTypeOf('function');
      return handler;
    });

    vi.useFakeTimers();
    try {
      act(() => clickHandler({ position: [-115, 50.7] }));
      act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
        detail: {
          query: 'Whitehorse, Yukon, Canada',
          clearSessions: true,
          resetContext: true,
        },
      })));
      const callCountAfterReset = onGeointAnalysis.mock.calls.length;

      await act(async () => vi.runAllTimersAsync());

      expect(onGeointAnalysis).toHaveBeenCalledTimes(callCountAfterReset);
    } finally {
      vi.useRealTimers();
    }
  });

  it('removes rendered imagery before a navigation-only Get Started Setup', async () => {
    renderMap({ selectedDataset: null, lastChatResponse: createHlsFireResponse() });
    await waitFor(() => expect(imageryLayerSetOptions).toHaveBeenCalled());
    expect(await screen.findByRole('button', { name: 'Map layers' })).toBeInTheDocument();
    const map = lastMockValue(atlasMock.Map);

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query: 'Whitehorse, Yukon, Canada',
        clearSessions: true,
        resetContext: true,
      },
    })));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Map layers' })).not.toBeInTheDocument();
    });
    expect(map.layers.remove).toHaveBeenCalled();
  });

  it('places a Canadian pin with the universal drop-pin control', async () => {
    const onPinChange = vi.fn();
    renderMap({ selectedDataset: null, onPinChange });
    const dropPinButton = await screen.findByTitle('Drop Pin: click the map to place a pin and ask any question about that location');
    fireEvent.click(dropPinButton);

    const map = lastMockValue(atlasMock.Map);
    const clickHandler = await waitFor(() => {
      const handler = map.events.add.mock.calls
        .filter(([event]: [string]) => event === 'click')
        .at(-1)?.[1];
      expect(handler).toBeTypeOf('function');
      return handler;
    });
    act(() => clickHandler({ position: [-79.3832, 43.6532] }));

    await waitFor(() => {
      expect(onPinChange).toHaveBeenCalledWith({ lat: 43.6532, lng: -79.3832 });
    });
  });

  it('selects resilience as a region-scoped chat workflow', async () => {
    const onGeointAnalysis = vi.fn();
    const onModuleSelected = vi.fn();
    renderMap({ selectedDataset: null, onGeointAnalysis, onModuleSelected });
    await openModulePicker();

    fireEvent.click(screen.getByText('Resilience'));

    expect(onModuleSelected).toHaveBeenCalledWith('resilience');
    expect(onGeointAnalysis).not.toHaveBeenCalled();
  });

  it('blocks unavailable modules from clicks and selection events', async () => {
    const onModuleSelected = vi.fn();
    renderMap({
      selectedDataset: null,
      onModuleSelected,
      features: {
        mpcPublic: true,
        mpcPro: false,
        fabric: false,
        resilience: false,
        weather: false,
      },
    });
    await openModulePicker();

    const siteIntel = screen.getByRole('button', { name: /Site Intel/ });
    const resilience = screen.getByRole('button', { name: /Resilience/ });
    const forecast = screen.getByRole('button', { name: /Forecast/ });
    const buildingDamage = screen.getByRole('button', { name: /Building Damage/ });
    expect(siteIntel).toHaveAttribute('aria-disabled', 'true');
    expect(resilience).toHaveAttribute('aria-disabled', 'true');
    expect(forecast).toHaveAttribute('aria-disabled', 'true');
    expect(buildingDamage).toHaveAttribute('aria-disabled', 'true');
    expect(siteIntel).toBeDisabled();
    expect(resilience).toBeDisabled();
    expect(forecast).toBeDisabled();
    expect(buildingDamage).toBeDisabled();
    fireEvent.click(siteIntel);
    fireEvent.click(buildingDamage);
    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-select-module', {
      detail: { module: 'resilience' },
    })));

    expect(onModuleSelected).not.toHaveBeenCalled();
  });

  it('selects Building Damage when MPC Pro tenant imagery is enabled', async () => {
    const onGeointAnalysis = vi.fn();
    const onModuleSelected = vi.fn();
    renderMap({
      selectedDataset: null,
      onGeointAnalysis,
      onModuleSelected,
      features: {
        mpcPublic: true,
        mpcPro: true,
        fabric: false,
        resilience: false,
        weather: false,
      },
    });
    await openModulePicker();

    fireEvent.click(screen.getByRole('button', { name: /Building Damage/ }));

    expect(onModuleSelected).toHaveBeenCalledWith('building_damage');
    expect(onGeointAnalysis).toHaveBeenCalledWith({
      type: 'module_selected',
      message: '**Building Damage selected.**',
    });
    expect(screen.queryByText('Geointelligence Modules')).not.toBeInTheDocument();
  });

  it('selects an available gated module from the keyboard', async () => {
    const user = userEvent.setup();
    const onModuleSelected = vi.fn();
    renderMap({
      selectedDataset: null,
      onModuleSelected,
      features: {
        mpcPublic: true,
        mpcPro: true,
        fabric: false,
        resilience: false,
        weather: false,
      },
    });
    await openModulePicker();
    const buildingDamage = screen.getByRole('button', { name: /Building Damage/ });
    buildingDamage.focus();

    await user.keyboard('{Enter}');

    expect(onModuleSelected).toHaveBeenCalledWith('building_damage');
  });

  it('selects foundation change and arms a bounded AOI pin workflow', async () => {
    const onGeointAnalysis = vi.fn();
    const onModuleSelected = vi.fn();
    const onPinChange = vi.fn();
    renderMap({ selectedDataset: null, onGeointAnalysis, onModuleSelected, onPinChange });
    await openModulePicker();

    fireEvent.click(screen.getByText('Foundation Change'));

    expect(onModuleSelected).toHaveBeenCalledWith('foundation_change');
    expect(onGeointAnalysis).toHaveBeenCalledWith(expect.objectContaining({
      type: 'module_selected',
      message: expect.stringContaining('Click the map to set the analysis area'),
    }));

    const map = lastMockValue(atlasMock.Map);
    const clickHandler = await waitFor(() => {
      const handler = map.events.add.mock.calls
        .filter(([event]: [string]) => event === 'click')
        .at(-1)?.[1];
      expect(handler).toBeTypeOf('function');
      return handler;
    });
    act(() => clickHandler({ position: [-104.6189, 50.4452] }));

    await waitFor(() => {
      expect(onPinChange).toHaveBeenCalledWith({ lat: 50.4452, lng: -104.6189 });
    });
    await waitFor(() => {
      expect(onGeointAnalysis).toHaveBeenCalledWith(expect.objectContaining({
        type: 'info',
        message: expect.stringContaining('Analysis area set'),
      }));
    });
    expect(apiMocks.triggerGeointAnalysis).not.toHaveBeenCalled();
  });

  it('keeps the exact Thunder Bay HLS layer after a denied Foundation Change request', async () => {
    const onGeointAnalysis = vi.fn();
    const onModuleSelected = vi.fn();
    const onPinChange = vi.fn();
    const view = renderMap({
      selectedDataset: null,
      lastChatResponse: createHlsFireResponse(),
      onGeointAnalysis,
      onModuleSelected,
      onPinChange,
    });

    await waitFor(() => {
      expect(tileJsonMocks.fetchAndSignTileJSON).toHaveBeenCalledWith(
        expect.stringContaining('assets=B12&assets=B8A&assets=B04'),
        expect.anything(),
      );
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Map layers' }));
    expect(await screen.findByText('HLS fire false colour')).toBeInTheDocument();
    expect(screen.queryByText('PlanAura contextual change')).not.toBeInTheDocument();

    await openModulePicker();
    fireEvent.click(screen.getByText('Foundation Change'));
    const map = lastMockValue(atlasMock.Map);
    const clickHandler = await waitFor(() => {
      const handler = map.events.add.mock.calls
        .filter(([event]: [string]) => event === 'click')
        .at(-1)?.[1];
      expect(handler).toBeTypeOf('function');
      return handler;
    });
    act(() => clickHandler({ position: [-89.8572, 50.268] }));

    await waitFor(() => {
      expect(onPinChange).toHaveBeenCalledWith({ lat: 50.268, lng: -89.8572 });
      expect(onGeointAnalysis).toHaveBeenCalledWith(expect.objectContaining({
        type: 'info',
        message: expect.stringContaining('Analysis area set'),
      }));
    });
    view.rerender(
      <MapView
        selectedDataset={null}
        lastChatResponse={{
          response: 'GeoFM submission was not approved.',
          tools_used: ['compare_with_geofm'],
          structured: {
            compare_with_geofm: {
              success: false,
              structured: { status: 'denied' },
            },
          },
        }}
        onGeointAnalysis={onGeointAnalysis}
        onModuleSelected={onModuleSelected}
        onPinChange={onPinChange}
      />,
    );

    expect(await screen.findByText('HLS fire false colour')).toBeInTheDocument();
    expect(screen.queryByText('PlanAura contextual change')).not.toBeInTheDocument();
    expect(atlasMock.layer.PolygonLayer).not.toHaveBeenCalled();
    expect(atlasMock.layer.LineLayer).not.toHaveBeenCalled();
    expect(apiMocks.triggerGeointAnalysis).not.toHaveBeenCalled();
  });

  it('adds a dynamic PlanAura layer control for completed GeoFM polygons', async () => {
    const feature = {
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[[-89.86, 50.26], [-89.85, 50.26], [-89.86, 50.26]]],
      },
      properties: {},
    };
    const view = renderMap({
      selectedDataset: null,
      lastChatResponse: {
        tools_used: ['get_geofm_run'],
        map_data: { type: 'FeatureCollection', features: [feature] },
      },
    });
    await openModulePicker();
    fireEvent.click(screen.getByText('Foundation Change'));

    const layersButton = await screen.findByRole('button', { name: 'Map layers' });
    fireEvent.click(layersButton);
    expect(await screen.findByText('PlanAura contextual change')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('slider', { name: 'PlanAura contextual change opacity' }), {
      target: { value: '45' },
    });
    expect(geoFmPolygonSetOptions).toHaveBeenLastCalledWith({
      visible: true,
      fillOpacity: 0.225,
    });
    expect(geoFmLineSetOptions).toHaveBeenLastCalledWith({
      visible: true,
      strokeOpacity: 0.45,
    });

    fireEvent.click(screen.getByRole('button', { name: 'PlanAura contextual change visibility' }));
    expect(geoFmPolygonSetOptions).toHaveBeenLastCalledWith({ visible: false, fillOpacity: 0 });
    expect(geoFmLineSetOptions).toHaveBeenLastCalledWith({ visible: false, strokeOpacity: 0 });

    const map = lastMockValue(atlasMock.Map);
    const sourceAddsBeforeReload = map.sources.add.mock.calls.length;
    const layerAddsBeforeReload = map.layers.add.mock.calls.length;
    const styleDataHandler = map.events.add.mock.calls.find(
      ([event]: [string]) => event === 'styledata',
    )?.[1];
    expect(styleDataHandler).toBeTypeOf('function');

    act(() => styleDataHandler({ dataType: 'style' }));

    expect(map.sources.add).toHaveBeenCalledTimes(sourceAddsBeforeReload + 1);
    expect(map.layers.add).toHaveBeenCalledTimes(layerAddsBeforeReload + 1);
    expect(geoFmPolygonSetOptions).toHaveBeenLastCalledWith({ visible: false, fillOpacity: 0 });
    expect(geoFmLineSetOptions).toHaveBeenLastCalledWith({ visible: false, strokeOpacity: 0 });

    const sourceRemovalsBeforeFollowUp = map.sources.remove.mock.calls.length;
    const layerRemovalsBeforeFollowUp = map.layers.remove.mock.calls.length;
    view.rerender(
      <MapView
        selectedDataset={null}
        lastChatResponse={{ response: 'Follow-up response without GeoFM data' }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('PlanAura contextual change')).toBeInTheDocument();
    });
    expect(map.sources.remove).toHaveBeenCalledTimes(sourceRemovalsBeforeFollowUp);
    expect(map.layers.remove).toHaveBeenCalledTimes(layerRemovalsBeforeFollowUp);

    view.rerender(
      <MapView
        selectedDataset={null}
        lastChatResponse={createHlsFireResponse()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByText('PlanAura contextual change')).not.toBeInTheDocument();
      expect(map.sources.remove.mock.calls.length).toBeGreaterThan(sourceRemovalsBeforeFollowUp);
      expect(map.layers.remove.mock.calls.length).toBeGreaterThan(layerRemovalsBeforeFollowUp);
    });
  });

  it('uses configured opacity and keeps the HLS layer control after navigation', async () => {
    const view = renderMap({
      selectedDataset: null,
      lastChatResponse: createHlsFireResponse(),
    });

    await waitFor(() => expect(imageryLayerSetOptions).toHaveBeenCalled());
    expect(imageryLayerSetOptions).toHaveBeenLastCalledWith({ visible: true, opacity: 0.85 });
    view.rerender(
      <MapView selectedDataset={null} lastChatResponse={createHlsFireResponse()} />,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Map layers' })).toBeInTheDocument();
    });
    view.rerender(
      <MapView
        selectedDataset={null}
        lastChatResponse={{
          action: 'navigate_to',
          navigate_to: { latitude: 50.268, longitude: -89.857, zoom: 11 },
        }}
      />,
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Map layers' }));
    expect(await screen.findByText('HLS fire false colour')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('slider', { name: 'HLS fire false colour opacity' }), {
      target: { value: '60' },
    });
    expect(imageryLayerSetOptions).toHaveBeenLastCalledWith({ visible: true, opacity: 0.6 });

    fireEvent.click(screen.getByRole('button', { name: 'HLS fire false colour visibility' }));
    expect(imageryLayerSetOptions).toHaveBeenLastCalledWith({ visible: false, opacity: 0 });
  });

  it('does not expose an imagery layer when TileJSON rendering fails', async () => {
    tileJsonMocks.fetchAndSignTileJSON.mockResolvedValue({
      success: false,
      error: 'TileJSON unavailable',
    });

    renderMap({ selectedDataset: null, lastChatResponse: createHlsFireResponse() });

    await waitFor(() => expect(tileJsonMocks.fetchAndSignTileJSON).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Map layers' })).not.toBeInTheDocument();
  });

  it('removes rendered imagery when replacement STAC data has no tile URL', async () => {
    const view = renderMap({
      selectedDataset: null,
      lastChatResponse: createHlsFireResponse(),
    });
    await waitFor(() => expect(imageryLayerSetOptions).toHaveBeenCalled());
    const rasterLayer = lastMockValue(atlasMock.layer.TileLayer);
    const map = lastMockValue(atlasMock.Map);

    view.rerender(
      <MapView selectedDataset={null} lastChatResponse={createTilelessResponse()} />,
    );

    await waitFor(() => expect(map.layers.remove).toHaveBeenCalledWith(rasterLayer));
    expect(screen.queryByRole('button', { name: 'Map layers' })).not.toBeInTheDocument();
  });

  it('does not add a pending raster after tile-less STAC data replaces it', async () => {
    let resolveTileJson: (result: any) => void = () => undefined;
    tileJsonMocks.fetchAndSignTileJSON.mockImplementationOnce(
      () => new Promise((resolve) => { resolveTileJson = resolve; }),
    );
    const view = renderMap({
      selectedDataset: null,
      lastChatResponse: createHlsFireResponse(),
    });
    await waitFor(() => expect(tileJsonMocks.fetchAndSignTileJSON).toHaveBeenCalled());
    const map = lastMockValue(atlasMock.Map);

    view.rerender(
      <MapView selectedDataset={null} lastChatResponse={createTilelessResponse()} />,
    );
    await waitFor(() => {
      expect(map.setCamera).toHaveBeenCalledWith(expect.objectContaining({
        bounds: [-90, 50, -89, 51],
      }));
    });
    await act(async () => {
      resolveTileJson({
        success: true,
        tileTemplate: 'https://example.test/{z}/{x}/{y}.png',
        tilejson: { tilejson: '3.0.0', tiles: ['https://example.test/{z}/{x}/{y}.png'] },
        originalUrl: 'https://example.test/tilejson.json',
      });
    });

    expect(atlasMock.layer.TileLayer).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Map layers' })).not.toBeInTheDocument();
  });

  it('uses collection opacity with the Leaflet fallback', async () => {
    const leafletMap = {
      fitBounds: vi.fn(),
      getBounds: vi.fn().mockReturnValue({
        getNorth: () => 60,
        getSouth: () => 50,
        getEast: () => -80,
        getWest: () => -90,
      }),
      getCenter: vi.fn().mockReturnValue({ lat: 55, lng: -85 }),
      getZoom: vi.fn().mockReturnValue(8),
      hasLayer: vi.fn().mockReturnValue(true),
      off: vi.fn(),
      on: vi.fn(),
      removeLayer: vi.fn(),
      setView: vi.fn(),
    };
    const createLeafletLayer = () => ({
      addTo: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
      setOpacity: vi.fn(),
    });
    atlasMock.Map.mockImplementationOnce(function FailingAzureMap() {
      throw new Error('Azure Maps unavailable');
    });
    leafletMock.map.mockReturnValueOnce(leafletMap);
    leafletMock.tileLayer.mockImplementation(() => createLeafletLayer());

    renderMap({ selectedDataset: null, lastChatResponse: createHlsFireResponse() });

    await waitFor(() => {
      const imageryCall = leafletMock.tileLayer.mock.calls.find(
        ([url]) => url === 'https://example.test/{z}/{x}/{y}.png',
      );
      expect(imageryCall?.[1]).toEqual(expect.objectContaining({ opacity: 0.85 }));
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Map layers' }));
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('preserves STAC assets and catalog provenance for follow-up inspection', async () => {
    const onMapContextChange = vi.fn();
    const response = createHlsFireResponse();
    response.data.stac_results.features[0]._planetary_explorer_stac_mode = 'public';
    response.data.stac_results.features[0].assets = {
      B04: {
        href: 'https://example.test/B04.tif',
        type: 'image/tiff',
        'raster:bands': [{ scale: 0.0000275, offset: -0.2 }],
      },
      B8A: { href: 'https://example.test/B8A.tif', type: 'image/tiff' },
      B12: { href: 'https://example.test/B12.tif', type: 'image/tiff' },
    };

    renderMap({
      selectedDataset: null,
      lastChatResponse: response,
      onMapContextChange,
      stacMode: 'public',
    });

    await waitFor(() => {
      const context = onMapContextChange.mock.calls
        .map(([value]) => value)
        .find((value) => value?.stac_items?.length);
      expect(context?.stac_items[0]).toEqual(expect.objectContaining({
        id: 'HLS.S30.T15UYR.2026185T165839.v2.0',
        collection: 'hls2-s30',
        stac_mode: 'public',
        assets: expect.objectContaining({
          B04: expect.objectContaining({
            href: 'https://example.test/B04.tif',
            'raster:bands': [{ scale: 0.0000275, offset: -0.2 }],
          }),
          B8A: expect.objectContaining({ href: 'https://example.test/B8A.tif' }),
          B12: expect.objectContaining({ href: 'https://example.test/B12.tif' }),
        }),
      }));
    });
  });

  it('restores layer labels from the saved imagery render profile', async () => {
    const view = renderMap({
      selectedDataset: null,
      historyRestore: {
        token: 1,
        context: {
          selectedModule: 'foundation_change',
          map: {
            bounds: {
              north: 50.278,
              south: 50.258,
              east: -89.8472,
              west: -89.8672,
              center_lat: 50.268,
              center_lng: -89.8572,
            },
            current_collection: 'hls2-s30',
            render_profile_id: 'hls-s30-fire-false-colour',
            imagery_url: 'https://example.test/fire/tilejson.json',
            item_id: 'fire-item',
            datetime: '2026-07-04T17:09:44Z',
          },
        },
      },
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Map layers' }));
    expect(await screen.findByText('HLS fire false colour')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Map layers' }));

    view.rerender(
      <MapView
        selectedDataset={null}
        historyRestore={{
          token: 2,
          context: {
            map: {
              bounds: {
                north: 48,
                south: 47,
                east: -121,
                west: -123,
                center_lat: 47.5,
                center_lng: -122,
              },
              current_collection: 'sentinel-2-l2a',
              imagery_url: 'https://example.test/standard/tilejson.json',
              item_id: 'standard-item',
              datetime: '2026-08-26T00:00:00Z',
            },
          },
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Map layers' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Map layers' }));
    expect(await screen.findByText('Sentinel-2 Level-2A')).toBeInTheDocument();
    expect(screen.queryByText('HLS fire false colour')).not.toBeInTheDocument();
  });

  it('exposes the current satellite-label control', async () => {
    renderMap();

    expect(await screen.findByTitle('Hide map labels (switch to plain satellite)')).toBeInTheDocument();
  });
});