import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DataGovAPIError(Exception):
    """Base exception for data.gov.in integration failures."""
    pass


class DataGovAuthError(DataGovAPIError):
    """Raised when the data.gov.in API key is missing or invalid."""
    pass


class DataGovRateLimitError(DataGovAPIError):
    """Raised when data.gov.in rate limits the client."""
    pass


def _mask_api_key(url_or_params: str) -> str:
    """Helper to remove API keys from URLs or error logs."""
    import re
    return re.sub(r'(api-key=)[^&]+', r'\1***', str(url_or_params))


class DataGovClient:
    """
    HTTP client for querying the official Open Government Data (data.gov.in)
    Real-time Air Quality Index API contributed by CPCB / MoEFCC.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        resource_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.data_gov_in_api_key
        self.resource_id = resource_id or settings.data_gov_in_resource_id
        self.base_url = (base_url or settings.data_gov_in_base_url).rstrip("/")
        self.timeout = timeout or settings.data_gov_in_timeout_seconds

    @property
    def endpoint_url(self) -> str:
        return f"{self.base_url}/{self.resource_id}"

    def fetch_records(
        self,
        limit: int = 1000,
        offset: int = 0,
        state: Optional[str] = None,
        city: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch raw pollutant observation records from data.gov.in.

        Returns a list of raw record dictionaries.
        Raises DataGovAuthError, DataGovRateLimitError, or DataGovAPIError on failure.
        """
        if not self.api_key:
            raise DataGovAuthError(
                "DATA_GOV_IN_API_KEY is not configured in environment. "
                "Obtain a free API key at https://data.gov.in to enable ingestion."
            )

        params: Dict[str, Any] = {
            "api-key": self.api_key,
            "format": "json",
            "limit": limit,
            "offset": offset,
        }
        if state:
            params["filters[state]"] = state
        if city:
            params["filters[city]"] = city

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.endpoint_url, params=params)

                if response.status_code in (401, 403):
                    raise DataGovAuthError(
                        f"Authentication failed on data.gov.in (HTTP {response.status_code}). "
                        "Verify that your DATA_GOV_IN_API_KEY is valid."
                    )
                elif response.status_code == 429:
                    raise DataGovRateLimitError(
                        "Rate limit exceeded on data.gov.in (HTTP 429). Please retry later."
                    )
                elif response.status_code != 200:
                    raise DataGovAPIError(
                        f"data.gov.in returned error HTTP {response.status_code}: {response.text[:200]}"
                    )

                try:
                    payload = response.json()
                except Exception as exc:
                    raise DataGovAPIError(
                        f"Failed to decode JSON response from data.gov.in: {str(exc)}"
                    ) from exc

                # Check if payload contains an internal error status
                if isinstance(payload, dict):
                    if payload.get("status") == "error":
                        error_msg = payload.get("message") or payload.get("desc") or "Unknown API error"
                        raise DataGovAPIError(f"data.gov.in reported error: {error_msg}")

                    records = payload.get("records", [])
                    if isinstance(records, list):
                        return records
                    return []

                return []

        except (DataGovAuthError, DataGovRateLimitError, DataGovAPIError):
            raise
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise DataGovAPIError(
                f"Connection failure communicating with data.gov.in: {str(exc)}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise DataGovAPIError(
                f"Request to data.gov.in timed out after {self.timeout}s: {str(exc)}"
            ) from exc
        except Exception as exc:
            raise DataGovAPIError(
                f"Unexpected error querying data.gov.in: {str(exc)}"
            ) from exc
