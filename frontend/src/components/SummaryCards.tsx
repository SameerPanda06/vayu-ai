import React from 'react';
import { ForecastUnits, HourlyForecastRecord } from '../types';
import { PblHeightIcon, Pm25Icon, TempIcon, WindSpeedIcon } from './Icons';

interface SummaryCardsProps {
  record: HourlyForecastRecord | undefined;
  units: ForecastUnits | undefined;
  isLoading: boolean;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({
  record,
  units,
  isLoading,
}) => {
  const pm25Unit = units?.pm25 || 'µg/m³';
  const tempUnit = units?.temperature || '°C';
  const windUnit = units?.wind_speed || 'm/s';
  const pblUnit = units?.pbl_height || 'm';

  const pm25Value = record?.pm25 !== undefined ? record.pm25.toFixed(1) : '—';
  const tempValue = record?.temperature_c !== undefined ? record.temperature_c.toFixed(1) : '—';
  const windValue = record?.wind_speed_ms !== undefined ? record.wind_speed_ms.toFixed(1) : '—';
  const pblValue = record?.pbl_height_m !== undefined ? Math.round(record.pbl_height_m).toString() : '—';

  return (
    <section className="summary-cards-section" aria-label="Atmospheric conditions summary">
      <div className="summary-grid">
        {/* PM2.5 Concentration Card */}
        <div className={`summary-card card-pm25 ${isLoading ? 'card-loading' : ''}`}>
          <div className="card-top">
            <span className="card-icon-wrap icon-pm25">
              <Pm25Icon size={18} />
            </span>
            <span className="card-param-title">PM2.5 Concentration</span>
          </div>
          <div className="card-value-row">
            <span className="card-value">{pm25Value}</span>
            <span className="card-unit">{pm25Unit}</span>
          </div>
          <div className="card-caption">Mass concentration · Not AQI index</div>
        </div>

        {/* Ambient Temperature Card */}
        <div className={`summary-card card-temp ${isLoading ? 'card-loading' : ''}`}>
          <div className="card-top">
            <span className="card-icon-wrap icon-temp">
              <TempIcon size={18} />
            </span>
            <span className="card-param-title">Ambient Temperature</span>
          </div>
          <div className="card-value-row">
            <span className="card-value">{tempValue}</span>
            <span className="card-unit">{tempUnit}</span>
          </div>
          <div className="card-caption">Synthetic temperature</div>
        </div>

        {/* Surface Wind Speed Card */}
        <div className={`summary-card card-wind ${isLoading ? 'card-loading' : ''}`}>
          <div className="card-top">
            <span className="card-icon-wrap icon-wind">
              <WindSpeedIcon size={18} />
            </span>
            <span className="card-param-title">Surface Wind Speed</span>
          </div>
          <div className="card-value-row">
            <span className="card-value">{windValue}</span>
            <span className="card-unit">{windUnit}</span>
          </div>
          <div className="card-caption">Synthetic wind speed</div>
        </div>

        {/* Boundary Layer Height Card */}
        <div className={`summary-card card-pbl ${isLoading ? 'card-loading' : ''}`}>
          <div className="card-top">
            <span className="card-icon-wrap icon-pbl">
              <PblHeightIcon size={18} />
            </span>
            <span className="card-param-title">Boundary Layer Height</span>
          </div>
          <div className="card-value-row">
            <span className="card-value">{pblValue}</span>
            <span className="card-unit">{pblUnit}</span>
          </div>
          <div className="card-caption">Synthetic PBL height</div>
        </div>
      </div>
    </section>
  );
};
