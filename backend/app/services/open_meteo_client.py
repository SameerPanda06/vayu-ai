from datetime import date, datetime, timedelta
import logging
import time
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


class OpenMeteoRateLimitError(OpenMeteoError):
    """Raised when Open-Meteo rate limits requests (HTTP 429)."""
    pass


class OpenMeteoResponseError(OpenMeteoError):
    """Raised on non-200 HTTP responses, malformed JSON, or unexpected payload shapes."""
    pass


def parse_date_string(date_str: str) -> date:
    """
    Validate and parse a date string formatted as 'YYYY-MM-DD'.
    Raises ValueError on invalid formats.
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError(f"Date string must be a non-empty string in YYYY-MM-DD format, got: {date_str!r}")
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'.") from exc


class OpenMeteoClient:
    """
    HTTP client for querying Open-Meteo Air Quality API
    (https://air-quality-api.open-meteo.com/v1/air-quality)
    as a non-commercial, zero-cost development fallback and historical reanalysis source for Delhi NCR.
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
        Fetch modeled recent hourly air quality estimates for given geographic coordinates.

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

        return self._execute_request(params)

    def fetch_historical_air_quality(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        chunk_days: Optional[int] = 30,
    ) -> Dict[str, Any]:
        """
        Fetch historical hourly modeled air quality estimates for a defined date window [start_date, end_date].

        Parameters:
        - latitude, longitude: Geographic decimal coordinates.
        - start_date, end_date: ISO date strings ('YYYY-MM-DD').
        - max_retries: Maximum transient retry attempts with exponential backoff.
        - backoff_base: Base duration in seconds for exponential backoff.
        - chunk_days: Optional maximum window per API query to avoid oversized responses.

        Returns unified decoded JSON response dictionary with 'hourly' records covering [start_date, end_date].
        """
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            raise ValueError(f"Invalid coordinates: latitude={latitude}, longitude={longitude}")

        start_d = parse_date_string(start_date)
        end_d = parse_date_string(end_date)

        if end_d < start_d:
            raise ValueError(f"end_date ({end_date}) cannot be earlier than start_date ({start_date})")

        # Determine date chunks if chunk_days is defined and window exceeds chunk_days
        total_days = (end_d - start_d).days + 1
        if chunk_days and total_days > chunk_days:
            return self._fetch_chunked_historical(
                latitude=latitude,
                longitude=longitude,
                start_d=start_d,
                end_d=end_d,
                chunk_days=chunk_days,
                max_retries=max_retries,
                backoff_base=backoff_base,
            )

        params: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(HOURLY_VARIABLES),
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "timezone": self.timezone,
        }

        return self._execute_request_with_retries(
            params=params,
            max_retries=max_retries,
            backoff_base=backoff_base,
        )

    def _fetch_chunked_historical(
        self,
        latitude: float,
        longitude: float,
        start_d: date,
        end_d: date,
        chunk_days: int,
        max_retries: int,
        backoff_base: float,
    ) -> Dict[str, Any]:
        """Query historical air quality in consecutive date intervals and merge the hourly arrays."""
        curr_start = start_d
        combined_hourly: Dict[str, List[Any]] = {
            "time": [],
            "pm2_5": [],
            "pm10": [],
            "nitrogen_dioxide": [],
            "sulphur_dioxide": [],
            "carbon_monoxide": [],
            "ozone": [],
        }
        metadata_sample: Dict[str, Any] = {}

        while curr_start <= end_d:
            curr_end = min(curr_start + timedelta(days=chunk_days - 1), end_d)
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(HOURLY_VARIABLES),
                "start_date": curr_start.isoformat(),
                "end_date": curr_end.isoformat(),
                "timezone": self.timezone,
            }

            chunk_payload = self._execute_request_with_retries(
                params=params,
                max_retries=max_retries,
                backoff_base=backoff_base,
            )

            if not metadata_sample:
                metadata_sample = {k: v for k, v in chunk_payload.items() if k != "hourly"}

            chunk_hourly = chunk_payload.get("hourly", {})
            for key, vals in chunk_hourly.items():
                if key not in combined_hourly:
                    combined_hourly[key] = []
                if isinstance(vals, list):
                    combined_hourly[key].extend(vals)

            curr_start = curr_end + timedelta(days=1)

        result = dict(metadata_sample)
        result["hourly"] = combined_hourly
        return result

    def _execute_request_with_retries(
        self,
        params: Dict[str, Any],
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> Dict[str, Any]:
        """Execute request with bounded exponential backoff for transient failures and rate limits."""
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                return self._execute_request(params)
            except (OpenMeteoTimeoutError, OpenMeteoNetworkError, OpenMeteoRateLimitError) as exc:
                last_exception = exc
                if attempt == max_retries:
                    raise

                sleep_time = backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    f"Transient Open-Meteo failure ({exc}). Retrying attempt {attempt + 1}/{max_retries} "
                    f"in {sleep_time:.1f}s..."
                )
                time.sleep(sleep_time)
            except OpenMeteoResponseError as exc:
                # Retry on server 5xx errors
                last_exception = exc
                if "HTTP 5" in str(exc) and attempt < max_retries:
                    sleep_time = backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"Open-Meteo 5xx server error ({exc}). Retrying attempt {attempt + 1}/{max_retries} "
                        f"in {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)
                    continue
                raise

        if last_exception:
            raise last_exception
        raise OpenMeteoError("Failed to execute Open-Meteo request after retries.")

    def _execute_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute single synchronous HTTP GET request with error classification."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)

                if response.status_code == 429:
                    raise OpenMeteoRateLimitError(
                        "Open-Meteo API rate limit exceeded (HTTP 429). Please throttle queries."
                    )
                elif response.status_code != 200:
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
