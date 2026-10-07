import React from 'react';
import { HealthResponse } from '../types';
import { WindLogoIcon } from './Icons';

interface HeaderProps {
  health: HealthResponse | null;
  healthError: boolean;
}

export const Header: React.FC<HeaderProps> = ({ health, healthError }) => {
  return (
    <header className="app-header">
      <div className="header-container">
        <div className="brand-group">
          <div className="brand-icon-wrap" aria-hidden="true">
            <WindLogoIcon size={24} className="brand-svg" />
          </div>
          <div className="brand-info">
            <div className="brand-row">
              <span className="brand-name">Vayu AI</span>
              <span className="data-mode-badge">Demo Mode · Synthetic</span>
            </div>
            <span className="brand-sub">Delhi NCR Air-Quality Exploration</span>
          </div>
        </div>

        <div className="header-actions">
          <div
            className={`status-pill ${healthError ? 'status-pill-error' : health ? 'status-pill-ok' : 'status-pill-pending'}`}
            title={health ? `API v${health.version} - Status: ${health.status}` : 'Checking backend connectivity...'}
          >
            <span className="status-dot"></span>
            <span className="status-pill-label">
              {healthError ? 'API Disconnected' : health ? `Backend v${health.version}` : 'Connecting...'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
