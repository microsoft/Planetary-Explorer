// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import React, { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Header from './components/Header';
import LandingPage from './components/LandingPage';
import MainApp from './components/MainApp';
import { GlobalStyles } from './styles/GlobalStyles';
import { API_BASE_URL } from './config/api';
import type { ChatHistoryContext } from './services/api';
import { confirmFailedHistoryDiscard, restoredStacMode } from './utils/chatHistory';
import type { DeploymentFeatureFlags } from './components/GetStartedButton';

const queryClient = new QueryClient();

export interface AppState {
  entered: boolean;
  entryTarget: string | null;
  selectedDataset: any | null;
  chatMode: boolean;
  initialQuery?: string;
  sessionKey?: number;
}

// Deployment-time feature flags, surfaced by /api/config. The SPA uses
// these to lock controls (e.g. the StacModeToggle "Pro" side) for
// integrations that aren't wired up in this environment. We default to
// the most-permissive shape so the UI stays usable while the fetch is
// in flight; the backend's response then narrows the flags.
interface DeploymentFeatures extends DeploymentFeatureFlags {
  chatHistory: boolean;
}

const DEFAULT_FEATURES: DeploymentFeatures = {
  mpcPublic: true,
  mpcPro: false,
  fabric: false,
  chatHistory: false,
  resilience: false,
  weather: false,
};

