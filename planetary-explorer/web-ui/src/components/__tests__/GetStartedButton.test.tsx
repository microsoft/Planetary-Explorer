import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';

import {
  buildingDamageQueries,
  exampleQueries,
  extremeWeatherQueries,
  forecastQueries,
  mobilityQueries,
  resilienceQueries,
  siteAuditQueries,
  terrainQueries,
} from '../../config/canadianExamples';
import GetStartedButton from '../GetStartedButton';

const features = {
  mpcPublic: true,
  mpcPro: false,
  fabric: false,
  resilience: true,
  weather: true,
};

const allFeatures = {
  mpcPublic: true,
  mpcPro: true,
  fabric: true,
  resilience: true,
  weather: true,
};

const setupExamples = [
  ...exampleQueries.flatMap((category) => category.examples.map((example) => ['Vision', example.query, undefined] as const)),
  ...terrainQueries.map((example) => ['Terrain', example.setupQuery, undefined] as const),
  ...mobilityQueries.map((example) => ['Mobility', example.setupQuery, undefined] as const),
  ...extremeWeatherQueries.map((example) => ['Extreme Weather', example.setupQuery, undefined] as const),
  ...buildingDamageQueries.map((example) => ['Building Damage', example.setupQuery, 'pro'] as const),
  ...siteAuditQueries.map((example) => ['Site Intel', example.setupQuery, undefined] as const),
  ...resilienceQueries.map((example) => ['Resilience', example.setupQuery, undefined] as const),
  ...forecastQueries.map((example) => ['Forecast', example.setupQuery, undefined] as const),
];

describe('GetStartedButton deployment behavior', () => {
  it('locks unavailable integrations from deployment feature flags', () => {
    render(<GetStartedButton features={features} />);

    fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));

    expect(screen.getByRole('button', { name: /Building Damage/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Site Intel/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Resilience/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: /Forecast/ })).toBeEnabled();
  });

  it('allows setup but defers analysis until the map view is open', () => {
    const onQuerySelect = vi.fn();
    render(<GetStartedButton features={features} onQuerySelect={onQuerySelect} />);
    fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));
    fireEvent.click(screen.getByRole('button', { name: /Vision/ }));

    const setupCard = screen.getByText(
      'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26',
    ).closest('.stac-card');
    const rasterCard = screen.getByText(
      'Sample the 2026 red and near-infrared reflectance values at this pin.',
    ).closest('.raster-card');

    expect(setupCard).not.toBeNull();
    expect(rasterCard).not.toBeNull();
    expect(within(setupCard as HTMLElement).getByRole('button', { name: 'Go' })).toBeEnabled();
    expect(within(rasterCard as HTMLElement).getByRole('button', { name: 'Go' })).toBeDisabled();
  });

  it('preserves explicit Pro mode through the landing-page callback', () => {
    const onQuerySelect = vi.fn();
    render(<GetStartedButton features={allFeatures} onQuerySelect={onQuerySelect} />);

    fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));
    fireEvent.click(screen.getByRole('button', { name: /Building Damage/ }));
    const query = buildingDamageQueries[0].setupQuery;
    const setupCard = screen.getByText(query, { exact: true }).closest('.setup-query');
    fireEvent.click(within(setupCard as HTMLElement).getByRole('button', { name: 'Go' }));

    expect(onQuerySelect).toHaveBeenCalledWith(query, 'pro');
  });

  it('marks Setup actions as fresh-context turns', async () => {
    const events: Array<{ query: string; clearSessions: boolean; resetContext: boolean }> = [];
    const handler = (event: Event) => {
      events.push((event as CustomEvent).detail);
    };
    window.addEventListener('planetaryexplorer-stac-query', handler);
    render(<GetStartedButton features={features} />);

    try {
      fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));
      fireEvent.click(screen.getByRole('button', { name: /Vision/ }));
      const query = 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26';
      const card = screen.getByText(query).closest('.stac-card');
      fireEvent.click(within(card as HTMLElement).getByRole('button', { name: 'Go' }));

      await waitFor(() => expect(events).toContainEqual({
        query,
        clearSessions: true,
        resetContext: true,
      }));
    } finally {
      window.removeEventListener('planetaryexplorer-stac-query', handler);
    }
  });

  it.each(setupExamples)(
    'dispatches the %s Setup query as a fresh-context turn: %s',
    async (label, query, stacMode) => {
      const events: Array<{
        query: string;
        clearSessions: boolean;
        resetContext: boolean;
        stacMode?: string;
      }> = [];
      const handler = (event: Event) => events.push((event as CustomEvent).detail);
      window.addEventListener('planetaryexplorer-stac-query', handler);
      render(<GetStartedButton features={allFeatures} />);

      try {
        fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));
        fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));
        const queryElement = screen.getByText(query, { exact: true });
        const card = queryElement.closest('.stac-card, .setup-query');
        expect(card).not.toBeNull();
        fireEvent.click(within(card as HTMLElement).getByRole('button', { name: 'Go' }));

        await waitFor(() => expect(events).toContainEqual({
          query,
          clearSessions: true,
          resetContext: true,
          ...(stacMode ? { stacMode } : {}),
        }));
      } finally {
        window.removeEventListener('planetaryexplorer-stac-query', handler);
      }
    },
  );

  it.each([
    ['Terrain', terrainQueries[0].question],
    ['Mobility', mobilityQueries[0].question],
    ['Extreme Weather', extremeWeatherQueries[0].question],
    ['Building Damage', buildingDamageQueries[0].question],
    ['Site Intel', siteAuditQueries[0].question],
    ['Resilience', resilienceQueries[0].question],
    ['Forecast', forecastQueries[0].question],
  ])('dispatches the canonical %s analysis query from its enabled card', async (label, query) => {
    // Arrange
    const queryEvents: string[] = [];
    const handler = (event: Event) => {
      queryEvents.push((event as CustomEvent<{ query: string }>).detail.query);
    };
    window.addEventListener('planetaryexplorer-query', handler);
    render(<GetStartedButton features={allFeatures} />);

    try {
      // Act
      fireEvent.click(screen.getByTitle('Example queries for all geointelligence modules'));
      fireEvent.click(screen.getByRole('button', { name: new RegExp(label) }));
      const question = screen.getByText(query, { exact: true });
      fireEvent.click(within(question.parentElement as HTMLElement).getByRole('button', { name: 'Go' }));

      // Assert
      await waitFor(() => expect(queryEvents).toContain(query));
    } finally {
      window.removeEventListener('planetaryexplorer-query', handler);
    }
  });
});