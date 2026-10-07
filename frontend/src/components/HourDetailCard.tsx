import React from 'react';
import { ForecastUnits, HourlyForecastRecord } from '../types';

interface HourDetailCardProps {
  record: HourlyForecastRecord | undefined;
  units: ForecastUnits;
}

export const HourDetailCard: React.FC<HourDetailCardProps> = ({ record, units }) => {
  if (!record) return null;

  // Format timestamp in both UTC and Indian Standard Time (IST, UTC+5:30)
  const utcDate = new Date(record.timestamp_utc);
  const utcFormatted = utcDate.toISOString().replace('T', ' ').substring(0, 16) + ' UTC';

  const istFormatted = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(utcDate) + ' IST';

  return (
    <div className="hour-detail-section">
      <div className="detail-header-row">
        <div className="time-badge-group">
          <span className="lead-tag">T+{record.hour_index} Hours</span>
          <div className="time-chips">
            <span className="chip-time utc" title="Coordinated Universal Time">
              <span className="chip-label">UTC:</span> {utcFormatted}
            </span>
            <span className="chip-time ist" title="Indian Standard Time (UTC+05:30)">
              <span className="chip-label">Local (Delhi):</span> {istFormatted}
            </span>
          </div>
        </div>
        <div className="mode-pill">Synthetic Demo Output</div>
      </div>

      <div className="metrics-grid">
        {/* PM2.5 Card */}
        <div className="metric-card metric-pm">
          <div className="metric-header">
            <span className="metric-icon">🌫️</span>
            <span className="metric-name">PM2.5 Concentration</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-number">{record.pm25.toFixed(1)}</span>
            <span className="metric-unit">{units.pm25}</span>
          </div>
          <div className="metric-footer-note">Mass concentration • Not AQI index</div>
        </div>

        {/* Temperature Card */}
        <div className="metric-card metric-temp">
          <div className="metric-header">
            <span className="metric-icon">🌡️</span>
            <span className="metric-name">Ambient Temperature</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-number">{record.temperature_c.toFixed(1)}</span>
            <span className="metric-unit">{units.temperature}</span>
          </div>
          <div className="metric-footer-note">Coupled surface thermal profile</div>
        </div>

        {/* Wind Speed Card */}
        <div className="metric-card metric-wind">
          <div className="metric-header">
            <span className="metric-icon">💨</span>
            <span className="metric-name">Surface Wind Speed</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-number">{record.wind_speed_ms.toFixed(1)}</span>
            <span className="metric-unit">{units.wind_speed}</span>
          </div>
          <div className="metric-footer-note">Ventilation & horizontal dispersion proxy</div>
        </div>

        {/* PBL Height Card */}
        <div className="metric-card metric-pbl">
          <div className="metric-header">
            <span className="metric-icon">📏</span>
            <span className="metric-name">Planetary Boundary Layer</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-number">{Math.round(record.pbl_height_m)}</span>
            <span className="metric-unit">{units.pbl_height}</span>
          </div>
          <div className="metric-footer-note">Vertical mixing layer (Inversion proxy)</div>
        </div>
      </div>
    </div>
  );
};
