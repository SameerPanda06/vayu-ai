import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Documented atmospheric pollutant variables requested from Open-Meteo
HOURLY_VARIABLES: List[str] = [
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "carbon_monoxide",
    "ozone",
]


class OpenMeteoError(Exception):
    """Base exception for Open-Meteo API integration failures."""
    pass


class OpenMeteoNetworkError(OpenMeteoError):
    """Raised on network connection errors reaching Open-Meteo."""
    pass


class OpenMeteoTimeoutError(OpenMeteoError):
    """Raised when an Open-Meteo HTTP request times out."""
    pass


class OpenMeteoResponseError(OpenMeteoError):
    """Raised on non-200 HTTP responses, malformed JSON, or unexpected payload shapes."""
    pass


class OpenMeteoClient:
    """
    HTTP client for querying Open-Meteo Air Quality API
    (https://air-quality-api.open-meteo.com/v1/air-quality)
    as a non-commercial, zero-cost development fallback for Delhi NCR stations.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        past_hours: Optional[int] = None,
        forecast_hours: Optional[int] = None,
        timezone: str = "UTC",
    ):
        self.base_url = (base_url or settings.open_meteo_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.open_meteo_timeout_seconds
        self.past_hours = past_hours if past_hours is not None else settings.open_meteo_past_hours
        self.forecast_hours = forecast_hours if forecast_hours is not None else settings.open_meteo_forecast_hours
        self.timezone = timezone

    def fetch_air_quality(
        self,
        latitude: float,
        longitude: float,
        past_hours: Optional[int] = None,
        forecast_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Fetch modeled hourly air quality estimates for given geographic coordinates.

        Returns raw decoded JSON response dictionary.
        Raises OpenMeteoTimeoutError, OpenMeteoNetworkError, or OpenMeteoResponseError on failure.
        """
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            raise ValueError(f"Invalid coordinates: latitude={latitude}, longitude={longitude}")

        req_past = past_hours if past_hours is not None else self.past_hours
        req_forecast = forecast_hours if forecast_hours is not None else self.forecast_hours

        params: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": self.timezone,
            "past_hours": req_past,
            "forecast_hours": req_forecast,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)

                if response.status_code != 200:
                    raise OpenMeteoResponseError(
                        f"Open-Meteo returned HTTP {response.status_code}: {response.text[:200]}"
                    )

                try:
                    payload = response.json()
                except Exception as exc:
                    raise OpenMeteoResponseError(
                        f"Failed to decode JSON from Open-Meteo: {str(exc)}"
                    ) from exc

                if not isinstance(payload, dict):
                    raise OpenMeteoResponseError(
                        f"Expected JSON object from Open-Meteo, received {type(payload).__name__}"
                    )

                hourly = payload.get("hourly")
                if not isinstance(hourly, dict) or "time" not in hourly:
                    raise OpenMeteoResponseError(
                        "Malformed Open-Meteo response: 'hourly' object or 'time' series missing."
                    )

                return payload

        except httpx.TimeoutException as exc:
            raise OpenMeteoTimeoutError(
                f"Open-Meteo request timed out after {self.timeout}s: {str(exc)}"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise OpenMeteoNetworkError(
                f"Network failure connecting to Open-Meteo: {str(exc)}"
            ) from exc
        except (OpenMeteoError, ValueError):
            raise
        except Exception as exc:
            raise OpenMeteoError(
                f"Unexpected error communicating with Open-Meteo: {str(exc)}"
            ) from exc
