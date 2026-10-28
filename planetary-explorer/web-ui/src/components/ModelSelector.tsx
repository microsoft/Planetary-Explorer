// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.

import React, { useState, useEffect, useRef } from 'react';
import './ModelSelector.css';
import { authenticatedFetch } from '../services/authHelper';

interface ModelOption {
  id: string;
  name: string;
  isDefault?: boolean;
  isAvailable?: boolean;
}

interface ModelSelectorProps {
  onModelChange?: (modelId: string) => void;
  selectedModel?: string;
  apiBaseUrl?: string;
}

const DEFAULT_MODELS: ModelOption[] = [
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4o mini (fast)',
    isDefault: true,
    isAvailable: true
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    isAvailable: true
  },
  {
    id: 'gpt-5',
    name: 'GPT-5 (deep reasoning)',
    isAvailable: true
  }
];

const ModelSelector: React.FC<ModelSelectorProps> = ({ onModelChange, selectedModel, apiBaseUrl = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelOption[]>(DEFAULT_MODELS);
  const [currentModel, setCurrentModel] = useState<string>(
    selectedModel || DEFAULT_MODELS.find(m => m.isDefault)?.id || 'gpt-5'
  );
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch the real list of deployed models from the backend, which
  // discovers them live via Azure's ARM management API (see
  // GET /api/models in fastapi_app.py). This replaces guessing model
  // availability from the overall /api/health status -- any deployment
  // actually present in the tenant (gpt-5, a future gpt-5.5, a custom
  // fine-tune, etc.) shows up automatically with no code changes needed.
  // Falls back to the static DEFAULT_MODELS list if the call fails, so
  // the dropdown is never empty.
  useEffect(() => {
    const fetchAvailableModels = async () => {
      try {
        const response = await authenticatedFetch(`${apiBaseUrl}/api/models`);
        const data = await response.json();
        if (Array.isArray(data.models) && data.models.length > 0) {
          setModels(data.models);
        }
      } catch (err) {
        console.error('Failed to fetch available models, keeping fallback list:', err);
      }
    };

    fetchAvailableModels();
    // Refresh every 5 minutes -- deployment lists rarely change, and the
    // backend itself caches the ARM call for the same window.
    const interval = setInterval(fetchAvailableModels, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Store model preference in localStorage
  useEffect(() => {
    localStorage.setItem('planetaryexplorer-model', currentModel);
  }, [currentModel]);

  // Load model preference from localStorage on mount
  useEffect(() => {
    const savedModel = localStorage.getItem('planetaryexplorer-model');
    if (savedModel && models.find(m => m.id === savedModel)) {
      setCurrentModel(savedModel);
      onModelChange?.(savedModel);
    }
  }, []);

  const handleModelSelect = (modelId: string) => {
    const model = models.find(m => m.id === modelId);
    // Only allow selecting available models
    if (model?.isAvailable) {
      setCurrentModel(modelId);
      setIsOpen(false);
      onModelChange?.(modelId);
    }
  };

  const currentModelInfo = models.find(m => m.id === currentModel);

  return (
    <div className="model-selector" ref={dropdownRef}>
      <div 
        className="model-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        title="Deployed model status"
      >
        <span className="model-selector-label">Models</span>
      </div>
      
      {isOpen && (
        <div className="model-dropdown">
          <ul className="model-list" role="listbox">
            {models.map((model) => (
              <li
                key={model.id}
                className={`model-option ${currentModel === model.id ? 'selected' : ''} ${!model.isAvailable ? 'unavailable' : ''}`}
                onClick={() => handleModelSelect(model.id)}
                role="option"
                aria-selected={currentModel === model.id}
                aria-disabled={!model.isAvailable}
                style={{ opacity: model.isAvailable ? 1 : 0.5 }}
              >
                <span className="model-option-name">{model.name}</span>
                <span 
                  className="model-availability-dot"
                  style={{ 
                    backgroundColor: model.isAvailable ? '#4CAF50' : '#F44336',
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    marginLeft: '8px',
                    display: 'inline-block'
                  }}
                  title={model.isAvailable ? 'Available' : 'Not Deployed'}
                />
                {currentModel === model.id && <span className="check-mark">✓</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ModelSelector;
