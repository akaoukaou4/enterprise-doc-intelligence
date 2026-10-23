"""HTTP client of the FastAPI backend, used by the Streamlit UI.

The UI talks to the API over HTTP only and imports nothing from app/ (D-47).
"""

import os
from typing import Any

import requests

DEFAULT_API_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 15
UPLOAD_TIMEOUT = 60
# The first question after a server start loads the embedding model (about 22 s)
# and then waits for Gemini (30 s timeout on the server).
ASK_TIMEOUT = 90
HEALTH_TIMEOUT = 5


class ApiError(Exception):
    """A failure the UI can show to the user as a short message."""


def _error_message(response: Any) -> str:
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return f"The server returned an error ({response.status_code})."


class ApiClient:
    def __init__(self, base_url: str | None = None, session: Any = None) -> None:
        self._base = (base_url or os.environ.get("API_URL", DEFAULT_API_URL)).rstrip("/")
        self._http = session or requests.Session()

    def _request(self, method: str, path: str, timeout: int, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base}{API_PREFIX}{path}"
        try:
            response = self._http.request(method, url, timeout=timeout, **kwargs)
        except requests.ConnectionError:
            raise ApiError("Cannot reach the API. Is it running?") from None
        except requests.Timeout:
            raise ApiError("The API took too long to answer. Try again.") from None
        except requests.RequestException:
            raise ApiError("The request to the API failed.") from None
        if not response.ok:
            raise ApiError(_error_message(response))
        return response.json()

    def upload_document(self, filename: str, data: bytes) -> dict[str, Any]:
        files = {"file": (filename, data, "application/pdf")}
        return self._request("POST", "/documents", UPLOAD_TIMEOUT, files=files)

    def list_documents(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        params = {"limit": limit, "offset": offset}
        return self._request("GET", "/documents", DEFAULT_TIMEOUT, params=params)

    def ask(self, question: str, top_k: int | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question}
        if top_k is not None:
            body["top_k"] = top_k
        return self._request("POST", "/ask", ASK_TIMEOUT, json=body)

    def model_status(self) -> str:
        """The embedding model state: ready, loading or idle. unknown if the API is unreachable."""
        try:
            response = self._http.request(
                "GET", f"{self._base}/health/model", timeout=HEALTH_TIMEOUT
            )
            return str(response.json()["status"])
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return "unknown"
