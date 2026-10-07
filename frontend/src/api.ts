import { ForecastResponse, HealthResponse, StationsResponse } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`Failed to fetch system health status (${res.status} ${res.statusText})`);
  }
  return res.json();
}

export async function fetchStations(): Promise<StationsResponse> {
  const res = await fetch(`${API_BASE_URL}/stations`);
  if (!res.ok) {
    throw new Error(`Failed to fetch stations list (${res.status} ${res.statusText})`);
  }
  return res.json();
}

export async function fetchForecast(stationId: string): Promise<ForecastResponse> {
  const res = await fetch(`${API_BASE_URL}/forecast?station_id=${encodeURIComponent(stationId)}`);
  if (!res.ok) {
    let errorDetail = `Forecast request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail && typeof errorJson.detail === 'object' && errorJson.detail.message) {
        errorDetail = errorJson.detail.message;
      } else if (typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Keep default errorDetail
    }
    throw new Error(errorDetail);
  }
  return res.json();
}
