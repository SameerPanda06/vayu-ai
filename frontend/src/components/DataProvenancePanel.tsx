import React, { useState } from 'react';
import { ChevronRightIcon, InfoIcon } from './Icons';

export const DataProvenancePanel: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  const toggleExpanded = () => setIsExpanded((prev) => !prev);

  return (
    <section className="provenance-panel" aria-label="Data provenance and system disclosures">
      <div
        className="provenance-header"
        onClick={toggleExpanded}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleExpanded();
          }
        }}
        tabIndex={0}
        role="button"
        aria-expanded={isExpanded}
      >
        <div className="provenance-title-row">
          <InfoIcon size={18} className="provenance-info-icon" />
          <h2 className="provenance-title">Data Provenance, Architecture & System Specifications</h2>
        </div>
        <button
          type="button"
          className="provenance-toggle-btn"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Collapse provenance panel' : 'Expand provenance panel'}
          onClick={(e) => {
            e.stopPropagation();
            toggleExpanded();
          }}
        >
          <span className="toggle-label">{isExpanded ? 'Collapse' : 'Expand'}</span>
          <span
            className="toggle-chevron"
            style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(-90deg)' }}
          >
            <ChevronRightIcon size={16} />
          </span>
        </button>
      </div>

      {isExpanded && (
        <div className="provenance-body">
          <div className="provenance-grid">
            <div className="provenance-block">
              <h3 className="block-title">Current Generation Methodology</h3>
              <p className="block-text">
                All values in Phase 2 are produced by a deterministic, physics-inspired diurnal model
                (fixed seed <code>26082</code>). Variations emulate characteristic Delhi NCR boundary-layer
                dynamics: nocturnal ground inversions (200–400m PBLH) causing particulate accumulation, and
                afternoon convective mixing (1400–1800m PBLH) facilitating dispersion.
              </p>
            </div>

            <div className="provenance-block">
              <h3 className="block-title">Scientific Validation Scope</h3>
              <p className="block-text">
                This deployment operates strictly as an architectural and contract demonstration. It does
                <strong>not</strong> ingest live CPCB or SAFAR ground monitors, does not execute numerical
                Eulerian chemistry transport, and does not provide certified forecasts for public advisory
                or regulatory enforcement. In future data integrations, the system will never silently substitute
                synthetic data for failed real-data requests.
              </p>
            </div>

            <div className="provenance-block">
              <h3 className="block-title">Units & Parameter Designation</h3>
              <p className="block-text">
                Particulate concentrations are reported strictly as <strong>PM2.5 (µg/m³)</strong> mass
                concentrations and are deliberately not converted into an AQI number. Temperature
                (°C), wind speed (m/s), and boundary layer height (m) represent idealized
                surface-layer atmospheric conditions.
              </p>
            </div>

            <div className="provenance-block">
              <h3 className="block-title">Future Operational Pipeline & Persistence</h3>
              <p className="block-text">
                Subsequent releases will couple gridded IMD/NCMRWF numerical weather inputs with high-resolution
                (1–3 km) WRF-Chem aerosol-radiation feedback modeling and a physics-informed ML layer.
                <strong>PostgreSQL</strong> (with PostGIS extensions) is the designated persistence layer for
                the next data-integration phase (never SQLite).
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
