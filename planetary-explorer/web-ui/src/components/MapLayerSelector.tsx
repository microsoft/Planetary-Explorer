import { useEffect, useRef, type RefObject } from 'react';
import { Eye, EyeOff, Layers3 } from 'lucide-react';

import './MapLayerSelector.css';

export interface SelectableMapLayer {
  id: string;
  label: string;
  swatch: string;
  visible: boolean;
  opacity: number;
  onVisibilityChange: (visible: boolean) => void;
  onOpacityChange: (opacity: number) => void;
}

interface MapLayerSelectorProps {
  layers: SelectableMapLayer[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fallbackFocusRef?: RefObject<HTMLElement>;
}

export default function MapLayerSelector({
  layers,
  open,
  onOpenChange,
  fallbackFocusRef,
}: MapLayerSelectorProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (layers.length === 0 && open) {
      fallbackFocusRef?.current?.focus();
      onOpenChange(false);
    }
  }, [fallbackFocusRef, layers.length, onOpenChange, open]);

  useEffect(() => {
    if (open) {
      panelRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    }
  }, [open]);

  if (layers.length === 0) return null;

  return (
    <div className="map-layer-selector">
      <button
        ref={triggerRef}
        type="button"
        className={`map-layer-selector__trigger${open ? ' is-open' : ''}`}
        aria-label="Map layers"
        aria-expanded={open}
        aria-controls="map-layer-selector-panel"
        title="Map layers"
        onClick={() => onOpenChange(!open)}
      >
        <Layers3 size={22} />
        <span className="map-layer-selector__count" aria-hidden="true">
          {layers.length}
        </span>
      </button>

      {open && (
        <section
          ref={panelRef}
          id="map-layer-selector-panel"
          className="map-layer-selector__panel"
          role="dialog"
          aria-label="Map layers"
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onOpenChange(false);
              triggerRef.current?.focus();
            }
          }}
        >
          <header className="map-layer-selector__header">
            <span>Layers</span>
            <span className="map-layer-selector__summary">
              {layers.filter((layer) => layer.visible).length}/{layers.length}
            </span>
          </header>

          <div className="map-layer-selector__list">
            {layers.map((layer) => {
              const opacityPercent = Math.round(layer.opacity * 100);
              return (
                <div className="map-layer-selector__row" key={layer.id} data-layer-id={layer.id}>
                  <div className="map-layer-selector__row-header">
                    <span
                      className="map-layer-selector__swatch"
                      style={{ background: layer.swatch }}
                      aria-hidden="true"
                    />
                    <span className="map-layer-selector__label">{layer.label}</span>
                    <button
                      type="button"
                      className="map-layer-selector__visibility"
                      aria-label={`${layer.label} visibility`}
                      aria-pressed={layer.visible}
                      title={`${layer.visible ? 'Hide' : 'Show'} ${layer.label}`}
                      onClick={() => layer.onVisibilityChange(!layer.visible)}
                    >
                      {layer.visible ? <Eye size={17} /> : <EyeOff size={17} />}
                    </button>
                  </div>

                  <div className="map-layer-selector__opacity">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="1"
                      value={opacityPercent}
                      disabled={!layer.visible}
                      aria-label={`${layer.label} opacity`}
                      onChange={(event) => layer.onOpacityChange(Number(event.target.value) / 100)}
                    />
                    <output>{opacityPercent}%</output>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}