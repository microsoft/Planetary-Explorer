// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import React from 'react';
import STACInfoButton from './STACInfoButton';
import HealthCheckInfo from './HealthCheckInfo';
import RestartButton from './RestartButton';
import GetStartedButton, { DeploymentFeatureFlags } from './GetStartedButton';
import ModelSelector from './ModelSelector';
import UserAccountMenu from './UserAccountMenu';
import StacModeToggle, { StacMode } from './StacModeToggle';
import FoundationModelsInfo from './FoundationModelsInfo';
import { API_BASE_URL } from '../config/api';

interface HeaderProps {
  onReturnToLanding: () => void;
  onRestartSession?: () => void;
  onModelChange?: (modelId: string) => void;
  selectedModel?: string;
  onReasoningEffortChange?: (effort: string) => void;
  onModelAvailabilityChange?: (ready: boolean) => void;
  selectedReasoningEffort?: string;
  stacMode?: StacMode;
  onStacModeChange?: (next: StacMode) => void;
  /** Surfaced from /api/config.features.mpcPro. When false the toggle renders
   *  in a locked state with a "How to enable" link. */
  proEnabled?: boolean;
  features?: DeploymentFeatureFlags;
}

// Identical to the landing page brand: 44x44 globe icon.
// Brand mark used in the persistent app header. The previous version
// composited a tiny Microsoft 4-color square onto the bottom-right of
// the globe; that overlay has been removed so the brand reads as
// "Planetary Explorer" rather than a Microsoft sub-brand.
const GlobeLogo: React.FC = () => (
  // Container is sized by height only; width auto-scales to preserve the
  // logo's natural aspect ratio (currently ~178x152). object-fit:contain
  // guards against any future asset whose ratio differs.
  // Matches landing page size (48px) so the brand reads consistently across pages.
  <span style={{ display: 'inline-flex', alignItems: 'center', height: 48 }}>
    <img
      src="/icon.png"
      alt="Planetary Explorer"
      style={{ display: 'block', height: 48, width: 'auto', objectFit: 'contain', background: 'transparent', borderRadius: 6 }}
    />
  </span>
);

const Header: React.FC<HeaderProps> = ({ onReturnToLanding, onRestartSession, onModelChange, selectedModel, onReasoningEffortChange, onModelAvailabilityChange, selectedReasoningEffort, stacMode, onStacModeChange, proEnabled, features }) => {
  return (
    <div className="top-header">
      <div style={{ padding: '0' }}>
        <div className="brand" onClick={onReturnToLanding} style={{cursor:'pointer', transition:'opacity 0.2s ease', paddingLeft: 0}}
             onMouseEnter={(e) => (e.target as HTMLElement).style.opacity = '0.8'}
             onMouseLeave={(e) => (e.target as HTMLElement).style.opacity = '1'}>
          <GlobeLogo />
          <div className="brand-name">Planetary Explorer</div>
        </div>
      </div>
      <div className="header-controls">
        <GetStartedButton features={features} />
        <ModelSelector
          onModelChange={onModelChange}
          selectedModel={selectedModel}
          onReasoningEffortChange={onReasoningEffortChange}
          onAvailabilityChange={onModelAvailabilityChange}
          selectedReasoningEffort={selectedReasoningEffort}
          apiBaseUrl={API_BASE_URL}
        />
        <FoundationModelsInfo apiBaseUrl={API_BASE_URL} />
        {stacMode && onStacModeChange && (
          <StacModeToggle mode={stacMode} onChange={onStacModeChange} proEnabled={proEnabled} />
        )}
        <STACInfoButton />
        <HealthCheckInfo apiBaseUrl={API_BASE_URL} />
        {onRestartSession && <RestartButton onRestart={onRestartSession} />}
        <UserAccountMenu />
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }
      `}</style>
    </div>
  );
};

export default Header;
