import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiService } from '../api';

describe('ApiService model selection', () => {
  const post = vi.fn();

  beforeEach(() => {
    post.mockReset();
    post.mockResolvedValue({ status: 200, data: { response: 'ok' } });
    (apiService as any).api = { post };
  });

  it('serializes the selected model, thinking level, and GEOINT module', async () => {
    // Act
    await apiService.sendChatMessage(
      'Compare the loaded HLS epochs',
      undefined,
      'session-1',
      [],
      undefined,
      true,
      undefined,
      'gpt-5.6-terra',
      'high',
      'foundation_change',
      false,
      'public',
    );

    // Assert
    expect(post).toHaveBeenCalledWith(
      '/api/query',
      expect.objectContaining({
        query: 'Compare the loaded HLS epochs',
        model: 'gpt-5.6-terra',
        reasoning_effort: 'high',
        geoint_module: 'foundation_change',
      }),
      { signal: undefined },
    );
  });

  it('omits model controls until deployment discovery validates a model', async () => {
    // Act
    await apiService.sendChatMessage(
      'Open the saved query',
      undefined,
      'session-1',
      [],
      undefined,
      false,
      undefined,
      undefined,
      'high',
    );

    // Assert
    const request = post.mock.calls[0][1];
    expect(request).not.toHaveProperty('model');
    expect(request).not.toHaveProperty('reasoning_effort');
  });

  it('serializes an explicit Get Started screenshot analysis hint', async () => {
    await apiService.sendChatMessage(
      'Describe the visible vegetation colours',
      undefined,
      'session-vision',
      [],
      undefined,
      true,
      {
        analysis_type: 'screenshot',
        imagery_base64: 'image-data',
        current_collection: 'modis-13Q1-061',
      },
    );

    expect(post).toHaveBeenCalledWith(
      '/api/query',
      expect.objectContaining({
        analysis_type: 'screenshot',
        imagery_base64: 'image-data',
      }),
      { signal: undefined },
    );
  });
});