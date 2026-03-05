from __future__ import annotations

from urllib.parse import urlparse

from .config import Settings
from .errors import NoSerpResultsError, UpstreamApiError
from .http import post_json
from .models import SerpResult


SERP_ENDPOINT = "https://google.serper.dev/search"


def _is_linkedin(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "linkedin.com" in host


def discover_sources(
    company_name: str, objective: str, *, settings: Settings, max_results: int = 10
) -> list[SerpResult]:
    q = f"{company_name} {objective}".strip()

    headers = {
        "X-API-KEY": settings.serper_api_key,
    }
    body = {"q": q}

    resp = post_json(
        SERP_ENDPOINT,
        headers=headers,
        body=body,
        timeout_s=settings.http_timeout_seconds,
    )
    if not isinstance(resp.json, dict):
        raise UpstreamApiError("Serper.dev returned non-JSON payload")

    organic = resp.json.get("organic") or []
    out: list[SerpResult] = []
    seen: set[str] = set()

    for item in organic:
        if not isinstance(item, dict):
            continue
        url = (item.get("link") or "").strip()
        if not url or url in seen:
            continue
        if _is_linkedin(url):
            continue

        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        pos = item.get("position")
        out.append(
            SerpResult(
                title=title,
                url=url,
                snippet=snippet,
                position=pos if isinstance(pos, int) else None,
            )
        )
        seen.add(url)

    if not out:
        raise NoSerpResultsError(
            "No usable SERP results found for the company/objective."
        )

    return out
