from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import UpstreamApiError


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    json: Any
    text: str


def get_json(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout_s: int = 30) -> HttpResponse:
    try:
        import requests  # type: ignore
    except ImportError as e:
        raise UpstreamApiError("Missing dependency: requests. Install with: pip install -r requirements.txt") from e

    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout_s)
    except requests.RequestException as e:
        raise UpstreamApiError(f"HTTP GET failed: {url}") from e

    text = r.text or ""
    try:
        payload = r.json()
    except ValueError:
        payload = None

    if r.status_code >= 400:
        raise UpstreamApiError(f"HTTP GET {r.status_code} from {url}", status_code=r.status_code)

    return HttpResponse(status_code=r.status_code, json=payload, text=text)


def post_json(url: str, *, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None, timeout_s: int = 30) -> HttpResponse:
    try:
        import requests  # type: ignore
    except ImportError as e:
        raise UpstreamApiError("Missing dependency: requests. Install with: pip install -r requirements.txt") from e

    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout_s)
    except requests.RequestException as e:
        raise UpstreamApiError(f"HTTP POST failed: {url}") from e

    text = r.text or ""
    try:
        payload = r.json()
    except ValueError:
        payload = None

    if r.status_code >= 400:
        raise UpstreamApiError(f"HTTP POST {r.status_code} from {url}", status_code=r.status_code)

    return HttpResponse(status_code=r.status_code, json=payload, text=text)

