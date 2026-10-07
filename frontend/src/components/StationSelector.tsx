import React from 'react';
import { Station } from '../types';

interface StationSelectorProps {
  stations: Station[];
  selectedStationId: string;
  onSelectStation: (stationId: string) => void;
  isLoading: boolean;
}

export const StationSelector: React.FC<StationSelectorProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
  isLoading,
}) => {
  const currentStation = stations.find((s) => s.id === selectedStationId);

  return (
    <div className="station-selector-card">
      <div className="selector-header">
        <label htmlFor="station-select" className="selector-label">
          Monitoring Location
        </label>
        <div className="station-count-tag">
          {stations.length} Delhi NCR Stations Available
        </div>
      </div>

      <div className="selector-control-row">
        <div className="select-wrapper">
          <select
            id="station-select"
            className="station-dropdown"
            value={selectedStationId}
            onChange={(e) => onSelectStation(e.target.value)}
            disabled={isLoading || stations.length === 0}
          >
            {stations.map((st) => (
              <option key={st.id} value={st.id}>
                {st.name} — {st.city} ({st.state})
              </option>
            ))}
          </select>
        </div>

        {currentStation && (
          <div className="station-coords-chip">
            <span className="coords-icon">📍</span>
            <span>{currentStation.latitude.toFixed(4)}°N, {currentStation.longitude.toFixed(4)}°E</span>
            {currentStation.elevation_m !== null && (
              <span className="elevation-text">({currentStation.elevation_m}m asl)</span>
            )}
          </div>
        )}
      </div>

      {currentStation && (
        <p className="station-description">
          <span className="desc-label">Station Profile:</span> {currentStation.description}
        </p>
      )}
    </div>
  );
};
