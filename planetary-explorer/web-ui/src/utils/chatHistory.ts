import { ChatHistoryContext, ChatHistorySession, ChatHistorySnapshot, ChatMessage, MapContext } from '../services/api';

export const MAX_HISTORY_TILE_URLS = 50;
export const MAX_HISTORY_SCENE_REFS = 50;

export function persistedChatMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.filter((message) => !message.isThinking);
}

export function chatHistoryFingerprint(
  snapshot: Omit<ChatHistorySnapshot, 'expectedRevision' | 'mutationId'>,
): string {
  const canonicalize = (value: unknown): unknown => {
    if (value instanceof Date) return value.toISOString();
    if (Array.isArray(value)) return value.map(canonicalize);
    if (value && typeof value === 'object') {
      return Object.keys(value as Record<string, unknown>)
        .sort()
        .reduce<Record<string, unknown>>((result, key) => {
          const child = (value as Record<string, unknown>)[key];
          if (child !== undefined) result[key] = canonicalize(child);
          return result;
        }, {});
    }
    return value;
  };
  return JSON.stringify(canonicalize(snapshot));
}

export function createChatHistoryMutationId(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `mutation-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

export function hasFailedHistorySave(
  state: 'idle' | 'saving' | 'saved' | 'error',
  hasQueuedSnapshot: boolean,
): boolean {
  return state === 'error' && hasQueuedSnapshot;
}

export function isHistorySaveAtRisk(
  state: 'idle' | 'saving' | 'saved' | 'error',
  hasQueuedSnapshot: boolean,
): boolean {
  return state === 'saving' || hasFailedHistorySave(state, hasQueuedSnapshot);
}

export function confirmFailedHistoryDiscard(
  hasFailedSave: boolean,
  confirmDiscard: (message: string) => boolean = window.confirm,
): boolean {
  return !hasFailedSave || confirmDiscard('This chat was not saved. Discard it?');
}

export function restoredStacMode(
  mode: 'public' | 'pro' | undefined,
  proEnabled: boolean,
): 'public' | 'pro' | undefined {
  return mode === 'pro' && !proEnabled ? 'public' : mode;
}

export function normalizeRestoredChatContext(
  context: ChatHistoryContext,
  proEnabled: boolean,
): ChatHistoryContext {
  const hasProState = context.stacMode === 'pro'
    || context.map?.stac_mode === 'pro'
    || context.map?.tile_urls?.some((tile) => tile.stac_mode === 'pro')
    || context.map?.scene_refs?.some((scene) => scene.stac_mode === 'pro');
  if (!hasProState || proEnabled) return context;
  return {
    ...context,
    stacMode: 'public',
    selectedDataset: undefined,
    pin: undefined,
    map: undefined,
  };
}

export function historyUnmountAction(
  hasTerminalFailure: boolean,
  hasQueuedSnapshot: boolean,
): 'discard' | 'flush' | 'none' {
  if (hasTerminalFailure) return 'discard';
  return hasQueuedSnapshot ? 'flush' : 'none';
}

export function restoreChatMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => ({
    ...message,
    timestamp: new Date(message.timestamp),
    isThinking: false,
  }));
}

export function reconcileAmbiguousHistorySave(
  server: Pick<ChatHistorySession, 'revision' | 'appliedMutationId'>,
  mutationId: string,
  attemptedRevision: number,
): 'committed' | 'unchanged' | 'conflict' {
  if (server.appliedMutationId === mutationId) return 'committed';
  if (server.revision === attemptedRevision) return 'unchanged';
  return 'conflict';
}

export function boundedHistoryTileUrls(
  tileUrls: MapContext['tile_urls'],
): MapContext['tile_urls'] {
  return tileUrls?.slice(0, MAX_HISTORY_TILE_URLS);
}

export function boundedHistorySceneRefs(
  stacItems: MapContext['stac_items'],
): MapContext['scene_refs'] {
  return stacItems?.slice(0, MAX_HISTORY_SCENE_REFS).map((item) => ({
    id: item.id,
    collection: item.collection,
    stac_mode: item.stac_mode,
    bbox: item.bbox,
    datetime: typeof item.properties?.datetime === 'string'
      ? item.properties.datetime
      : undefined,
  }));
}