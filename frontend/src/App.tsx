import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchForecast, fetchHealth, fetchStations } from './api';
import { ForecastResponse, HealthResponse, Station } from './types';
import { Header } from './components/Header';
import { NoticeBanner } from './components/NoticeBanner';
import { LocationTimeBar } from './components/LocationTimeBar';
import { SummaryCards } from './components/SummaryCards';
import { DelhiMap } from './components/DelhiMap';
import { StationDetailPanel } from './components/StationDetailPanel';
import { ForecastChart } from './components/ForecastChart';
import { DataProvenancePanel } from './components/DataProvenancePanel';
import { StatusView } from './components/StatusView';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<boolean>(false);

  const [stations, setStations] = useState<Station[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string>('');
  
  // Session cache: stationId -> ForecastResponse | null (null means failed)
  const [forecastCache, setForecastCache] = useState<Record<string, ForecastResponse | null>>({});
  
  // Shared single forecast hour index (0 to 71)
  const [selectedHourIndex, setSelectedHourIndex] = useState<number>(0);

  const [isLoadingStations, setIsLoadingStations] = useState<boolean>(true);
  const [isFetchingSelected, setIsFetchingSelected] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Keep ref of latest selected station to prevent race conditions / stale updates
  const activeStationIdRef = useRef<string>('');
  activeStationIdRef.current = selectedStationId;

  // 1. Initial health and station catalog load
  const loadInitialData = useCallback(async () => {
    setIsLoadingStations(true);
    setErrorMessage(null);

    // Health check
    try {
      const healthRes = await fetchHealth();
      setHealth(healthRes);
      setHealthError(false);
    } catch {
      setHealthError(true);
    }

    // Stations load
    try {
      const stationsRes = await fetchStations();
      const loadedStations = stationsRes.stations;
      setStations(loadedStations);

      if (loadedStations.length > 0) {
        const firstStationId = loadedStations[0].id;
        setSelectedStationId(firstStationId);
        activeStationIdRef.current = firstStationId;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve stations directory';
      setErrorMessage(msg);
    } finally {
      setIsLoadingStations(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Fetch forecast for a single station with caching & race-condition prevention
  const fetchStationForecast = useCallback(
    async (stationId: string, isCurrentSelection: boolean = false) => {
      // Check cache first
      if (forecastCache[stationId] !== undefined) {
        return forecastCache[stationId];
      }

      if (isCurrentSelection) {
        setIsFetchingSelected(true);
      }

      try {
        const data = await fetchForecast(stationId);
        setForecastCache((prev) => ({ ...prev, [stationId]: data }));
        return data;
      } catch (err) {
        // Mark as null in cache to indicate failure for this session
        setForecastCache((prev) => ({ ...prev, [stationId]: null }));
        if (isCurrentSelection && activeStationIdRef.current === stationId) {
          const msg = err instanceof Error ? err.message : 'Failed to retrieve station forecast';
          setErrorMessage(msg);
        }
        return null;
      } finally {
        if (isCurrentSelection && activeStationIdRef.current === stationId) {
          setIsFetchingSelected(false);
        }
      }
    },
    [forecastCache],
  );

  // 2. Fetch or retrieve from cache whenever selectedStationId changes
  useEffect(() => {
    if (!selectedStationId) return;

    if (forecastCache[selectedStationId] === undefined) {
      fetchStationForecast(selectedStationId, true);
    }
  }, [selectedStationId, forecastCache, fetchStationForecast]);

  // 3. Background pre-fetch remaining stations for map tooltips (non-blocking)
  useEffect(() => {
    if (!stations.length) return;

    stations.forEach((st) => {
      if (forecastCache[st.id] === undefined && st.id !== selectedStationId) {
        // Fetch quietly in background
        fetchForecast(st.id)
          .then((data) => {
            setForecastCache((prev) => (prev[st.id] ? prev : { ...prev, [st.id]: data }));
          })
          .catch(() => {
            setForecastCache((prev) => (prev[st.id] !== undefined ? prev : { ...prev, [st.id]: null }));
          });
      }
    });
  }, [stations, selectedStationId, forecastCache]);

  const handleStationChange = (newStationId: string) => {
    setErrorMessage(null);
    setSelectedStationId(newStationId);
  };

  const handleHourSelect = (hourIndex: number) => {
    setSelectedHourIndex(Math.max(0, Math.min(71, hourIndex)));
  };

  const handlePrevHour = () => {
    setSelectedHourIndex((prev) => Math.max(0, prev - 1));
  };

  const handleNextHour = () => {
    setSelectedHourIndex((prev) => Math.min(71, prev + 1));
  };

  const selectedStation = stations.find((s) => s.id === selectedStationId);
  const selectedForecast = forecastCache[selectedStationId];
  const selectedHourRecord = selectedForecast?.forecast?.[selectedHourIndex];

  return (
    <div className="app-root">
      <Header health={health} healthError={healthError} />
      <NoticeBanner />

      <main className="main-container">
        {isLoadingStations ? (
          <StatusView
            type="loading"
            title="Initializing Vayu AI System"
            message="Discovering Delhi NCR air quality monitoring network..."
          />
        ) : errorMessage && !selectedForecast ? (
          <StatusView
            type="error"
            title="Service Communication Error"
            message={errorMessage}
            onRetry={() => {
              if (!stations.length) {
                loadInitialData();
              } else if (selectedStationId) {
                fetchStationForecast(selectedStationId, true);
              }
            }}
          />
        ) : (
          <>
            {/* Step 2: Selected location and selected forecast timestamp */}
            <LocationTimeBar
              stations={stations}
              selectedStationId={selectedStationId}
              onSelectStation={handleStationChange}
              selectedStation={selectedStation}
              selectedHourIndex={selectedHourIndex}
              totalHours={selectedForecast?.forecast_hours || 72}
              validTimestampUtc={selectedHourRecord?.timestamp_utc}
              onPrevHour={handlePrevHour}
              onNextHour={handleNextHour}
              isLoading={isFetchingSelected}
            />

            {/* Step 3: Four summary cards */}
            <SummaryCards
              record={selectedHourRecord}
              units={selectedForecast?.units}
              isLoading={isFetchingSelected}
            />

            {/* Step 4: Main content: Map on left, Selected-location details on right */}
            <div className="main-content-split">
              <div className="split-left">
                <DelhiMap
                  stations={stations}
                  selectedStationId={selectedStationId}
                  onSelectStation={handleStationChange}
                  forecastCache={forecastCache}
                  selectedHourIndex={selectedHourIndex}
                />
              </div>

              <div className="split-right">
                <StationDetailPanel
                  station={selectedStation}
                  forecast={selectedForecast}
                  selectedHourRecord={selectedHourRecord}
                  selectedHourIndex={selectedHourIndex}
                  isLoading={isFetchingSelected}
                  onRetryForecast={() => fetchStationForecast(selectedStationId, true)}
                />
              </div>
            </div>

            {/* Step 5: Shared time slider and 72-hour PM2.5 chart */}
            <ForecastChart
              forecast={selectedForecast?.forecast || []}
              selectedHourIndex={selectedHourIndex}
              onSelectHour={handleHourSelect}
              units={selectedForecast?.units?.pm25 || 'µg/m³'}
              onPrevHour={handlePrevHour}
              onNextHour={handleNextHour}
              isLoading={isFetchingSelected}
            />

            {/* Step 6: Concise data provenance panel */}
            <DataProvenancePanel />
          </>
        )}
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <div className="footer-left">
            <span>Vayu AI · Delhi NCR Air-Quality Exploration · SIH26082</span>
          </div>
          <div className="footer-right">
            <span>Demo Mode: Synthetic series</span>
            <span>Horizon: 72 Hourly Steps (T+0h to T+71h)</span>
            <span>Timezone: IST (UTC+05:30)</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
