import type { ChatLegendDefinition, MapContext } from '../services/api';

const categorical = (
  title: string,
  items: ChatLegendDefinition['items'],
  note?: string,
): ChatLegendDefinition => ({ title, items, note });

export function legendForCollection(collection: string): ChatLegendDefinition | undefined {
  const id = collection.toLowerCase();

  if (id.includes('sentinel-1') || id.includes('sar') || id.includes('palsar')) {
    return categorical('Radar backscatter', [
      { color: '#111827', label: 'Dark', description: 'Smooth water or low return' },
      { color: '#6b7280', label: 'Mid-tone', description: 'Soil or vegetation' },
      { color: '#f8fafc', label: 'Bright', description: 'Rough surface or built structure' },
    ], 'Brightness represents radar return, not visible colour.');
  }

  if (id.includes('dem') || id.includes('elevation') || id.includes('srtm')) {
    return {
      title: 'Terrain elevation',
      gradient: 'linear-gradient(90deg, #2e7d32 0%, #d4b86a 45%, #8b6f47 75%, #ffffff 100%)',
      minLabel: 'Lower terrain',
      maxLabel: 'Higher terrain',
      items: [],
      note: 'Exact elevations depend on the range reported for the displayed layer.',
    };
  }

  if (id.includes('14a') || id.includes('fire') || id.includes('thermal')) {
    return categorical('Fire and thermal intensity', [
      { color: '#1d4ed8', label: 'Blue', description: 'No fire or background' },
      { color: '#fde047', label: 'Yellow', description: 'Low confidence or intensity' },
      { color: '#f97316', label: 'Orange', description: 'Elevated activity' },
      { color: '#dc2626', label: 'Red', description: 'Highest activity' },
    ]);
  }

  if (id.includes('10a1') || id.includes('snow')) {
    return {
      title: 'Snow cover',
      gradient: 'linear-gradient(90deg, #6b4f2a 0%, #38bdf8 45%, #ffffff 100%)',
      minLabel: 'No snow',
      maxLabel: 'Full snow cover',
      items: [],
    };
  }

  if (id.includes('13q1') || id.includes('ndvi') || id.includes('vegetation')) {
    return {
      title: 'Vegetation index',
      gradient: 'linear-gradient(90deg, #8b4513 0%, #facc15 40%, #86efac 70%, #166534 100%)',
      minLabel: 'Water or bare ground',
      maxLabel: 'Dense vegetation',
      items: [],
      note: 'NDVI normally ranges from -1 to 1.',
    };
  }

  if (
    id.includes('17a2h')
    || id.includes('17a3')
    || id.includes('gpp')
    || id.includes('npp')
    || id.includes('productivity')
  ) {
    return {
      title: 'Vegetation productivity',
      gradient: 'linear-gradient(90deg, #440154 0%, #2a788e 50%, #7ad151 100%)',
      minLabel: 'Lower productivity',
      maxLabel: 'Higher productivity',
      items: [],
    };
  }

  if (
    id.includes('sentinel-2')
    || id.includes('landsat')
    || id.includes('hls')
    || id.includes('naip')
  ) {
    return categorical('Natural-colour imagery', [
      { color: '#2563eb', label: 'Blue or dark', description: 'Water or shadow' },
      { color: '#2f855a', label: 'Green', description: 'Vegetation' },
      { color: '#a16207', label: 'Tan or brown', description: 'Bare ground' },
      { color: '#64748b', label: 'Grey', description: 'Built surface' },
      { color: '#f8fafc', label: 'White', description: 'Cloud, snow, or bright surface' },
    ], 'These are interpretive cues. Confirm classes with raster values and collection metadata.');
  }

  return undefined;
}

function firstCollection(response: any, mapContext?: MapContext): string | undefined {
  const candidates = [
    response?.collection,
    response?.collection_id,
    response?.data?.search_metadata?.collections_searched?.[0],
    response?.data?.stac_results?.features?.[0]?.collection,
    response?.results?.features?.[0]?.collection,
    response?.translation_metadata?.all_tile_urls?.[0]?.collection,
    response?.items?.[0]?.collection,
    mapContext?.current_collection,
    mapContext?.tile_urls?.[0]?.collection,
    mapContext?.stac_items?.[0]?.collection,
  ];

  return candidates.find((candidate) => typeof candidate === 'string' && candidate.trim())?.trim();
}