function App() {
  const [appState, setAppState] = useState<AppState>({
    entered: false,
    entryTarget: null,
    selectedDataset: null,
    chatMode: false,
    initialQuery: undefined,
    sessionKey: 1
  });

  const [geointMode, setGeointMode] = useState<boolean>(false);
  // ModelSelector reconciles the saved preference against live health before
  // publishing it here. Until then, requests omit model and let the API choose
  // its configured default.
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [modelSelectionReady, setModelSelectionReady] = useState(false);
  const [reasoningEffort, setReasoningEffort] = useState<string>(() => {
    return localStorage.getItem('planetaryexplorer-reasoning-effort') || 'none';
  });
  const [stacMode, setStacMode] = useState<'public' | 'pro'>('public');
  // Note: stacMode intentionally does NOT read from localStorage. Product
  // requirement is that every fresh app open defaults to MPC Public; the
  // user must explicitly click the Pro toggle to switch. The current
  // selection still lives in React state for the lifetime of the session
  // so toggling once stays sticky during navigation between landing and
  // the chat/map view.

  const [features, setFeatures] = useState<DeploymentFeatures>(DEFAULT_FEATURES);
  const [hasUnsavedHistorySnapshot, setHasUnsavedHistorySnapshot] = useState(false);

  // Pull deployment feature flags once on mount. We treat any error as
  // "keep the defaults" so the UI stays functional even if the config
  // endpoint is briefly unreachable. The flags are static per-deploy, so
  // we don't poll or refetch.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/config`, {
      credentials: import.meta.env.DEV ? 'omit' : 'include',
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data || !data.features) return;
        const next: DeploymentFeatures = {
          mpcPublic: data.features.mpcPublic !== false,
          mpcPro: !!data.features.mpcPro,
          fabric: !!data.features.fabric,
          chatHistory: !!data.features.chatHistory,
          resilience: !!data.features.resilience,
          weather: !!data.features.weather,
        };
        setFeatures(next);
        // If Pro is locked out by this deployment but the user had it
        // selected (e.g. from a previous session that did support it),
        // snap them back to Public so the toggle and the requests agree.
        if (!next.mpcPro) {
          setStacMode((current) => (current === 'pro' ? 'public' : current));
        }
      })
      .catch(() => { /* keep defaults */ });
    return () => {
      cancelled = true;
    };
  }, []);
  const handleModelChange = (modelId: string) => {
    console.log(' App: Model changed to:', modelId);
    setSelectedModel(modelId);
    localStorage.setItem('planetaryexplorer-model', modelId);
  };

  const handleReasoningEffortChange = (effort: string) => {
    setReasoningEffort(effort);
    localStorage.setItem('planetaryexplorer-reasoning-effort', effort);
  };

  const handleStacModeChange = (next: 'public' | 'pro') => {
    // Defense-in-depth: even if a child somehow calls onChange with 'pro'
    // while the deployment has it locked out, ignore the change. The
    // StacModeToggle should already prevent this in its own click handler
    // but the source of truth lives here.
    if (next === 'pro' && !features.mpcPro) {
      console.log(' App: STAC mode change to \'pro\' blocked (mpcPro disabled in this deployment)');
      return;
    }
    console.log(' App: STAC mode changed to:', next);
    setStacMode(next);
    // Intentionally NOT persisting to localStorage -- see useState init above.
  };

  const handleEnterApp = (target: string, query?: string) => {
    setAppState(prev => ({ 
      ...prev, 
      entered: true, 
      entryTarget: target,
      initialQuery: query,
      chatMode: !!query // Enable chat mode if there's a query
    }));
  };

  const handleReturnToLanding = () => {
    if (!confirmFailedHistoryDiscard(hasUnsavedHistorySnapshot)) return;
    setHasUnsavedHistorySnapshot(false);
    setAppState({ entered: false, entryTarget: null, selectedDataset: null, chatMode: false, initialQuery: undefined });
  };

  const handleRestartSession = (discardConfirmed = false) => {
    if (!discardConfirmed && !confirmFailedHistoryDiscard(hasUnsavedHistorySnapshot)) return;
    setHasUnsavedHistorySnapshot(false);
    // Clear chat and dataset selection but stay in the app
    // Force chat component to re-render by updating session key
    setAppState(prev => ({ 
      ...prev, 
      selectedDataset: null, 
      chatMode: false, 
      initialQuery: undefined,
      sessionKey: Date.now() // Add session key to force re-render
    }));
    //  Also reset GEOINT mode to simulate fresh page load
    setGeointMode(false);
  };

  const handleDatasetSelect = (dataset: any) => {
    setAppState(prev => ({ ...prev, selectedDataset: dataset, chatMode: true }));
  };

  const handleRestoreChatContext = (context: ChatHistoryContext) => {
    if (context.selectedModel) {
      setModelSelectionReady(false);
      handleModelChange(context.selectedModel);
    }
    if (context.reasoningEffort) handleReasoningEffortChange(context.reasoningEffort);
    const allowedStacMode = restoredStacMode(context.stacMode, features.mpcPro);
    if (allowedStacMode) handleStacModeChange(allowedStacMode);
    setAppState(prev => ({
      ...prev,
      selectedDataset: context.selectedDataset
        ? { ...context.selectedDataset, description: context.selectedDataset.description || '' }
        : null,
      chatMode: true,
      initialQuery: undefined,
    }));
  };

  return (
    <QueryClientProvider client={queryClient}>
      <GlobalStyles />
      <div className="app-container">
        {!appState.entered ? (
          <LandingPage
            onEnter={handleEnterApp}
            onModelChange={handleModelChange}
            selectedModel={selectedModel}
            onReasoningEffortChange={handleReasoningEffortChange}
            onModelAvailabilityChange={setModelSelectionReady}
            selectedReasoningEffort={reasoningEffort}
            stacMode={stacMode}
            onStacModeChange={handleStacModeChange}
            proEnabled={features.mpcPro}
            features={features}
          />
        ) : (
          <>
            <Header 
              onReturnToLanding={handleReturnToLanding}
              onRestartSession={handleRestartSession}
              onModelChange={handleModelChange}
              selectedModel={selectedModel}
              onReasoningEffortChange={handleReasoningEffortChange}
              onModelAvailabilityChange={setModelSelectionReady}
              selectedReasoningEffort={reasoningEffort}
              stacMode={stacMode}
              onStacModeChange={handleStacModeChange}
              proEnabled={features.mpcPro}
              features={features}
            />
            <MainApp 
              appState={appState}
              onDatasetSelect={handleDatasetSelect}
              onReturnToLanding={handleReturnToLanding}
              onRestartSession={handleRestartSession}
              geointMode={geointMode}
              onGeointToggle={setGeointMode}
              selectedModel={modelSelectionReady ? selectedModel : ''}
              reasoningEffort={modelSelectionReady ? reasoningEffort : undefined}
              chatHistoryEnabled={features.chatHistory}
              onRestoreChatContext={handleRestoreChatContext}
              stacMode={stacMode}
              onStacModeChange={handleStacModeChange}
              onHistorySaveRiskChange={setHasUnsavedHistorySnapshot}
              proEnabled={features.mpcPro}
              features={features}
            />
          </>
        )}
      </div>
    </QueryClientProvider>
  );
}

export default App;
