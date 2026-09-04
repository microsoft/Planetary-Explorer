import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Chat from '../Chat';
import { apiService } from '../../services/api';

vi.mock('../../services/api', () => ({
  apiService: {
    getChatSession: vi.fn(),
    sendChatMessage: vi.fn(),
    saveChatSession: vi.fn(),
  },
}));

const mockedSendChatMessage = vi.mocked(apiService.sendChatMessage);
const mockedSaveChatSession = vi.mocked(apiService.saveChatSession);
const mockedGetChatSession = vi.mocked(apiService.getChatSession);

describe('Chat sequential parts cancellation', () => {
  beforeEach(() => {
    mockedSendChatMessage.mockReset();
    mockedSaveChatSession.mockReset();
    mockedGetChatSession.mockReset();
    mockedSaveChatSession.mockResolvedValue({ revision: 1 } as any);
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('keeps Stop visible and aborts before dispatching later parts', async () => {
    // Arrange
    let partSignal: AbortSignal | undefined;
    mockedSendChatMessage
      .mockResolvedValueOnce({
        action: 'sequential_parts',
        response: 'I will answer this in two parts.',
        session_id: 'session-1',
        parts: [
          { id: 1, query: 'First part', depends_on: [] },
          { id: 2, query: 'Second part', depends_on: [1] },
        ],
      })
      .mockImplementationOnce((...args: any[]) => {
        partSignal = args[12] as AbortSignal;
        return new Promise((_resolve, reject) => {
          partSignal?.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'));
          });
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
        <Chat selectedDataset={null} chatMode geointMode={false} />
      </QueryClientProvider>
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Answer two questions' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('I will answer this in two parts.');
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('Working on part 1 of 2…')).toHaveLength(1);
    const stopButton = await screen.findByRole('button', { name: 'Stop generating' });

    // Act
    fireEvent.click(stopButton);

    // Assert
    await waitFor(() => expect(partSignal?.aborted).toBe(true));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument());
    expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
  });

  it('adopts settled restoration context without issuing another history save', async () => {
    // Arrange
    mockedSendChatMessage.mockResolvedValue({
      response: 'Initial answer',
      session_id: 'session-1',
    });
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode={false}
          chatHistoryEnabled
          historyRestorePending={false}
          mapContext={{
            current_collection: 'hls2-s30',
            render_profile_id: 'hls-s30-fire-false-colour',
            imagery_url: 'https://tiles.example/fire/tilejson.json',
          }}
        />
      </QueryClientProvider>
    );
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Create a saved turn' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Initial answer');
    await waitFor(() => expect(mockedSaveChatSession).toHaveBeenCalledTimes(1));
    expect(mockedSaveChatSession.mock.calls[0][1].context.map).toMatchObject({
      current_collection: 'hls2-s30',
      render_profile_id: 'hls-s30-fire-false-colour',
    });
    mockedSaveChatSession.mockClear();

    // Act
    rerender(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode={false}
          chatHistoryEnabled
          historyRestorePending
          stacMode="pro"
          mapContext={{
            stac_mode: 'pro',
            current_collection: 'private-dem',
            imagery_url: 'https://private.example/item.tif',
          }}
        />
      </QueryClientProvider>
    );
    rerender(
      <QueryClientProvider client={queryClient}>
        <Chat
          selectedDataset={null}
          chatMode
          geointMode={false}
          chatHistoryEnabled
          historyRestorePending={false}
          stacMode="public"
          mapContext={{ stac_mode: 'public', has_satellite_data: false }}
        />
      </QueryClientProvider>
    );

    // Assert
    await waitFor(() => expect(screen.getByText('Saved')).toBeInTheDocument());
    expect(mockedSaveChatSession).not.toHaveBeenCalled();
  });

  it('ignores stale history reconciliation after a Get Started Setup', async () => {
    let resolveReconciliation: ((value: any) => void) | undefined;
    let resolveSetup: ((value: any) => void) | undefined;
    mockedSendChatMessage
      .mockResolvedValueOnce({ response: 'Old answer', session_id: 'old-session' })
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveSetup = resolve;
      }));
    mockedSaveChatSession
      .mockRejectedValueOnce({ response: { status: 409 } })
      .mockResolvedValueOnce({ revision: 1 } as any);
    mockedGetChatSession.mockImplementationOnce(() => new Promise((resolve) => {
      resolveReconciliation = resolve;
    }));
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <Chat selectedDataset={null} chatMode geointMode={false} chatHistoryEnabled />
      </QueryClientProvider>
    );

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Describe the old location' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Old answer');
    await waitFor(() => expect(mockedGetChatSession).toHaveBeenCalledTimes(1));

    act(() => window.dispatchEvent(new CustomEvent('planetaryexplorer-stac-query', {
      detail: {
        query: 'Show imagery over Toronto',
        clearSessions: true,
        resetContext: true,
      },
    })));
    await waitFor(() => expect(mockedSendChatMessage).toHaveBeenCalledTimes(2));
    const firstMutationId = mockedSaveChatSession.mock.calls[0][1].mutationId;
    await act(async () => {
      resolveReconciliation?.({
        sessionId: 'old-session',
        revision: 7,
        appliedMutationId: firstMutationId,
        messages: [],
        context: {},
      });
    });
    await act(async () => {
      resolveSetup?.({ response: 'Toronto loaded' });
    });

    await waitFor(() => expect(mockedSaveChatSession).toHaveBeenCalledTimes(2));
    expect(mockedSaveChatSession.mock.calls[1][1].expectedRevision).toBe(0);
  });
});
