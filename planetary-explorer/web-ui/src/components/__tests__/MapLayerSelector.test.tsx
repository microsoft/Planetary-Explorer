import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';

import MapLayerSelector, { SelectableMapLayer } from '../MapLayerSelector';

const layer = (overrides: Partial<SelectableMapLayer> = {}): SelectableMapLayer => ({
  id: 'imagery',
  label: 'HLS fire false colour',
  swatch: 'linear-gradient(90deg, #8b1e1e, #3f8d55)',
  visible: true,
  opacity: 1,
  onVisibilityChange: vi.fn(),
  onOpacityChange: vi.fn(),
  ...overrides,
});

describe('MapLayerSelector', () => {
  it('does not render before map layers are available', () => {
    render(<MapLayerSelector layers={[]} open={false} onOpenChange={vi.fn()} />);

    expect(screen.queryByRole('button', { name: 'Map layers' })).not.toBeInTheDocument();
  });

  it('lists available layers dynamically when opened', () => {
    render(
      <MapLayerSelector
        layers={[
          layer(),
          layer({ id: 'geofm', label: 'PlanAura contextual change', opacity: 0.7 }),
        ]}
        open
        onOpenChange={vi.fn()}
      />,
    );

    expect(screen.getByText('HLS fire false colour')).toBeInTheDocument();
    expect(screen.getByText('PlanAura contextual change')).toBeInTheDocument();
    expect(screen.getByText('2/2')).toBeInTheDocument();
  });

  it('changes layer visibility and opacity', () => {
    const onVisibilityChange = vi.fn();
    const onOpacityChange = vi.fn();
    render(
      <MapLayerSelector
        layers={[layer({ onVisibilityChange, onOpacityChange })]}
        open
        onOpenChange={vi.fn()}
      />,
    );

    const visibility = screen.getByRole('button', { name: 'HLS fire false colour visibility' });
    expect(visibility).toHaveAttribute('aria-pressed', 'true');
    expect(visibility).toHaveAttribute('title', 'Hide HLS fire false colour');
    fireEvent.click(visibility);
    fireEvent.change(screen.getByRole('slider', { name: 'HLS fire false colour opacity' }), {
      target: { value: '55' },
    });

    expect(onVisibilityChange).toHaveBeenCalledWith(false);
    expect(onOpacityChange).toHaveBeenCalledWith(0.55);
  });

  it('reports trigger state and disables opacity for hidden layers', () => {
    const onOpenChange = vi.fn();
    render(
      <MapLayerSelector
        layers={[layer({ visible: false, opacity: 0.65 })]}
        open
        onOpenChange={onOpenChange}
      />,
    );

    const trigger = screen.getByRole('button', { name: 'Map layers' });
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('slider', { name: 'HLS fire false colour opacity' })).toBeDisabled();
    fireEvent.click(trigger);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('moves focus into the panel and closes with Escape', async () => {
    const onOpenChange = vi.fn();
    render(
      <MapLayerSelector
        layers={[layer()]}
        open
        onOpenChange={onOpenChange}
      />,
    );

    const visibility = screen.getByRole('button', { name: 'HLS fire false colour visibility' });
    await waitFor(() => expect(visibility).toHaveFocus());
    fireEvent.keyDown(screen.getByRole('dialog', { name: 'Map layers' }), { key: 'Escape' });

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByRole('button', { name: 'Map layers' })).toHaveFocus();
  });

  it('closes and restores focus when its last layer disappears', async () => {
    const onOpenChange = vi.fn();
    const fallbackFocusRef = { current: document.createElement('button') };
    fallbackFocusRef.current.textContent = 'Map focus target';
    document.body.appendChild(fallbackFocusRef.current);
    render(
      <MapLayerSelector
        layers={[]}
        open
        onOpenChange={onOpenChange}
        fallbackFocusRef={fallbackFocusRef}
      />,
    );

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
      expect(fallbackFocusRef.current).toHaveFocus();
    });
    fallbackFocusRef.current.remove();
  });
});