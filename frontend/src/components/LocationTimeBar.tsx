import React from 'react';
import { Station } from '../types';
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon, PinIcon } from './Icons';

interface LocationTimeBarProps {
  stations: Station[];
  selectedStationId: string;
  onSelectStation: (stationId: string) => void;
  selectedStation: Station | undefined;
  selectedHourIndex: number;
  totalHours: number;
  validTimestampUtc: string | undefined;
  onPrevHour: () => void;
  onNextHour: () => void;
  isLoading: boolean;
}

export const LocationTimeBar: React.FC<LocationTimeBarProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
  selectedStation,
  selectedHourIndex,
  totalHours,
  validTimestampUtc,
  onPrevHour,
  onNextHour,
  isLoading,
}) => {
  // Format IST and UTC timestamps
  let istFormatted = '—';
  let utcFormatted = '—';

  if (validTimestampUtc) {
    try {
      const date = new Date(validTimestampUtc);
      istFormatted = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }).format(date) + ' IST';

      utcFormatted = date.toISOString().replace('T', ' ').substring(0, 16) + ' UTC';
    } catch {
      istFormatted = 'Invalid Timestamp';
      utcFormatted = 'Invalid Timestamp';
    }
  }

  return (
    <div className="location-time-bar">
      <div className="location-select-wrap">
        <label htmlFor="station-dropdown" className="bar-label">
          <PinIcon size={16} className="bar-label-icon" />
          <span>Monitoring Location</span>
        </label>
        <div className="select-container">
          <select
            id="station-dropdown"
            className="station-select"
            value={selectedStationId}
            onChange={(e) => onSelectStation(e.target.value)}
            disabled={isLoading || stations.length === 0}
            aria-label="Select Delhi NCR monitoring station"
          >
            {stations.map((st) => (
              <option key={st.id} value={st.id}>
                {st.name}, {st.city} ({st.state})
              </option>
            ))}
          </select>
          {selectedStation && (
            <span className="station-coord-tag">
              {selectedStation.latitude.toFixed(4)}°N, {selectedStation.longitude.toFixed(4)}°E
            </span>
          )}
        </div>
      </div>

      <div className="time-control-wrap">
        <div className="time-label-row">
          <ClockIcon size={16} className="bar-label-icon" />
          <span className="bar-label">Forecast Valid Time (IST)</span>
          <span className="lead-step-badge">T+{selectedHourIndex}h</span>
        </div>

        <div className="time-stepper-row">
          <button
            type="button"
            className="time-step-btn"
            onClick={onPrevHour}
            disabled={selectedHourIndex <= 0}
            aria-label="Previous forecast hour"
            title="Step back 1 hour"
          >
            <ChevronLeftIcon size={16} />
          </button>

          <div className="time-display-box" title={`UTC: ${utcFormatted}`}>
            <span className="time-ist-text">{istFormatted}</span>
            <span className="time-utc-sub">({utcFormatted})</span>
          </div>

          <button
            type="button"
            className="time-step-btn"
            onClick={onNextHour}
            disabled={selectedHourIndex >= totalHours - 1}
            aria-label="Next forecast hour"
            title="Step forward 1 hour"
          >
            <ChevronRightIcon size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};
