import React from 'react';
import { ForecastResponse, HourlyForecastRecord, Station } from '../types';
import { ClockIcon, InfoIcon, PinIcon } from './Icons';

interface StationDetailPanelProps {
  station: Station | undefined;
  forecast: ForecastResponse | null | undefined;
  selectedHourRecord: HourlyForecastRecord | undefined;
  selectedHourIndex: number;
  isLoading: boolean;
  onRetryForecast?: () => void;
}

export const StationDetailPanel: React.FC<StationDetailPanelProps> = ({
  station,
  forecast,
  selectedHourRecord,
  selectedHourIndex,
  isLoading,
  onRetryForecast,
}) => {
  if (!station) {
    return (
      <div className="detail-panel empty-detail-panel">
        <p>Select a monitoring station from the map or menu to inspect localized conditions.</p>
      </div>
    );
  }

  // Formatting timestamps
  let istFormatted = '—';
  let utcFormatted = '—';
  if (selectedHourRecord?.timestamp_utc) {
    try {
      const d = new Date(selectedHourRecord.timestamp_utc);
      istFormatted = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }).format(d) + ' IST';
      utcFormatted = d.toISOString().replace('T', ' ').substring(0, 16) + ' UTC';
    } catch {
      istFormatted = '—';
      utcFormatted = '—';
    }
  }

  const isUnavailable = forecast === null && !isLoading;

  return (
    <aside className="detail-panel" aria-label="Selected location details">
      <div className="panel-header">
        <div className="panel-station-title-row">
          <PinIcon size={18} className="panel-pin-icon" />
          <h2 className="panel-station-title">{station.name}</h2>
        </div>
        <span className="panel-badge-station">{station.city} · {station.state}</span>
      </div>

      <div className="panel-meta-bar">
        <span className="panel-coords">
          {station.latitude.toFixed(4)}°N, {station.longitude.toFixed(4)}°E
        </span>
        {station.elevation_m !== null && (
          <span className="panel-elevation">Elevation: {station.elevation_m}m MSL</span>
        )}
      </div>

      <div className="panel-section">
        <h3 className="panel-subheading">Station Characteristics</h3>
        <p className="panel-description">{station.description}</p>
      </div>

      <div className="panel-section">
        <div className="panel-lead-header">
          <h3 className="panel-subheading">Selected Hour Parameters</h3>
          <span className="panel-hour-tag">Step T+{selectedHourIndex}h</span>
        </div>

        {isUnavailable ? (
          <div className="panel-unavailable-box" role="status">
            <InfoIcon size={16} />
            <p>Forecast data currently unavailable for this station.</p>
            {onRetryForecast && (
              <button type="button" className="panel-retry-btn" onClick={onRetryForecast}>
                Retry Loading
              </button>
            )}
          </div>
        ) : isLoading ? (
          <div className="panel-loading-box">
            <span className="panel-spinner"></span>
            <span>Retrieving station forecast series...</span>
          </div>
        ) : (
          <div className="panel-table-wrap">
            <table className="param-table">
              <tbody>
                <tr>
                  <td className="param-name">Local Valid Time (IST)</td>
                  <td className="param-val">{istFormatted}</td>
                </tr>
                <tr>
                  <td className="param-name">Valid Time (UTC)</td>
                  <td className="param-val">{utcFormatted}</td>
                </tr>
                <tr>
                  <td className="param-name">PM2.5 Concentration</td>
                  <td className="param-val highlight-val">
                    {selectedHourRecord?.pm25 !== undefined ? `${selectedHourRecord.pm25.toFixed(1)} µg/m³` : '—'}
                  </td>
                </tr>
                <tr>
                  <td className="param-name">Ambient Temperature</td>
                  <td className="param-val">
                    {selectedHourRecord?.temperature_c !== undefined ? `${selectedHourRecord.temperature_c.toFixed(1)} °C` : '—'}
                  </td>
                </tr>
                <tr>
                  <td className="param-name">Surface Wind Speed</td>
                  <td className="param-val">
                    {selectedHourRecord?.wind_speed_ms !== undefined ? `${selectedHourRecord.wind_speed_ms.toFixed(1)} m/s` : '—'}
                  </td>
                </tr>
                <tr>
                  <td className="param-name">Boundary Layer Height</td>
                  <td className="param-val">
                    {selectedHourRecord?.pbl_height_m !== undefined ? `${Math.round(selectedHourRecord.pbl_height_m)} m` : '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel-footer-note">
        <ClockIcon size={14} className="panel-footer-icon" />
        <span>Values are deterministic synthetic demo outputs · 72-hour forecast horizon</span>
      </div>
    </aside>
  );
};
