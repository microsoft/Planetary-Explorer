import { describe, expect, it, vi } from 'vitest';

import { ChatHistorySnapshot } from '../../services/api';
import {
  boundedHistorySceneRefs,
  boundedHistoryTileUrls,
  chatHistoryFingerprint,
  confirmFailedHistoryDiscard,
  createChatHistoryMutationId,
  hasFailedHistorySave,
  historyUnmountAction,
  isHistorySaveAtRisk,
  normalizeRestoredChatContext,
  reconcileAmbiguousHistorySave,
  restoreChatMessages,
  restoredStacMode,
} from '../chatHistory';

describe('chat history snapshots', () => {
  it('changes the autosave fingerprint when only context changes', () => {
    // Arrange
    const base: Omit<ChatHistorySnapshot, 'expectedRevision' | 'mutationId'> = {
      messages: [{ role: 'user', content: 'Show Toronto in 2026', timestamp: new Date(0) }],
      context: { selectedModel: 'gpt-5', stacMode: 'public' },
    };
    const changed: Omit<ChatHistorySnapshot, 'expectedRevision' | 'mutationId'> = {
      ...base,
      context: { ...base.context, stacMode: 'pro' },
    };

    // Act & Assert
    expect(chatHistoryFingerprint(base)).not.toBe(chatHistoryFingerprint(changed));
  });

  it('produces the same fingerprint regardless of object key order', () => {
    const first = {
      messages: [{ role: 'user' as const, content: 'Test', timestamp: new Date(0) }],
      context: {
        selectedModel: 'gpt-5',
        map: { current_collection: 'cop-dem', item_id: 'item-1' },
      },
    };
    const second = {
      context: {
        map: { item_id: 'item-1', current_collection: 'cop-dem' },
        selectedModel: 'gpt-5',
      },
      messages: [{ timestamp: new Date(0), content: 'Test', role: 'user' as const }],
    };

    expect(chatHistoryFingerprint(first)).toBe(chatHistoryFingerprint(second));
  });

  it('retains all 50 zoom-expansion tiles in persisted history', () => {
    const tiles = Array.from({ length: 60 }, (_, index) => ({
      tilejson_url: `https://tiles.example/item-${index}.json`,
      item_id: `item-${index}`,
      stac_mode: index === 49 ? 'pro' as const : 'public' as const,
    }));

    expect(boundedHistoryTileUrls(tiles)).toHaveLength(50);
    expect(boundedHistoryTileUrls(tiles)?.[49].item_id).toBe('item-49');
    expect(boundedHistoryTileUrls(tiles)?.[49].stac_mode).toBe('pro');
  });

  it('stores bounded scene provenance without STAC assets', () => {
    const scenes = Array.from({ length: 60 }, (_, index) => ({
      id: `item-${index}`,
      collection: 'sentinel-2-l2a',
      stac_mode: index === 49 ? 'pro' as const : 'public' as const,
      bbox: [index, 0, index + 1, 1],
      properties: { datetime: `2026-06-${String((index % 28) + 1).padStart(2, '0')}T00:00:00Z` },
      assets: { visual: { href: 'https://storage.example/signed.tif?sig=secret' } },
    }));

    const refs = boundedHistorySceneRefs(scenes);

    expect(refs).toHaveLength(50);
    expect(refs?.[49]).toMatchObject({
      id: 'item-49',
      stac_mode: 'pro',
    });
    expect(refs?.[0]).not.toHaveProperty('assets');
  });

  it('creates URL-safe mutation identifiers for idempotent saves', () => {
    expect(createChatHistoryMutationId()).toMatch(/^[A-Za-z0-9._:-]+$/);
  });

  it('reconciles ambiguous committed saves before advancing queued snapshots', () => {
    expect(reconcileAmbiguousHistorySave(
      { revision: 2, appliedMutationId: 'save-a' },
      'save-a',
      1,
    )).toBe('committed');
    expect(reconcileAmbiguousHistorySave(
      { revision: 1, appliedMutationId: 'older-save' },
      'save-a',
      1,
    )).toBe('unchanged');
    expect(reconcileAmbiguousHistorySave(
      { revision: 2, appliedMutationId: 'other-writer' },
      'save-a',
      1,
    )).toBe('conflict');
  });

  it('requires confirmation before discarding a queued failed save', () => {
    // Arrange
    const confirmDiscard = vi.fn(() => false);

    // Act and assert
    expect(hasFailedHistorySave('error', true)).toBe(true);
    expect(confirmFailedHistoryDiscard(true, confirmDiscard)).toBe(false);
    expect(confirmDiscard).toHaveBeenCalledWith('This chat was not saved. Discard it?');
  });

  it('clamps restored Pro mode when the deployment disables it', () => {
    expect(restoredStacMode('pro', false)).toBe('public');
    expect(restoredStacMode('pro', true)).toBe('pro');
    expect(restoredStacMode('public', false)).toBe('public');
  });

  it('removes private dataset and map references before restoring disabled Pro history', () => {
    const context = normalizeRestoredChatContext({
      stacMode: 'pro',
      selectedDataset: { id: 'private-dem', title: 'Private DEM' },
      pin: { lat: 47.5, lng: -122.0 },
      map: {
        stac_mode: 'pro',
        imagery_url: 'https://private.blob.core.windows.net/data/private.tif?<redacted>',
        current_collection: 'private-dem',
      },
    }, false);

    expect(context).toEqual({
      stacMode: 'public',
      selectedDataset: undefined,
      pin: undefined,
      map: undefined,
    });
  });

  it('removes nested Pro item references before restoring disabled Pro history', () => {
    const context = normalizeRestoredChatContext({
      stacMode: 'public',
      map: {
        stac_mode: 'public',
        tile_urls: [
          {
            tilejson_url: '/api/pro/tilejson?collection=private-dem&item=item-1',
            item_id: 'item-1',
            stac_mode: 'pro',
          },
        ],
      },
    }, false);

    expect(context).toEqual({
      stacMode: 'public',
      selectedDataset: undefined,
      pin: undefined,
      map: undefined,
    });
  });

  it('removes Pro mosaic scene references before restoring disabled Pro history', () => {
    const context = normalizeRestoredChatContext({
      stacMode: 'public',
      map: {
        stac_mode: 'public',
        imagery_url: 'https://tiles.example/mosaic/{z}/{x}/{y}.png',
        scene_refs: [
          {
            id: 'private-scene',
            collection: 'private-imagery',
            stac_mode: 'pro',
          },
        ],
      },
    }, false);

    expect(context.map).toBeUndefined();
  });

  it('discards terminal failures instead of flushing them during unmount', () => {
    expect(historyUnmountAction(true, true)).toBe('discard');
    expect(historyUnmountAction(false, true)).toBe('flush');
    expect(historyUnmountAction(false, false)).toBe('none');
  });

  it('treats in-flight and terminal failed saves as navigation risk', () => {
    expect(isHistorySaveAtRisk('saving', false)).toBe(true);
    expect(isHistorySaveAtRisk('error', true)).toBe(true);
    expect(isHistorySaveAtRisk('saved', false)).toBe(false);
  });

  it('restores message timestamps as Date values and clears thinking state', () => {
    // Act
    const restored = restoreChatMessages([
      {
        role: 'assistant',
        content: 'Saved answer',
        timestamp: '2026-08-26T12:00:00Z' as unknown as Date,
        isThinking: true,
      },
    ]);

    // Assert
    expect(restored[0].timestamp).toBeInstanceOf(Date);
    expect(restored[0].isThinking).toBe(false);
  });
});