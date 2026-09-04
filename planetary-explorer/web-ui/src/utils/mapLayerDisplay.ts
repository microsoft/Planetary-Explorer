export type MapLayerProvider = 'azure' | 'leaflet' | null;

export function clampLayerOpacity(opacity: number): number {
  if (!Number.isFinite(opacity)) return 1;
  return Math.max(0, Math.min(1, opacity));
}

export function applyRasterLayerDisplay(
  layers: any[],
  provider: MapLayerProvider,
  visible: boolean,
  opacity: number,
): void {
  const normalizedOpacity = clampLayerOpacity(opacity);
  const effectiveOpacity = visible ? normalizedOpacity : 0;

  new Set(layers.filter(Boolean)).forEach((layer) => {
    if (provider === 'azure' && typeof layer.setOptions === 'function') {
      layer.setOptions({ visible, opacity: effectiveOpacity });
      return;
    }
    if (provider === 'leaflet' && typeof layer.setOpacity === 'function') {
      layer.setOpacity(effectiveOpacity);
    }
  });
}