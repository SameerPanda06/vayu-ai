import React, { useEffect, useState } from 'react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { ForecastResponse, Station } from '../types';

interface DelhiMapProps {
  stations: Station[];
  selectedStationId: string;
  onSelectStation: (stationId: string) => void;
  forecastCache: Record<string, ForecastResponse | null>;
  selectedHourIndex: number;
}

// PM2.5 concentration color bins (strictly distinct from official AQI categories)
function getPm25Color(value: number | undefined): string {
  if (value === undefined || isNaN(value)) return '#64748b'; // Unavailable / neutral slate
  if (value < 60) return '#14b8a6';   // Teal: < 60 µg/m³
  if (value < 120) return '#0284c7';  // Sky: 60–120 µg/m³
  if (value < 180) return '#f59e0b';  // Amber: 120–180 µg/m³
  return '#e11d48';                   // Rose: > 180 µg/m³
}

// Controller to smoothly pan map when the selected station changes
const MapPanController: React.FC<{ targetStation: Station | undefined }> = ({ targetStation }) => {
  const map = useMap();

  useEffect(() => {
    if (targetStation) {
      map.panTo([targetStation.latitude, targetStation.longitude], {
        animate: true,
        duration: 0.6,
      });
    }
  }, [targetStation, map]);

  return null;
};

export const DelhiMap: React.FC<DelhiMapProps> = ({
  stations,
  selectedStationId,
  onSelectStation,
  forecastCache,
  selectedHourIndex,
}) => {
  const [tileError, setTileError] = useState<boolean>(false);
  const selectedStation = stations.find((s) => s.id === selectedStationId);

  return (
    <div className="map-wrapper" aria-label="Delhi NCR Monitoring Stations Map">
      <div className="map-header-bar">
        <span className="map-title">Delhi NCR Station Network</span>
        <span className="map-subtitle">Click marker or select from menu</span>
      </div>

      <div className="map-canvas-container">
        {tileError && (
          <div className="basemap-error-banner" role="alert">
            <span>Basemap tiles unavailable. Discrete monitoring station coordinates rendered.</span>
          </div>
        )}

        <MapContainer
          center={[28.625, 77.22]}
          zoom={10}
          minZoom={8}
          maxZoom={16}
          scrollWheelZoom={false}
          className="leaflet-map-element"
        >
          {/* Public basemap with attribution (CartoDB Voyager) */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>'
            subdomains="abcd"
            maxZoom={19}
            eventHandlers={{
              tileerror: () => setTileError(true),
            }}
          />

          <MapPanController targetStation={selectedStation} />

          {stations.map((station) => {
            const isSelected = station.id === selectedStationId;
            const forecast = forecastCache[station.id];
            const hourRecord = forecast?.forecast?.[selectedHourIndex];
            const pm25Value = hourRecord?.pm25;
            const markerColor = getPm25Color(pm25Value);

            const pm25Display =
              pm25Value !== undefined
                ? `${pm25Value.toFixed(1)} µg/m³ (synthetic demo)`
                : forecast === null
                ? 'Forecast unavailable'
                : 'Loading demo series...';

            return (
              <CircleMarker
                key={station.id}
                center={[station.latitude, station.longitude]}
                radius={isSelected ? 12 : 8}
                pathOptions={{
                  fillColor: markerColor,
                  color: isSelected ? '#38bdf8' : '#0f172a',
                  weight: isSelected ? 3 : 1.5,
                  opacity: 1,
                  fillOpacity: isSelected ? 1 : 0.85,
                }}
                eventHandlers={{
                  click: () => onSelectStation(station.id),
                }}
              >
                <Tooltip
                  direction="top"
                  offset={[0, -8]}
                  opacity={0.96}
                  className="custom-leaflet-tooltip"
                >
                  <div className="map-tooltip-card">
                    <div className="map-tooltip-title">{station.name}</div>
                    <div className="map-tooltip-meta">
                      {station.city} ({station.state})
                    </div>
                    <div className="map-tooltip-pm">
                      <span className="tooltip-label">PM2.5:</span>{' '}
                      <strong>{pm25Display}</strong>
                    </div>
                    <div className="map-tooltip-hint">
                      {isSelected ? 'Currently Selected' : 'Click to select station'}
                    </div>
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      {/* Discrete PM2.5 Concentration Legend (Strictly marked Not AQI) */}
      <div className="map-legend" aria-label="PM2.5 concentration legend">
        <span className="legend-title">
          PM2.5 Concentration (µg/m³) — Synthetic Demo Scale
        </span>
        <div className="legend-items">
          <div className="legend-item">
            <span
              className="legend-color-dot"
              style={{ background: '#14b8a6' }}
            ></span>
            <span>&lt; 60</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-dot"
              style={{ background: '#0284c7' }}
            ></span>
            <span>60–120</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-dot"
              style={{ background: '#f59e0b' }}
            ></span>
            <span>120–180</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-dot"
              style={{ background: '#e11d48' }}
            ></span>
            <span>&gt; 180</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-dot"
              style={{ background: '#64748b' }}
            ></span>
            <span>Unavailable</span>
          </div>
        </div>
        <div className="legend-disclaimer">
          Not CPCB AQI categories · Discrete station points only
        </div>
      </div>
    </div>
  );
};
