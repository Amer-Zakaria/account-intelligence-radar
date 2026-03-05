from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .errors import FirecrawlTimeoutError, UpstreamApiError


FIRECRAWL_EXTRACT_ENDPOINT = "https://api.firecrawl.dev/v2/extract"


def company_extract_schema() -> dict[str, Any]:
    # JSON Schema to encourage per-item traceability via source_url.
    return {
        "type": "object",
        "properties": {
            "company_identifiers": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "headquarters": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "source_url": {"type": "string"},
                        },
                        "required": ["value", "source_url"],
                    },
                },
                "required": ["name"],
            },
            "business_snapshot": {
                "type": "object",
                "properties": {
                    "business_units": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}, "source_url": {"type": "string"}},
                            "required": ["value", "source_url"],
                        },
                    },
                    "products_services": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}, "source_url": {"type": "string"}},
                            "required": ["value", "source_url"],
                        },
                    },
                    "target_industries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}, "source_url": {"type": "string"}},
                            "required": ["value", "source_url"],
                        },
                    },
                },
            },
            "leadership_signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "source_url": {"type": "string"},
                    },
                    "required": ["name", "title", "source_url"],
                },
            },
            "strategic_initiatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "initiative": {"type": "string"},
                        "details": {"type": "string"},
                        "source_url": {"type": "string"},
                    },
                    "required": ["initiative", "source_url"],
                },
            },
            "notes": {"type": "string"},
        },
        "required": ["company_identifiers"],
        "additionalProperties": True,
    }


def company_extract_prompt(company_name: str, objective: str) -> str:
    return (
        f"You are extracting public information for a business outreach report about: {company_name}.\n"
        f"Objective: {objective}\n\n"
        "Instructions:\n"
        "- Only include executives if their names/titles are published on credible official sources.\n"
        "- For every field/item, include a source_url pointing to where it was found.\n"
        "- If a value is not found, omit it (do not guess).\n"
        "- Output must conform to the provided JSON Schema."
    )


@dataclass(frozen=True)
class FirecrawlExtract:
    data: dict[str, Any]
    sources: list[dict[str, Any]]
    invalid_urls: list[str]
    job_id: str


def run_extract(
    urls: list[str],
    *,
    settings: Settings,
    prompt: str,
    schema: dict[str, Any],
) -> FirecrawlExtract:
    try:
        import requests  # type: ignore
    except ImportError as e:
        raise UpstreamApiError("Missing dependency: requests. Install with: pip install -r requirements.txt") from e

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
    }
    body = {
        "urls": urls,
        "prompt": prompt,
        "schema": schema,
        "showSources": True,
        "ignoreInvalidURLs": True,
        "enableWebSearch": False,
    }

    try:
        r = requests.post(FIRECRAWL_EXTRACT_ENDPOINT, headers=headers, json=body, timeout=settings.http_timeout_seconds)
    except requests.RequestException as e:
        raise UpstreamApiError("Firecrawl extract request failed.") from e

    if r.status_code >= 400:
        raise UpstreamApiError(f"Firecrawl returned HTTP {r.status_code}.", status_code=r.status_code)

    try:
        start = r.json()
    except ValueError as e:
        raise UpstreamApiError("Firecrawl returned invalid JSON.") from e

    if not isinstance(start, dict) or not start.get("success") or not start.get("id"):
        raise UpstreamApiError("Firecrawl extract did not return a job id.")

    job_id = str(start["id"])
    invalid_urls = start.get("invalidURLs") or []
    if not isinstance(invalid_urls, list):
        invalid_urls = []

    status_url = f"{FIRECRAWL_EXTRACT_ENDPOINT}/{job_id}"
    deadline = time.time() + settings.firecrawl_max_poll_seconds
    last_status = None

    while time.time() < deadline:
        try:
            s = requests.get(status_url, headers=headers, timeout=settings.http_timeout_seconds)
        except requests.RequestException as e:
            raise UpstreamApiError("Firecrawl status request failed.") from e

        if s.status_code >= 400:
            raise UpstreamApiError(f"Firecrawl status returned HTTP {s.status_code}.", status_code=s.status_code)

        try:
            payload = s.json()
        except ValueError as e:
            raise UpstreamApiError("Firecrawl status returned invalid JSON.") from e

        if not isinstance(payload, dict) or not payload.get("success"):
            raise UpstreamApiError("Firecrawl status response was not successful.")

        status = payload.get("status")
        last_status = status
        if status == "completed":
            data = payload.get("data") or {}
            if not isinstance(data, dict):
                data = {"value": data}
            sources = data.get("sources") if isinstance(data, dict) else None
            if sources is None:
                sources = payload.get("sources")
            if not isinstance(sources, list):
                sources = []
            return FirecrawlExtract(data=data, sources=sources, invalid_urls=invalid_urls, job_id=job_id)

        if status in ("failed", "cancelled"):
            raise UpstreamApiError(f"Firecrawl extract job ended with status: {status}")

        time.sleep(max(1, settings.firecrawl_poll_interval_seconds))

    raise FirecrawlTimeoutError(f"Firecrawl extract timed out (last status: {last_status})")

