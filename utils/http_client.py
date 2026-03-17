from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Default timeout (seconds) for all requests
_DEFAULT_TIMEOUT: float = 10.0

# Keys expected in a valid build-area response
_BUILD_AREA_KEYS: frozenset[str] = frozenset(
    ["xFrom", "yFrom", "zFrom", "xTo", "yTo", "zTo"]
)


class GDMCClient:
    """
    HTTP client for the GDMC HTTP API.

    Uses a persistent session for connection reuse across the many requests
    a PCG run typically makes. Includes a configurable timeout and optional
    automatic retry on transient failures.

    Parameters
    ----------
    base_url : str
        Base URL of the GDMC server (default: "http://localhost:9000").
    timeout : float
        Per-request timeout in seconds (default: 10.0).
    retries : int
        Number of automatic retries on connection errors (default: 3).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9000",
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout

        self._session = requests.Session()

        # Mount a retry adapter for transient connection errors
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=retries,
                backoff_factor=0.2,
                status_forcelist=[502, 503, 504],
                allowed_methods=["GET", "PUT", "POST"],
            )
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> dict | None:
        url = f"{self.base_url}{endpoint}"
        try:
            r = self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=self.timeout,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise requests.exceptions.HTTPError(
                f"{method} {url} failed with status {exc.response.status_code}: "
                f"{exc.response.text[:200]}"
            ) from exc

        if r.text:
            return r.json()
        return None

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict | None = None) -> dict | None:
        return self.request("GET", endpoint, params=params)

    def put(self, endpoint: str, data: dict | None = None) -> dict | None:
        return self.request("PUT", endpoint, data=data)

    def post(self, endpoint: str, data: dict | None = None) -> dict | None:
        return self.request("POST", endpoint, data=data)

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        """Return True if the GDMC server is reachable."""
        try:
            r = self._session.options(
                f"{self.base_url}/", timeout=self.timeout
            )
            return r.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def check_build_area(self) -> bool:
        """Return True if the server returns a valid build-area response."""
        try:
            data = self.get("/buildarea")
            return data is not None and _BUILD_AREA_KEYS.issubset(data)
        except (requests.exceptions.RequestException, ValueError):
            return False

    # ------------------------------------------------------------------
    # Context manager support — ensures session is closed cleanly
    # ------------------------------------------------------------------

    def __enter__(self) -> "GDMCClient":
        return self

    def __exit__(self, *_) -> None:
        self._session.close()