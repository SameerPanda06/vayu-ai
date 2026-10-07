export interface Station {
  id: string;
  name: string;
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  elevation_m: number | null;
  description: string;
}

export interface StationsResponse {
  count: number;
  stations: Station[];
}

export interface ForecastUnits {
  pm25: string;
  temperature: string;
  wind_speed: string;
  pbl_height: string;
}

export interface HourlyForecastRecord {
  hour_index: number;
  timestamp_utc: string;
  pm25: number;
  temperature_c: number;
  wind_speed_ms: number;
  pbl_height_m: number;
}

export interface ForecastResponse {
  data_mode: 'synthetic_demo';
  statement: string;
  generated_at: string;
  units: ForecastUnits;
  station: Station;
  forecast_hours: number;
  forecast: HourlyForecastRecord[];
}

export interface HealthResponse {
  status: string;
  version: string;
  app_name: string;
  phase: string;
  timestamp_utc: string;
}
