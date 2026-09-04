import { describe, expect, it, vi } from 'vitest';

import { applyRasterLayerDisplay, clampLayerOpacity } from '../mapLayerDisplay';

describe('map layer display', () => {
  it('updates each unique Azure Maps layer', () => {
    const layer = { setOptions: vi.fn() };
    const secondLayer = { setOptions: vi.fn() };

    applyRasterLayerDisplay([layer, layer, secondLayer], 'azure', true, 0.62);

    expect(layer.setOptions).toHaveBeenCalledOnce();
    expect(layer.setOptions).toHaveBeenCalledWith({ visible: true, opacity: 0.62 });
    expect(secondLayer.setOptions).toHaveBeenCalledWith({ visible: true, opacity: 0.62 });
  });

  it('uses zero effective opacity when a Leaflet layer is hidden', () => {
    const layer = { setOpacity: vi.fn() };

    applyRasterLayerDisplay([layer], 'leaflet', false, 0.8);

    expect(layer.setOpacity).toHaveBeenCalledWith(0);
  });

  it('clamps invalid opacity values', () => {
    expect(clampLayerOpacity(-0.5)).toBe(0);
    expect(clampLayerOpacity(1.5)).toBe(1);
    expect(clampLayerOpacity(Number.NaN)).toBe(1);
  });
});