function hasHlsFireFalseColour(response: any, mapContext?: MapContext): boolean {
  const collection = firstCollection(response, mapContext)?.toLowerCase() || '';
  if (!collection.includes('hls')) return false;

  if (response?.translation_metadata?.render_profile?.id === 'hls-s30-fire-false-colour') {
    return true;
  }

  const urls = [
    response?.translation_metadata?.mosaic_tilejson?.tilejson_url,
    ...(response?.translation_metadata?.all_tile_urls || []).map((tile: any) => tile?.tilejson_url),
    mapContext?.imagery_url,
    ...(mapContext?.tile_urls || []).map((tile) => tile.tilejson_url),
  ].filter((url): url is string => typeof url === 'string');

  return urls.some((url) => {
    const decoded = decodeURIComponent(url);
    return ['B12', 'B8A', 'B04'].every((asset) => (
      new RegExp(`[?&]assets=${asset}(?:&|$)`).test(decoded)
    ));
  });
}

function hlsFireLegend(): ChatLegendDefinition {
  return categorical('HLS fire false colour', [
    { color: '#22c55e', label: 'Green', description: 'Vegetation with stronger near-infrared response' },
    { color: '#b91c1c', label: 'Red or rust', description: 'SWIR-bright dry, burned, or heated surface' },
    { color: '#ec4899', label: 'Pink or tan', description: 'Sparse vegetation or bare ground' },
    { color: '#111827', label: 'Dark', description: 'Water, shadow, or masked pixels' },
  ], 'B12/B8A/B04 uses scene-level 2nd to 98th percentile stretches. Colours are relative to this scene, not official burn severity.');
}

function hasCompletedGeoFmFeatures(response: any): boolean {
  const structured = response?.structured || response?.data?.structured || {};
  return ['compare_with_geofm', 'get_geofm_run'].some((toolName) => {
    const evidence = structured?.[toolName];
    return evidence?.success === true
      && evidence?.structured?.status === 'complete'
      && Array.isArray(evidence.structured.features)
      && evidence.structured.features.length > 0;
  });
}

export function deriveChatLegend(response: any, mapContext?: MapContext): ChatLegendDefinition | undefined {
  if (!response || response?.isError) return undefined;

  const isHlsFireFalseColour = hasHlsFireFalseColour(response, mapContext);

  if (hasCompletedGeoFmFeatures(response)) {
    return categorical('PlanAura contextual change', [
      { color: '#ef4444', label: 'Red area', description: 'Detected change above the requested threshold' },
      { color: '#7f1d1d', label: 'Dark red outline', description: 'Boundary of a detected change polygon' },
    ], isHlsFireFalseColour
      ? 'Red overlays are model detections. The HLS background is a scene-stretched B12/B8A/B04 fire false-colour composite.'
      : 'Red overlays are model detections. The HLS imagery underneath retains its natural-colour interpretation.');
  }

  if (isHlsFireFalseColour) return hlsFireLegend();

  if (response?.isResilienceResponse && Array.isArray(response?.dossier?.facilities)) {
    return categorical('Facility risk severity', [
      { color: '#22c55e', label: 'Low', description: 'Routine monitoring' },
      { color: '#eab308', label: 'Moderate', description: 'Prepare mitigation' },
      { color: '#f97316', label: 'High', description: 'Action required' },
      { color: '#dc2626', label: 'Severe', description: 'Immediate response' },
    ], 'Marker numbers show the overall risk score.');
  }

  if (response?.isMobilityResponse || response?.geoint_result?.result?.analysis_type === 'mobility_analysis') {
    return categorical('Terrain mobility', [
      { color: '#10b981', label: 'Passable', description: 'Normal movement' },
      { color: '#f59e0b', label: 'Reduced speed', description: 'Use caution' },
      { color: '#ef4444', label: 'Impassable', description: 'No-go terrain' },
    ]);
  }

  if (response?.isTerrainResponse || response?.geoint_result?.result?.analysis_type === 'terrain_analysis') {
    return categorical('Slope classification', [
      { color: '#00ff00', label: 'Flat', description: '0-15 degrees' },
      { color: '#ffff00', label: 'Moderate', description: '15-30 degrees' },
      { color: '#ff8000', label: 'Steep', description: '30-45 degrees' },
      { color: '#ff0000', label: 'Very steep', description: '45 degrees or more' },
    ]);
  }

  if (response?.isBuildingDamageResponse) {
    return categorical('Building damage classification', [
      { color: '#16a34a', label: 'No damage', description: 'Structure appears intact' },
      { color: '#facc15', label: 'Minor', description: 'Limited visible damage' },
      { color: '#f97316', label: 'Major', description: 'Significant structural damage' },
      { color: '#dc2626', label: 'Destroyed', description: 'Complete or near-complete loss' },
    ], 'AI classifications require field verification.');
  }

  const collection = firstCollection(response, mapContext);
  return collection ? legendForCollection(collection) : undefined;
}