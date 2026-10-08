from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Station(Base):
    """
    Monitoring station entity for Delhi NCR air quality observation locations.
    """
    __tablename__ = "stations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True,
        comment="Unique station slug identifier (e.g., 'anand-vihar')",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Display name of the monitoring station",
    )
    city: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Delhi NCR",
        comment="City or urban jurisdiction",
    )
    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Delhi",
        comment="State or National Capital Territory",
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Geographic latitude in decimal degrees",
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Geographic longitude in decimal degrees",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp in UTC",
    )

    # Relationships
    readings: Mapped[List["AirQualityReading"]] = relationship(
        "AirQualityReading",
        back_populates="station",
        cascade="all, delete-orphan",
        order_by="desc(AirQualityReading.timestamp)",
    )
    forecasts: Mapped[List["Forecast"]] = relationship(
        "Forecast",
        back_populates="station",
        cascade="all, delete-orphan",
        order_by="desc(Forecast.forecast_time)",
    )
    modeled_estimates: Mapped[List["ModeledAirQualityEstimate"]] = relationship(
        "ModeledAirQualityEstimate",
        back_populates="station",
        cascade="all, delete-orphan",
        order_by="desc(ModeledAirQualityEstimate.valid_time)",
    )

    def __repr__(self) -> str:
        return f"<Station(id='{self.id}', name='{self.name}', city='{self.city}')>"


class AirQualityReading(Base):
    """
    Historical and continuous monitoring observations from ground stations.
    """
    __tablename__ = "air_quality_readings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    station_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated monitoring station ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Observation valid timestamp in UTC",
    )
    aqi: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Calculated Air Quality Index (if official/derived)",
    )
    pm2_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="PM2.5 particulate mass concentration in µg/m³",
    )
    pm10: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="PM10 particulate mass concentration in µg/m³",
    )
    no2: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Nitrogen Dioxide concentration in µg/m³",
    )
    so2: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Sulfur Dioxide concentration in µg/m³",
    )
    co: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Carbon Monoxide concentration in mg/m³",
    )
    o3: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Ozone concentration in µg/m³",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record insertion timestamp in UTC",
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="readings",
    )

    __table_args__ = (
        UniqueConstraint("station_id", "timestamp", name="uq_station_reading_timestamp"),
        Index("ix_readings_station_timestamp", "station_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AirQualityReading(station_id='{self.station_id}', timestamp='{self.timestamp}', pm2_5={self.pm2_5})>"


class Forecast(Base):
    """
    Model and ML-predicted atmospheric and air quality forecast steps.
    """
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    station_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target station identifier",
    )
    forecast_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Valid forecast step timestamp in UTC",
    )
    predicted_aqi: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Predicted composite AQI value",
    )
    predicted_pm2_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Predicted PM2.5 mass concentration in µg/m³",
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Model or pipeline version tag (e.g. 'vayu-v0.1-emulator')",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Forecast generation timestamp in UTC",
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="forecasts",
    )

    __table_args__ = (
        Index("ix_forecasts_station_forecast_time", "station_id", "forecast_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<Forecast(station_id='{self.station_id}', forecast_time='{self.forecast_time}', "
            f"predicted_pm2_5={self.predicted_pm2_5}, model_version='{self.model_version}')>"
        )


class ModeledAirQualityEstimate(Base):
    """
    Modeled and reanalysis atmospheric chemistry estimates (e.g. Open-Meteo).
    Maintained strictly separate from ground station observations and official forecasts.
    """
    __tablename__ = "modeled_air_quality_estimates"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    station_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated monitoring station ID",
    )
    valid_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Model valid step timestamp in UTC",
    )
    pm2_5: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated PM2.5 particulate mass concentration in µg/m³",
    )
    pm10: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated PM10 particulate mass concentration in µg/m³",
    )
    no2: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated Nitrogen Dioxide concentration in µg/m³",
    )
    so2: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated Sulfur Dioxide concentration in µg/m³",
    )
    co: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated Carbon Monoxide concentration in mg/m³",
    )
    o3: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated Ozone concentration in µg/m³",
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="open-meteo",
        comment="Model data provider / upstream source identifier",
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Underlying atmospheric model name (e.g., 'cams_europe')",
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record retrieval timestamp in UTC",
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="modeled_estimates",
    )

    __table_args__ = (
        UniqueConstraint(
            "station_id", "provider", "valid_time",
            name="uq_modeled_estimate_station_provider_time",
        ),
        Index("ix_modeled_estimates_station_valid_time", "station_id", "valid_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<ModeledAirQualityEstimate(station_id='{self.station_id}', "
            f"provider='{self.provider}', valid_time='{self.valid_time}', pm2_5={self.pm2_5})>"
        )

