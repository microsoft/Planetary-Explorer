import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Chat from '../Chat';
import { apiService } from '../../services/api';

vi.mock('../../services/api', () => ({
  apiService: {
    resolveMcpConfirmation: vi.fn(),
    saveChatSession: vi.fn(),
    sendChatMessage: vi.fn(),
    triggerForecast: vi.fn(),
  },
  sendTerrainChatMessage: vi.fn(),
}));

const mockedResolveConfirmation = vi.mocked(apiService.resolveMcpConfirmation);
const mockedSendChatMessage = vi.mocked(apiService.sendChatMessage);
const mockedTriggerForecast = vi.mocked(apiService.triggerForecast);

const getMockedTerrainChat = async () => {
  const module = await import('../../services/api');
  return vi.mocked(module.sendTerrainChatMessage);
};

describe('Chat Foundation Change confirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLElement.prototype.scrollIntoView = vi.fn();
    mockedResolveConfirmation.mockResolvedValue(true);
  });

  it('denies PlanAura without replacing the loaded HLS fire legend', async () => {
    let resolveResponse: ((value: any) => void) | undefined;
    mockedSendChatMessage.mockImplementation((...args: any[]) => {
      const streamHandlers = args[13];
      streamHandlers.onConfirmRequest({
        type: 'confirm_request',
        trace_id: 'trace-thunder-bay',
        server_id: 'geofm',
        tool: 'geofm_compare_epochs',
        tier: 'write',
        args: {
          request: {
            item_id_epoch_a: 'HLS.S30.T15UYR.2026152T165841.v2.0',
            item_id_epoch_b: 'HLS.S30.T15UYR.2026185T165839.v2.0',
            threshold: 0.05,
            max_features: 10,
          },
        },
      });
      return new Promise((resolve) => {
        resolveResponse = resolve;
      });
    });
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode
          selectedModule="foundation_change"
          currentPin={{ lat: 50.268, lng: -89.8572 }}
          stacMode="public"
          mapContext={{
            stac_mode: 'public',
            current_collection: 'hls2-s30',
            render_profile_id: 'hls-s30-fire-false-colour',
            has_satellite_data: true,
            tile_urls: [{
              item_id: 'HLS.S30.T15UYR.2026185T165839.v2.0',
              collection: 'hls2-s30',
              tilejson_url: 'https://example.test/item?assets=B12&assets=B8A&assets=B04',
            }],
          }}
        />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: {
        value: (
          'Use PlanAura to compare HLS S30 on 2026-06-01 and 2026-07-04 '
          + 'at the pinned Thunder Bay 36 fire area.'
        ),
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    const confirmation = await screen.findByRole('alertdialog');
    expect(confirmation).toHaveTextContent('geofm_compare_epochs');
    expect(confirmation).toHaveTextContent('geofm');

    fireEvent.click(screen.getByRole('button', { name: 'Deny' }));
    await waitFor(() => {
      expect(mockedResolveConfirmation).toHaveBeenCalledWith(
        'trace-thunder-bay',
        false,
      );
    });
    await act(async () => {
      resolveResponse?.({
        response: 'GeoFM submission was not approved.',
        data_source: 'Public PC',
        tools_used: ['compare_with_geofm'],
        structured: {
          compare_with_geofm: {
            success: false,
            structured: { status: 'denied' },
          },
        },
      });
    });

    expect(await screen.findByText('GeoFM submission was not approved.')).toBeInTheDocument();
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByText('HLS fire false colour')).toBeInTheDocument();
    expect(screen.queryByText('PlanAura contextual change')).not.toBeInTheDocument();
  });

  it('forwards the Get Started Image Analysis hint with the map screenshot', async () => {
    mockedSendChatMessage.mockResolvedValue({
      response: 'Vegetation colours described.',
      tools_used: ['describe_map_screenshot'],
    });
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode
          selectedModule="vision"
          stacMode="public"
          mapContext={{
            stac_mode: 'public',
            current_collection: 'modis-13Q1-061',
            has_satellite_data: true,
            imagery_base64: 'image-data',
            tile_urls: [{
              item_id: 'scene-1',
              collection: 'modis-13Q1-061',
              tilejson_url: 'https://example.test/tilejson.json',
            }],
          }}
        />
      </QueryClientProvider>,
    );

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-query', {
      detail: {
        query: 'Explain the vegetation colours.',
        analysisType: 'screenshot',
        requiresStacData: true,
      },
    })));

    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalled());
    expect(mockedSendChatMessage.mock.calls[0][6]).toMatchObject({
      analysis_type: 'screenshot',
      imagery_base64: 'image-data',
      current_collection: 'modis-13Q1-061',
    });
  });

  it('runs a Get Started Setup without stale module, pin, map, or history context', async () => {
    mockedSendChatMessage.mockResolvedValue({ response: 'Loaded Toronto.' });
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode
          selectedModule="resilience"
          currentPin={{ lat: -33.8688, lng: 151.2093 }}
          stacMode="public"
          mapContext={{
            stac_mode: 'public',
            current_collection: 'sentinel-1-rtc',
            has_satellite_data: true,
            vision_pin: { lat: -33.8688, lng: 151.2093 },
            bounds: {
              west: 150.9,
              south: -34.1,
              east: 151.4,
              north: -33.6,
              center_lat: -33.85,
              center_lng: 151.15,
            },
          }}
        />
      </QueryClientProvider>,
    );
    const query = 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26';

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query,
        clearSessions: true,
        resetContext: true,
        stacMode: 'pro',
      },
    })));

    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalled());
    const call = mockedSendChatMessage.mock.calls[0];
    expect(call[0]).toBe(query);
    expect(call[2]).toMatch(/^web-session-/);
    expect(call[3]).toEqual([]);
    expect(call[4]).toBeUndefined();
    expect(call[5]).toBe(false);
    expect(call[6]).toBeUndefined();
    expect(call[9]).toBeUndefined();
    expect(call[11]).toBe('pro');
  });

  it('keeps prior bubbles out of follow-up history after Setup', async () => {
    mockedSendChatMessage
      .mockResolvedValueOnce({ response: 'Old-location answer.' })
      .mockResolvedValueOnce({ response: 'Loaded Toronto.' })
      .mockResolvedValueOnce({ response: 'Toronto follow-up.' });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat selectedDataset={null} chatMode geointMode={false} stacMode="public" />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Describe Sydney.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('Old-location answer.')).toBeInTheDocument();

    const setupQuery = 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26';
    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: { query: setupQuery, clearSessions: true, resetContext: true },
    })));
    expect(await screen.findByText('Loaded Toronto.')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'What is visible in Toronto?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(3));

    const followUpHistory = mockedSendChatMessage.mock.calls[2][3] ?? [];
    expect(followUpHistory.map((message: { content: string }) => message.content)).toEqual([
      setupQuery,
      'Loaded Toronto.',
      'What is visible in Toronto?',
    ]);
    expect(followUpHistory).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ content: 'Describe Sydney.' }),
      expect.objectContaining({ content: 'Old-location answer.' }),
    ]));
  });

  it('aborts stale Terrain work and suppresses its late session update on Setup', async () => {
    const mockedTerrainChat = await getMockedTerrainChat();
    let resolveTerrain: ((value: any) => void) | undefined;
    mockedTerrainChat.mockImplementation((...args: any[]) => new Promise((resolve) => {
      resolveTerrain = resolve;
      expect(args[6]).toBeInstanceOf(AbortSignal);
    }));
    mockedSendChatMessage.mockResolvedValue({ response: 'Loaded Toronto.' });
    const onTerrainSessionChange = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode={false}
          selectedModule="terrain"
          terrainSession={{ sessionId: null, lat: 51.05, lng: -114.07 }}
          onTerrainSessionChange={onTerrainSessionChange}
          stacMode="public"
        />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Assess this terrain.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(mockedTerrainChat).toHaveBeenCalledTimes(1));
    const terrainSignal = mockedTerrainChat.mock.calls[0][6] as AbortSignal;

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query: 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26',
        clearSessions: true,
        resetContext: true,
      },
    })));
    expect(terrainSignal.aborted).toBe(true);

    await act(async () => {
      resolveTerrain?.({
        response: 'Late terrain answer.',
        session_id: 'stale-terrain-session',
        tool_calls: [],
      });
    });
    expect(onTerrainSessionChange).not.toHaveBeenCalled();
    expect(screen.queryByText('Late terrain answer.')).not.toBeInTheDocument();
  });

  it('ignores a prior response that completes after a new Setup', async () => {
    let resolvePrior: ((value: any) => void) | undefined;
    mockedSendChatMessage
      .mockImplementationOnce(() => new Promise((resolve) => { resolvePrior = resolve; }))
      .mockResolvedValueOnce({ response: 'Loaded Toronto.' })
      .mockResolvedValueOnce({ response: 'Toronto follow-up.' });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat selectedDataset={null} chatMode geointMode={false} stacMode="public" />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Describe the old location.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(1));

    const query = 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26';
    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: { query, clearSessions: true, resetContext: true },
    })));
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Loaded Toronto.')).toBeInTheDocument();

    await act(async () => {
      resolvePrior?.({ response: 'Late answer from the old location.' });
    });
    expect(screen.queryByText('Late answer from the old location.')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'What is visible in Toronto?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(3));

    const followUpHistory = mockedSendChatMessage.mock.calls[2][3] ?? [];
    expect(followUpHistory.map((message: { content: string }) => message.content)).toEqual([
      query,
      'Loaded Toronto.',
      'What is visible in Toronto?',
    ]);
  });

  it('denies pending confirmations when a new Setup supersedes the turn', async () => {
    let staleStreamHandlers: any;
    mockedSendChatMessage
      .mockImplementationOnce((...args: any[]) => {
        staleStreamHandlers = args[13];
        staleStreamHandlers.onConfirmRequest({
          type: 'confirm_request',
          trace_id: 'trace-stale-write',
          server_id: 'geofm',
          tool: 'geofm_compare_epochs',
          tier: 'write',
          args: {},
        });
        return new Promise(() => undefined);
      })
      .mockResolvedValueOnce({ response: 'Loaded Toronto.' });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat selectedDataset={null} chatMode geointMode selectedModule="foundation_change" />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Start a change comparison.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument();

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query: 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26',
        clearSessions: true,
        resetContext: true,
      },
    })));

    await waitFor(() => expect(mockedResolveConfirmation).toHaveBeenCalledWith(
      'trace-stale-write',
      false,
      'Superseded by a new Get Started Setup.',
    ));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();

    act(() => staleStreamHandlers.onConfirmRequest({
      type: 'confirm_request',
      trace_id: 'trace-late-write',
      server_id: 'geofm',
      tool: 'geofm_compare_epochs',
      tier: 'write',
      args: {},
    }));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('waits for a newly captured screenshot before Image Analysis', async () => {
    mockedSendChatMessage.mockResolvedValue({
      response: 'Toronto imagery described.',
      tools_used: ['describe_map_screenshot'],
    });
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    const initialContext = {
      stac_mode: 'public' as const,
      current_collection: 'sentinel-2-l2a',
      has_satellite_data: true,
      vision_pin: { lat: 43.72, lng: -79.38 },
      tile_urls: [{
        item_id: 'scene-1',
        collection: 'sentinel-2-l2a',
        tilejson_url: 'https://example.test/tilejson.json',
      }],
    };
    const view = render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode
          selectedModule="vision"
          stacMode="public"
          mapContext={initialContext}
        />
      </QueryClientProvider>,
    );

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-query', {
      detail: {
        query: 'Explain the colours in Toronto.',
        analysisType: 'screenshot',
        requiresStacData: true,
      },
    })));
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode
          selectedModule="vision"
          stacMode="public"
          mapContext={{ ...initialContext, imagery_base64: 'new-image-data' }}
        />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalled());
    expect(mockedSendChatMessage.mock.calls[0][6]).toMatchObject({
      analysis_type: 'screenshot',
      imagery_base64: 'new-image-data',
    });
  });

  it('renders forecast statistics with their units', async () => {
    mockedTriggerForecast.mockResolvedValue({
      result: {
        providers_called: ['aurora-1.x', 'earth2-fcn'],
        providers_succeeded: ['aurora-1.x', 'earth2-fcn'],
        providers_failed: [],
        forecasts: [],
        ensemble_summary: {
          variables: {
            t2m: {
              mean: 292.053,
              spread: 2.113,
              stdev: 1.494,
              samples: 2,
              unit: 'K',
            },
          },
        },
      },
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode={false}
          selectedModule="forecast"
          currentPin={{ lat: 43.75, lng: -77.9 }}
          stacMode="public"
        />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Give me a five-day ensemble forecast.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText(/mean 292\.05 K.*spread 2\.11 K.*σ 1\.49 K/)).toBeInTheDocument();
  });
});