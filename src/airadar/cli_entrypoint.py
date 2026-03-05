from __future__ import annotations

import argparse
import sys

from .config import Settings
from .decision_llm import heuristic_select_urls, select_best_urls
from .discovery_serp import discover_sources
from .errors import (
    AiradarError,
    ConfigurationError,
    DeepSeekInsufficientBalanceError,
    InvalidModelJsonError,
    NoSerpResultsError,
    UpstreamApiError,
)
from .extraction_firecrawl import company_extract_prompt, company_extract_schema, run_extract
from .report_builder import build_company_report, write_report_files


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airadar (company mode)")
    p.add_argument("--company", dest="company", help="Company name")
    p.add_argument("--objective", dest="objective", help="Objective prompt for extraction")
    p.add_argument("--max-urls", dest="max_urls", type=int, default=0, help="Max URLs to extract (overrides .env)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    company = (args.company or "").strip()
    objective = (args.objective or "").strip()
    if not company:
        company = input("Company name: ").strip()
    if not objective:
        objective = input("Objective prompt: ").strip()
    if not company or not objective:
        print("Company name and objective are required.")
        return 2

    try:
        settings = Settings.load()
    except ConfigurationError as e:
        print(str(e))
        return 2

    max_urls = args.max_urls if args.max_urls and args.max_urls > 0 else settings.max_urls_for_extraction
    max_urls = max(1, min(max_urls, 10))

    try:
        serp = discover_sources(company, objective, settings=settings, max_results=10)
    except NoSerpResultsError as e:
        print(str(e))
        return 3
    except UpstreamApiError as e:
        print(f"Discovery failed: {e}")
        return 4

    selected = None
    try:
        decision = select_best_urls(objective, serp, settings=settings, max_urls=max_urls)
        selected = decision.selected
    except DeepSeekInsufficientBalanceError:
        print("DeepSeek balance insufficient (HTTP 402). Falling back to heuristic URL selection.")
        selected = heuristic_select_urls(serp, max_urls=max_urls)
    except (InvalidModelJsonError, UpstreamApiError) as e:
        print(f"URL selection issue: {e}. Falling back to heuristic URL selection.")
        selected = heuristic_select_urls(serp, max_urls=max_urls)

    urls = [s.url for s in selected][:max_urls]

    try:
        extract = run_extract(
            urls,
            settings=settings,
            prompt=company_extract_prompt(company, objective),
            schema=company_extract_schema(),
        )
    except AiradarError as e:
        print(f"Extraction failed: {e}")
        return 5

    report = build_company_report(
        company_name=company,
        objective=objective,
        serp_results=serp,
        selected_sources=selected,
        extraction=extract,
    )

    json_path, md_path = write_report_files(report)
    print(f"Wrote JSON: {json_path}")
    print(f"Wrote Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

