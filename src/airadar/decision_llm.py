from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .errors import (
    DeepSeekInsufficientBalanceError,
    InvalidModelJsonError,
    UpstreamApiError,
)
from .models import SelectedUrl, SerpResult, unique_preserve_order


DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"


def heuristic_select_urls(serp_results: list[SerpResult]) -> list[SelectedUrl]:
    picked = serp_results[: max(1, 3)]
    return [
        SelectedUrl(url=r.url, why="Top SERP result (heuristic fallback).")
        for r in picked
    ]


def _extract_first_json_object(text: str) -> str:
    s = text.strip()
    start = s.find("{")
    if start < 0:
        raise InvalidModelJsonError("Model output did not contain a JSON object.")

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    raise InvalidModelJsonError("Model output contained an incomplete JSON object.")


@dataclass(frozen=True)
class DecisionResult:
    selected: list[SelectedUrl]
    raw_model_text: str


def select_best_urls(
    objective: str,
    serp_results: list[SerpResult],
    *,
    settings: Settings,
    max_urls: int,
) -> DecisionResult:
    try:
        import requests  # type: ignore
    except ImportError as e:
        raise UpstreamApiError(
            "Missing dependency: requests. Install with: pip install -r requirements.txt"
        ) from e

    candidates = [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "position": r.position,
        }
        for r in serp_results
    ]

    system = (
        "You select public web sources for a company research report.\n"
        "Rules:\n"
        "- Prefer official and highly credible sources (company domain, regulators, reputable news).\n"
        "- Do NOT select LinkedIn.\n"
        "- Select up to N URLs that best support the objective.\n"
        "- Output JSON only (no markdown fences)."
    )
    user = {
        "objective": objective,
        "max_urls": max_urls,
        "candidates": candidates,
        "output_schema": {
            "selected": [
                {
                    "url": "https://example.com",
                    "why": "Short reason tied to the objective",
                }
            ]
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "stream": False,
    }

    try:
        r = requests.post(
            DEEPSEEK_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=settings.http_timeout_seconds,
        )
    except requests.RequestException as e:
        raise UpstreamApiError("DeepSeek request failed.") from e

    if r.status_code == 402:
        raise DeepSeekInsufficientBalanceError(
            "DeepSeek returned HTTP 402 (insufficient balance).", status_code=402
        )
    if r.status_code >= 400:
        raise UpstreamApiError(
            f"DeepSeek returned HTTP {r.status_code}.", status_code=r.status_code
        )

    try:
        resp = r.json()
    except ValueError as e:
        raise UpstreamApiError("DeepSeek returned invalid JSON.") from e

    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise UpstreamApiError(
            "DeepSeek response missing choices/message/content."
        ) from e

    try:
        extracted = _extract_first_json_object(content)
        parsed: Any = json.loads(extracted)
    except (InvalidModelJsonError, json.JSONDecodeError) as e:
        raise InvalidModelJsonError(
            "Model returned invalid JSON for URL selection."
        ) from e

    selected_raw = parsed.get("selected") if isinstance(parsed, dict) else None
    if not isinstance(selected_raw, list):
        raise InvalidModelJsonError("Model JSON did not contain a 'selected' list.")

    candidate_urls = {r.url for r in serp_results}
    selected: list[SelectedUrl] = []
    for item in selected_raw:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        why = (item.get("why") or "").strip()
        if not url or url not in candidate_urls:
            continue
        if "linkedin.com" in url.lower():
            continue
        selected.append(
            SelectedUrl(url=url, why=why or "Selected for relevance to the objective.")
        )

    # Ensure unique and capped
    uniq_urls = unique_preserve_order([s.url for s in selected])
    selected = [next(s for s in selected if s.url == u) for u in uniq_urls][
        : max(1, max_urls)
    ]

    if not selected:
        selected = heuristic_select_urls(serp_results)

    return DecisionResult(selected=selected, raw_model_text=content)
