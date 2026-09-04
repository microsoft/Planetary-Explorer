import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';

import LandingPage from '../LandingPage';

vi.mock('../GetStartedButton', () => ({
  default: ({ onQuerySelect }: {
    onQuerySelect: (query: string, stacMode?: 'public' | 'pro') => void;
  }) => (
    <button
      type="button"
      onClick={() => onQuerySelect('Show tenant damage imagery.', 'pro')}
    >
      Start Building Damage
    </button>
  ),
}));
vi.mock('../ModelSelector', () => ({ default: () => null }));
vi.mock('../FoundationModelsInfo', () => ({ default: () => null }));
vi.mock('../StacModeToggle', () => ({ default: () => null }));
vi.mock('../STACInfoButton', () => ({ default: () => null }));
vi.mock('../HealthCheckInfo', () => ({ default: () => null }));
vi.mock('../UserAccountMenu', () => ({ default: () => null }));

describe('LandingPage Get Started routing', () => {
  it('applies requested Pro mode before entering with the initial query', () => {
    const calls: string[] = [];
    const onStacModeChange = vi.fn(() => calls.push('mode'));
    const onEnter = vi.fn(() => calls.push('enter'));

    render(
      <LandingPage
        onEnter={onEnter}
        stacMode="public"
        onStacModeChange={onStacModeChange}
        proEnabled
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Start Building Damage' }));

    expect(onStacModeChange).toHaveBeenCalledWith('pro');
    expect(onEnter).toHaveBeenCalledWith('all', 'Show tenant damage imagery.');
    expect(calls).toEqual(['mode', 'enter']);
  });
});