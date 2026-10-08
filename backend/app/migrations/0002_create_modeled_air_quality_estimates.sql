-- Migration: 0002_create_modeled_air_quality_estimates.sql
-- Description: Add separate table for numerical modeled air quality estimates (Open-Meteo fallback)
-- Provenance: Strictly separated from ground-truth CPCB observations in air_quality_readings

CREATE TABLE IF NOT EXISTS modeled_air_quality_estimates (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(64) NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    valid_time TIMESTAMP WITH TIME ZONE NOT NULL,
    pm2_5 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    co DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    provider VARCHAR(64) NOT NULL DEFAULT 'open-meteo',
    model_name VARCHAR(64),
    retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_modeled_estimate_station_provider_time UNIQUE (station_id, provider, valid_time)
);

-- Index for efficient station + valid_time lookups
CREATE INDEX IF NOT EXISTS ix_modeled_estimates_station_valid_time 
    ON modeled_air_quality_estimates (station_id, valid_time);

CREATE INDEX IF NOT EXISTS ix_modeled_air_quality_estimates_station_id 
    ON modeled_air_quality_estimates (station_id);

CREATE INDEX IF NOT EXISTS ix_modeled_air_quality_estimates_valid_time 
    ON modeled_air_quality_estimates (valid_time);
