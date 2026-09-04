// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import React, { useState } from 'react';
import './GetStartedButton.css';
import {
  buildingDamageQueries,
  exampleQueries,
  extremeWeatherQueries,
  forecastQueries,
  mobilityQueries,
  resilienceQueries,
  siteAuditQueries,
  terrainQueries,
} from '../config/canadianExamples';

export interface DeploymentFeatureFlags {
  mpcPublic: boolean;
  mpcPro: boolean;
  fabric: boolean;
  resilience: boolean;
  // True when at least one weather provider endpoint (Aurora / Earth-2
  // FCN / MAI Weather, or the CPU weather stub) is configured. Drives
  // whether the Forecast tile is interactive.
  weather: boolean;
}

interface GetStartedButtonProps {
  onQuerySelect?: (query: string, stacMode?: 'public' | 'pro') => void;
  /** Deployment feature flags from /api/config. When omitted (e.g.
   *  Storybook) every tile is enabled. Agent tiles whose underlying
   *  integrations are disabled in this deployment render as locked so
   *  users don't pick a workflow that has no backend wired up. */
  features?: DeploymentFeatureFlags;
}

const GetStartedButton: React.FC<GetStartedButtonProps> = ({ onQuerySelect, features }) => {
  // Default to fully-enabled when no flags were passed (keeps the
  // component usable in tests / storybook). The App.tsx fetch fills
  // these in once /api/config responds.
  const siteIntelEnabled = features?.fabric ?? true;
  const resilienceEnabled = features?.resilience ?? true;
  const forecastEnabled = features?.weather ?? true;
  const buildingDamageEnabled = features?.mpcPro ?? true;
  const mapWorkflowReady = !onQuerySelect;
  const mapRequiredTitle = 'Run the Setup query first, then reopen Get Started in the map view.';
  const lockedTitle = (label: string, reason: string) =>
    `${label} is disabled in this deployment. ${reason}`;
  const [showModal, setShowModal] = useState(false);
  const [activeColumn, setActiveColumn] = useState<'stac' | 'vision'>('stac'); // For mobile toggle
  const [activeTab, setActiveTab] = useState<'none' | 'stac' | 'terrain' | 'mobility' | 'extreme-weather' | 'building-damage' | 'site-audit' | 'resilience' | 'forecast'>('none'); // Main tab navigation - 'none' shows only module buttons

  // Handler for STAC search queries (Step 1) - clears all GEOINT sessions
  const handleStacQueryClick = (query: string, requestedStacMode?: 'public' | 'pro') => {
    console.log('GetStartedButton: STAC query clicked:', query);
    
    // Close the modal
    setShowModal(false);
    
    // If onQuerySelect callback provided (from Landing Page), use it
    if (onQuerySelect) {
      console.log('GetStartedButton: Using onQuerySelect callback');
      onQuerySelect(query, requestedStacMode);
      return;
    }
    
    // Dispatch STAC query event - this clears all GEOINT sessions
    setTimeout(() => {
      console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-stac-query event (clears sessions)');
      const event = new CustomEvent('planetaryexplorer-stac-query', { 
        detail: {
          query,
          clearSessions: true,
          resetContext: true,
          ...(requestedStacMode ? { stacMode: requestedStacMode } : {}),
        },
        bubbles: true,
        composed: true
      });
      window.dispatchEvent(event);
    }, 150);
  };

  // Handler for Raster Analysis queries (Step 2a) - uses sample_raster_value tool
  // REQUIRES: Vision module ON + pin dropped + STAC data loaded
  const handleRasterQueryClick = (query: string) => {
    console.log('GetStartedButton: Raster query clicked:', query);
    
    // Close the modal
    setShowModal(false);
    
    // If onQuerySelect callback provided (from Landing Page), use it
    if (onQuerySelect) {
      console.log('GetStartedButton: Using onQuerySelect callback for raster query');
      onQuerySelect(query);
      return;
    }
    
    // Dispatch query event with raster analysis type hint and validation requirements
    setTimeout(() => {
      console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-query event (raster)');
      const event = new CustomEvent('planetaryexplorer-query', { 
        detail: { 
          query, 
          analysisType: 'raster',
          requiresVision: true,  // Must have Vision module ON
          requiresPin: true,     // Must have a pin dropped
          requiresStacData: true // Must have STAC tiles loaded (Step 1 completed)
        },
        bubbles: true,
        composed: true
      });
      window.dispatchEvent(event);
    }, 150);
  };

  // Handler for Image/Screenshot Analysis queries (Step 2b) - uses analyze_screenshot tool
  // REQUIRES: Vision module ON + pin dropped + STAC data loaded
  const handleScreenshotQueryClick = (query: string) => {
    console.log('GetStartedButton: Screenshot query clicked:', query);
    
    // Close the modal
    setShowModal(false);
    
    // If onQuerySelect callback provided (from Landing Page), use it
    if (onQuerySelect) {
      console.log('GetStartedButton: Using onQuerySelect callback for screenshot query');
      onQuerySelect(query);
      return;
    }
    
    // Dispatch query event with screenshot analysis type hint and validation requirements
    setTimeout(() => {
      console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-query event (screenshot)');
      const event = new CustomEvent('planetaryexplorer-query', { 
        detail: { 
          query, 
          analysisType: 'screenshot',
          requiresVision: true,  // Must have Vision module ON
          requiresPin: true,     // Must have a pin dropped  
          requiresStacData: true // Must have STAC tiles loaded (Step 1 completed)
        },
        bubbles: true,
        composed: true
      });
      window.dispatchEvent(event);
    }, 150);
  };

  // Handler for Terrain/Mobility/Extreme Weather/Building Damage queries (generic vision queries without specific tool hints)
  const handleVisionQueryClick = (query: string) => {
    console.log('GetStartedButton: Vision query clicked:', query);
    
    // Close the modal
    setShowModal(false);
    
    // If onQuerySelect callback provided (from Landing Page), use it
    if (onQuerySelect) {
      console.log('GetStartedButton: Using onQuerySelect callback for vision query');
      onQuerySelect(query);
      return;
    }
    
    // Dispatch query event without specific analysis type
    setTimeout(() => {
      console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-query event (vision)');
      const event = new CustomEvent('planetaryexplorer-query', { 
        detail: { query },
        bubbles: true,
        composed: true
      });
      window.dispatchEvent(event);
    }, 150);
  };

  // Handler for Resilience scenario questions. Differs from
  // `handleVisionQueryClick` because it ALSO flips the active module to
  // 'resilience' before sending the chat query — otherwise Chat.tsx sees
  // no active module and falls through to the generic /api/query path
  // (which is why "If our Vancouver distribution centre goes offline..." was getting a
  // generic LLM answer instead of running the planner against the
  // supply-edges seed graph). MapView listens for
  // `planetaryexplorer-select-module` and calls its handleModuleSelect.
  const handleResilienceQueryClick = (query: string) => {
    console.log('GetStartedButton: Resilience query clicked:', query);
    setShowModal(false);

    if (onQuerySelect) {
      // Landing-page path: caller has already wired its own routing, so
      // just defer to it (the landing page does not have a "Resilience
      // module" concept yet — it dumps queries into the chat directly).
      onQuerySelect(query);
      return;
    }

    // Flip module first, then send the question after a short delay so
    // MapView's setSelectedModule + Chat's selectedModuleRef have time to
    // settle.
    console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-select-module (resilience)');
    const selectEvt = new CustomEvent('planetaryexplorer-select-module', {
      detail: { module: 'resilience' },
      bubbles: true,
      composed: true,
    });
    window.dispatchEvent(selectEvt);

    setTimeout(() => {
      console.log('[OUTBOX] GetStartedButton: Dispatching planetaryexplorer-query event (resilience)');
      const queryEvt = new CustomEvent('planetaryexplorer-query', {
        detail: { query },
        bubbles: true,
        composed: true,
      });
      window.dispatchEvent(queryEvt);
    }, 300);
  };

  return (
    <>
      <div
        onClick={() => setShowModal(true)}
        className="get-started-button"
        title="Example queries for all geointelligence modules"
      >
        <span className="get-started-button-label">Get Started</span>
      </div>

      {showModal && (
        <div className="get-started-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="get-started-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="get-started-modal-header">
              <h2>Get Started</h2>
              <button 
                onClick={() => setShowModal(false)} 
                className="get-started-modal-close"
                title="Close"
              >
                ×
              </button>
            </div>

            <div className="get-started-modal-body">
              {/* Module Selection - Large buttons with descriptions */}
              <section className="get-started-section" style={{ marginBottom: '16px' }}>
                <div className="module-selector-grid">
                  <button 
                    className={`module-selector-btn vision-selector ${activeTab === 'stac' ? 'active' : ''}`}
                    onClick={() => setActiveTab(activeTab === 'stac' ? 'none' : 'stac')}
                  >
                    <span className="module-selector-label">Vision</span>
                    <span className="module-selector-desc">AI image analysis of map imagery and raster analysis of geospatial data</span>
                  </button>
                  <button 
                    className={`module-selector-btn site-audit-selector ${activeTab === 'site-audit' ? 'active' : ''}${siteIntelEnabled ? '' : ' disabled'}`}
                    onClick={() => siteIntelEnabled && setActiveTab(activeTab === 'site-audit' ? 'none' : 'site-audit')}
                    disabled={!siteIntelEnabled}
                    title={siteIntelEnabled ? undefined : lockedTitle('Site Intel', 'Requires Microsoft Fabric integration (set enableFabric=true in main.parameters.json and supply fabricWorkspaceId / fabricLakehouseId).')}
                  >
                    <span className="module-selector-label">Site Intel</span>
                    <span className="module-selector-desc">Rank candidate sites by power, water, hazards &amp; permitting precedent</span>
                  </button>
                  <button
                    className={`module-selector-btn resilience-selector ${activeTab === 'resilience' ? 'active' : ''}${resilienceEnabled ? '' : ' disabled'}`}
                    onClick={() => resilienceEnabled && setActiveTab(activeTab === 'resilience' ? 'none' : 'resilience')}
                    disabled={!resilienceEnabled}
                    title={resilienceEnabled ? undefined : lockedTitle('Resilience', 'Requires Microsoft Fabric integration (set enableFabric=true in main.parameters.json and supply fabricWorkspaceId / fabricLakehouseId).')}
                  >
                    <span className="module-selector-label">Resilience</span>
                    <span className="module-selector-desc">Monitor facilities &amp; supply chains for climate &amp; hazard disruption risk</span>
                  </button>
                  <button
                    className={`module-selector-btn forecast-selector ${activeTab === 'forecast' ? 'active' : ''}${forecastEnabled ? '' : ' disabled'}`}
                    onClick={() => forecastEnabled && setActiveTab(activeTab === 'forecast' ? 'none' : 'forecast')}
                    disabled={!forecastEnabled}
                    title={forecastEnabled ? undefined : lockedTitle('Forecast', 'Requires at least one AI weather model endpoint. Set deployWeatherStub=true (CPU mock) or supply auroraEndpointUrl / earth2FcnEndpointUrl / maiWeatherEndpointUrl in main.parameters.json.')}
                  >
                    <span className="module-selector-label">Forecast</span>
                    <span className="module-selector-desc">Short-range forecasts from every configured AI weather provider for any point on the map</span>
                  </button>
                  <button 
                    className={`module-selector-btn weather-selector ${activeTab === 'extreme-weather' ? 'active' : ''}`}
                    onClick={() => setActiveTab(activeTab === 'extreme-weather' ? 'none' : 'extreme-weather')}
                  >
                    <span className="module-selector-label">Extreme Weather</span>
                    <span className="module-selector-desc">Global climate projections: temperature, precipitation & wind from NASA CMIP6</span>
                  </button>
                  <button 
                    className={`module-selector-btn terrain-selector ${activeTab === 'terrain' ? 'active' : ''}`}
                    onClick={() => setActiveTab(activeTab === 'terrain' ? 'none' : 'terrain')}
                  >
                    <span className="module-selector-label">Terrain</span>
                    <span className="module-selector-desc">Landscape, elevation & environmental characteristics</span>
                  </button>
                  <button 
                    className={`module-selector-btn mobility-selector ${activeTab === 'mobility' ? 'active' : ''}`}
                    onClick={() => setActiveTab(activeTab === 'mobility' ? 'none' : 'mobility')}
                  >
                    <span className="module-selector-label">Mobility</span>
                    <span className="module-selector-desc">Traversability across two points based on terrain and context</span>
                  </button>
                  <button
                    className={`module-selector-btn damage-selector ${activeTab === 'building-damage' ? 'active' : ''}${buildingDamageEnabled ? '' : ' disabled'}`}
                    onClick={() => buildingDamageEnabled && setActiveTab(activeTab === 'building-damage' ? 'none' : 'building-damage')}
                    disabled={!buildingDamageEnabled}
                    title={buildingDamageEnabled ? undefined : lockedTitle('Building Damage', 'Requires MPC Pro tenant imagery. Enable MPC Pro and configure a private GeoCatalog before running this workflow.')}
                  >
                    <span className="module-selector-label">Building Damage</span>
                    <span className="module-selector-desc">Structural damage assessment from MPC Pro tenant aerial imagery</span>
                  </button>
                </div>
              </section>

              {/* Query Content - Only shows when a module is selected */}

              {/* STAC + Vision Tab Content - shows when Vision is clicked */}
              {activeTab === 'stac' && (
                <>
                  {/* Instructions for Vision */}
                  <div className="instructions-box" style={{ marginBottom: '20px' }}>
                    <p className="instruction-step">
                      <strong>About:</strong> AI looks at satellite imagery and answers questions about what’s on the ground — vegetation, buildings, water, fire scars, and change over time.
                    </p>
                    <p className="instruction-step">
                      <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on an example below to load satellite imagery on the map.
                    </p>
                    <p className="instruction-step">
                      <strong>Step 2:</strong> Select the <strong>Vision</strong> module, drop a pin, then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on a vision query or type your own.
                    </p>
                  </div>

                  {/* Mobile Column Toggle */}
                  <div className="column-toggle-mobile">
                    <button 
                      className={`toggle-btn ${activeColumn === 'stac' ? 'active' : ''}`}
                      onClick={() => setActiveColumn('stac')}
                    >
                      Step 1: STAC Search
                    </button>
                    <button 
                      className={`toggle-btn ${activeColumn === 'vision' ? 'active' : ''}`}
                      onClick={() => setActiveColumn('vision')}
                    >
                      Step 2: Vision Module
                    </button>
                  </div>

                  {/* Two Column Headers */}
                  <div className="three-column-header">
                    <div className="column-header stac-header">
                      <div className="column-header-row">
                        <span className="column-title">Step 1: STAC Search</span>
                      </div>
                    </div>
                    <div className="column-header vision-module-header">
                      <div className="column-header-row">
                        <span className="column-title vision-module-title">Step 2: Vision Module</span>
                      </div>
                      <div className="vision-sub-headers">
                        <div className="sub-header raster-sub">
                          <span className="sub-header-title">Raster Analysis</span>
                        </div>
                        <div className="sub-header screenshot-sub">
                          <span className="sub-header-title">Image Analysis</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {exampleQueries.map((category) => (
                      <div key={category.category} className="example-category">
                        <h4 className="category-title">{category.category}</h4>
                        
                        {/* Row-based layout: each example pair is a row with 3 columns */}
                        <div className="example-rows">
                          {category.examples.map((example, index) => (
                            <div key={`row-${index}`} className="example-row three-col">
                              {/* STAC Search Card */}
                              <div className={`example-card stac-card ${activeColumn === 'stac' ? 'active' : ''}`}>
                                <div className="example-query">
                                  <strong>{example.query}</strong>
                                </div>
                                <div className="example-description">
                                  {example.description}
                                </div>
                                <div className="example-meta">
                                  <span className="example-dataset">{example.dataset}</span>
                                  <div className="example-buttons">
                                    <button
                                      className="copy-query-btn"
                                      onClick={() => handleStacQueryClick(example.query)}
                                      title="Run this query in Copilot"
                                    >
                                      Go
                                    </button>
                                    {example.pc_link && (
                                      <button
                                        className="pc-explorer-btn"
                                        onClick={() => window.open(example.pc_link, '_blank')}
                                        title="View in Planetary Computer Explorer"
                                      >
                                        PC
                                      </button>
                                    )}
                                  </div>
                                </div>
                              </div>
                              
                              {/* Raster Analysis Card (Step 2a) */}
                              <div className={`example-card raster-card ${activeColumn === 'vision' ? 'active' : ''}`}>
                                <div className="example-query">
                                  <strong>{example.rasterQuery || 'Coming soon...'}</strong>
                                </div>
                                <div className="example-meta">
                                  <div className="example-buttons">
                                    <button
                                      className="copy-query-btn"
                                      onClick={() => handleRasterQueryClick(example.rasterQuery || '')}
                                      title={mapWorkflowReady ? 'Run this Raster query' : mapRequiredTitle}
                                      disabled={!example.rasterQuery || !mapWorkflowReady}
                                    >
                                      Go
                                    </button>
                                  </div>
                                </div>
                              </div>
                              
                              {/* Image Analysis Card (Step 2b) */}
                              <div className={`example-card screenshot-card ${activeColumn === 'vision' ? 'active' : ''}`}>
                                <div className="example-query">
                                  <strong>{example.screenshotQuery || 'Coming soon...'}</strong>
                                </div>
                                <div className="example-meta">
                                  <div className="example-buttons">
                                    <button
                                      className="copy-query-btn"
                                      onClick={() => handleScreenshotQueryClick(example.screenshotQuery || '')}
                                      title={mapWorkflowReady ? 'Run this Image Analysis query' : mapRequiredTitle}
                                      disabled={!example.screenshotQuery || !mapWorkflowReady}
                                    >
                                      Go
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {/* Terrain Analysis Tab Content */}
                {activeTab === 'terrain' && (
                  <div className="terrain-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Describes the landscape at a point — elevation, slope, land cover, water, and surrounding environment — from public elevation and land-cover datasets.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Setup</strong> query to load data on the map.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Select the <strong>Terrain</strong> module, drop a pin, then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Analyze</strong> query or type your own.
                      </p>
                    </div>
                    <div className="terrain-queries-grid">
                      {terrainQueries.map((query, index) => (
                        <div key={`terrain-${index}`} className="example-card terrain-card">
                          <div className="query-location">{query.location}</div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Load the map first"
                            >
                              Go
                            </button>
                          </div>
                          <div className="terrain-question">
                            <span className="query-label">2. Analyze:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Run terrain analysis' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                          <div className="expected-tools">
                            <span className="tools-label">Expected Tools:</span>
                            {query.expectedTools.map((tool, i) => (
                              <span key={i} className="tool-tag">{tool}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Mobility Assessment Tab Content */}
                {activeTab === 'mobility' && (
                  <div className="mobility-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Estimates whether you can travel between two points on the ground, given the terrain, land cover, and surroundings.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Setup</strong> query to load imagery on the map.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Select the <strong>Mobility</strong> module, drop <strong>Pin A</strong> (start) and <strong>Pin B</strong> (destination), then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Ask</strong> query or type your own.
                      </p>
                    </div>
                    <div className="mobility-queries-grid">
                      {mobilityQueries.map((query, index) => (
                        <div key={`mobility-${index}`} className="example-card mobility-card">
                          <div className="query-location">{query.location}</div>
                          <div className="analysis-type">
                            <span className={`analysis-badge ${query.analysisType.toLowerCase().replace(/\s+/g, '-')}`}>
                              {query.analysisType}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Load imagery on the map"
                            >
                              Go
                            </button>
                          </div>
                          <div className="mobility-question">
                            <span className="query-label">2. Ask:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Ask mobility question' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Extreme Weather Tab Content */}
                {activeTab === 'extreme-weather' && (
                  <div className="extreme-weather-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Long-range climate outlook — temperature, precipitation, and wind projections for the coming decades from NASA’s CMIP6 climate models.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Setup</strong> query to move the map to the region.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Select the <strong>Extreme Weather</strong> module, drop a pin, then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Analyze</strong> query or type your own.
                      </p>
                    </div>
                    <div className="extreme-weather-queries-grid">
                      {extremeWeatherQueries.map((query, index) => (
                        <div key={`extreme-weather-${index}`} className="example-card extreme-weather-card">
                          <div className="query-location">{query.location}</div>
                          <div className="analysis-type">
                            <span className="analysis-badge climate-variable">
                              {query.variable}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Navigate to region"
                            >
                              Go
                            </button>
                          </div>
                          <div className="extreme-weather-question">
                            <span className="query-label">2. Analyze:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Run climate analysis' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Building Damage Tab Content */}
                {activeTab === 'building-damage' && (
                  <div className="building-damage-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Structural damage assessment from authorized high-resolution MPC Pro tenant imagery. Best for post-event review of wildfires, floods, and storms.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Setup</strong> query to load aerial imagery on the map.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Select the <strong>Building Damage</strong> module, drop a pin on the area of interest, then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Assess</strong> query or type your own.
                      </p>
                    </div>
                    <div className="building-damage-queries-grid">
                      {buildingDamageQueries.map((query, index) => (
                        <div key={`building-damage-${index}`} className="example-card building-damage-card">
                          <div className="query-location">{query.location}</div>
                          <div className="analysis-type">
                            <span className={`analysis-badge ${query.analysisType.toLowerCase().replace(/\s+/g, '-')}`}>
                              {query.analysisType}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery, 'pro')}
                              title="Load aerial imagery"
                            >
                              Go
                            </button>
                          </div>
                          <div className="building-damage-question">
                            <span className="query-label">2. Assess:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Run damage assessment' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Site Intel Tab Content */}
                {activeTab === 'site-audit' && (
                  <div className="site-audit-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Scores candidate sites for projects like data centers, solar farms, and substations against power, water, hazards, and permitting precedent.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Setup</strong> query to move the map to the candidate region.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Select the <strong>Site Intel</strong> module, drop a pin on the candidate parcel, then click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on the <strong>Audit</strong> query or type your own.
                      </p>
                    </div>
                    <div className="extreme-weather-queries-grid">
                      {siteAuditQueries.map((query, index) => (
                        <div key={`site-audit-${index}`} className="example-card extreme-weather-card">
                          <div className="query-location">{query.location}</div>
                          <div className="analysis-type">
                            <span className="analysis-badge climate-variable">
                              {query.focus}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Navigate to candidate region"
                            >
                              Go
                            </button>
                          </div>
                          <div className="extreme-weather-question">
                            <span className="query-label">2. Audit:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Run site audit (requires Site Intel module + pin)' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Resilience Tab Content */}
                {activeTab === 'resilience' && (
                  <div className="site-audit-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Watches your facilities and supply chain for weather and hazard risks over the next week, ranks what’s exposed, and suggests what to act on.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Open the <strong>Modules</strong> menu and select <strong>Resilience</strong>. The assessment runs across the Canadian 2026 facility registry for the next 7 days.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on any scenario below, or click a facility marker on the map to drill in.
                      </p>
                    </div>
                    <div className="extreme-weather-queries-grid">
                      {resilienceQueries.map((query, index) => (
                        <div key={`resilience-${index}`} className="example-card extreme-weather-card">
                          <div className="query-location">{query.scenario}</div>
                          <div className="analysis-type">
                            <span className="analysis-badge climate-variable">
                              {query.hazards}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Navigate to region"
                            >
                              Go
                            </button>
                          </div>
                          <div className="extreme-weather-question">
                            <span className="query-label">2. Ask:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleResilienceQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Activate Resilience module and send to chat' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Forecast Tab Content */}
                {activeTab === 'forecast' && (
                  <div className="site-audit-queries-section">
                    <div className="instructions-box" style={{ marginBottom: '20px' }}>
                      <p className="instruction-step">
                        <strong>About:</strong> Short-range AI weather forecasts for any point on the map — temperature, wind, precipitation, and cyclone tracks for the next few days. Runs every provider configured in this deployment and shows where they agree.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 1:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on a location below to recenter the map.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 2:</strong> Open the <strong>Modules</strong> menu and select <strong>Forecast</strong>, then drop a pin where you want the forecast.
                      </p>
                      <p className="instruction-step">
                        <strong>Step 3:</strong> Click <button className="copy-query-btn" style={{cursor: 'default', pointerEvents: 'none'}}>Go</button> on a question, or type your own.
                      </p>
                    </div>
                    <div className="extreme-weather-queries-grid">
                      {forecastQueries.map((query, index) => (
                        <div key={`forecast-${index}`} className="example-card extreme-weather-card">
                          <div className="query-location">{query.scenario}</div>
                          <div className="analysis-type">
                            <span className="analysis-badge climate-variable">
                              {query.models}
                            </span>
                          </div>
                          <div className="setup-query">
                            <span className="query-label">1. Setup:</span>
                            <strong>{query.setupQuery}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleStacQueryClick(query.setupQuery)}
                              title="Recenter map"
                            >
                              Go
                            </button>
                          </div>
                          <div className="extreme-weather-question">
                            <span className="query-label">2. Ask:</span>
                            <strong>{query.question}</strong>
                            <button
                              className="copy-query-btn"
                              onClick={() => handleVisionQueryClick(query.question)}
                              title={mapWorkflowReady ? 'Send to chat (requires Forecast module + pin)' : mapRequiredTitle}
                              disabled={!mapWorkflowReady}
                            >
                              Go
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Pro Tip - at bottom, only show when a module is selected */}
                {activeTab !== 'none' && (
                  <div className="zoom-tip" style={{ marginTop: '24px' }}>
                    <span className="zoom-tip-icon"></span>
                    <div className="zoom-tip-content">
                      <strong>Pro Tip:</strong> Some satellite collections (especially MODIS fire data) only display tiles at deeper zoom levels. 
                      Try zooming to <strong>level 10+</strong> and panning around the map to see all available tiles. Gray areas may be clouds, no-data pixels, or tiling artifacts; check the layer legend and scene metadata.
                    </div>
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default GetStartedButton;
