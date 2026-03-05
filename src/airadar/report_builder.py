from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    CompanyReport,
    EvidenceItem,
    Executive,
    Fact,
    Initiative,
    SelectedUrl,
    SerpResult,
    slugify,
    utc_now_iso,
)
from .extraction_firecrawl import FirecrawlExtract


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class EvidenceRegistry:
    def __init__(self) -> None:
        self._by_url: dict[str, EvidenceItem] = {}
        self._counter = 1

    def ensure(self, url: str, *, title: str | None = None, snippet: str | None = None) -> EvidenceItem:
        url = (url or "").strip()
        if not url:
            raise ValueError("Evidence URL is empty")
        existing = self._by_url.get(url)
        if existing:
            # Keep first title/snippet if already set.
            return existing
        eid = f"E{self._counter}"
        self._counter += 1
        item = EvidenceItem(id=eid, url=url, title=title, snippet=snippet)
        self._by_url[url] = item
        return item

    def id_for(self, url: str) -> str:
        return self.ensure(url).id

    def all_items(self) -> list[EvidenceItem]:
        # Preserve creation order by numeric id.
        return sorted(self._by_url.values(), key=lambda e: int(e.id[1:]))


def _safe_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return str(v).strip() or None


def _fact_from_obj(obj: Any, registry: EvidenceRegistry, *, fallback_url: str | None = None) -> Fact | None:
    if not isinstance(obj, dict):
        s = _safe_str(obj)
        if not s:
            return None
        ev = registry.id_for(fallback_url) if fallback_url else None
        return Fact(value=s, evidence_ids=[ev] if ev else [])

    value = _safe_str(obj.get("value"))
    if not value:
        return None
    src = _safe_str(obj.get("source_url")) or fallback_url
    evidence_ids = [registry.id_for(src)] if src else []
    return Fact(value=value, evidence_ids=evidence_ids)


def build_company_report(
    *,
    company_name: str,
    objective: str,
    serp_results: list[SerpResult],
    selected_sources: list[SelectedUrl],
    extraction: FirecrawlExtract,
) -> CompanyReport:
    registry = EvidenceRegistry()

    serp_by_url: dict[str, SerpResult] = {r.url: r for r in serp_results}
    for s in selected_sources:
        sr = serp_by_url.get(s.url)
        registry.ensure(s.url, title=sr.title if sr else None, snippet=sr.snippet if sr else None)

    # Also include Firecrawl sources if provided
    for src in extraction.sources:
        if not isinstance(src, dict):
            continue
        u = _safe_str(src.get("url") or src.get("source") or src.get("link"))
        if not u:
            continue
        registry.ensure(u, title=_safe_str(src.get("title")), snippet=_safe_str(src.get("snippet")))

    fallback_url = selected_sources[0].url if selected_sources else (serp_results[0].url if serp_results else None)
    data = extraction.data or {}

    identifiers = data.get("company_identifiers") if isinstance(data, dict) else {}
    if not isinstance(identifiers, dict):
        identifiers = {}

    hq_fact = None
    if isinstance(identifiers.get("headquarters"), dict):
        hq_fact = _fact_from_obj(identifiers.get("headquarters"), registry, fallback_url=fallback_url)

    company_identifiers: dict[str, Any] = {
        "name": _safe_str((identifiers.get("name") if isinstance(identifiers, dict) else None) or company_name) or company_name,
    }
    if hq_fact:
        company_identifiers["headquarters"] = asdict(hq_fact)

    snapshot = data.get("business_snapshot") if isinstance(data, dict) else {}
    if not isinstance(snapshot, dict):
        snapshot = {}

    def parse_fact_list(key: str) -> list[dict[str, Any]]:
        raw = snapshot.get(key)
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            f = _fact_from_obj(item, registry, fallback_url=fallback_url)
            if f:
                out.append(asdict(f))
        return out

    business_snapshot: dict[str, Any] = {
        "business_units": parse_fact_list("business_units"),
        "products_services": parse_fact_list("products_services"),
        "target_industries": parse_fact_list("target_industries"),
    }

    leadership_raw = data.get("leadership_signals") if isinstance(data, dict) else None
    executives: list[Executive] = []
    if isinstance(leadership_raw, list):
        for item in leadership_raw:
            if not isinstance(item, dict):
                continue
            name = _safe_str(item.get("name"))
            title = _safe_str(item.get("title"))
            src = _safe_str(item.get("source_url")) or fallback_url
            if not name or not title:
                continue
            evidence_ids = [registry.id_for(src)] if src else []
            executives.append(Executive(name=name, title=title, evidence_ids=evidence_ids))

    initiatives_raw = data.get("strategic_initiatives") if isinstance(data, dict) else None
    initiatives: list[Initiative] = []
    if isinstance(initiatives_raw, list):
        for item in initiatives_raw:
            if not isinstance(item, dict):
                continue
            init = _safe_str(item.get("initiative"))
            details = _safe_str(item.get("details"))
            src = _safe_str(item.get("source_url")) or fallback_url
            if not init:
                continue
            evidence_ids = [registry.id_for(src)] if src else []
            initiatives.append(Initiative(initiative=init, details=details, evidence_ids=evidence_ids))

    meta = {
        "generated_at": utc_now_iso(),
        "objective": objective,
        "firecrawl_job_id": extraction.job_id,
        "invalid_urls": extraction.invalid_urls,
    }

    return CompanyReport(
        meta=meta,
        company_identifiers=company_identifiers,
        business_snapshot=business_snapshot,
        leadership_signals={"executives": [asdict(e) for e in executives]},
        strategic_initiatives={"initiatives": [asdict(i) for i in initiatives]},
        evidence=registry.all_items(),
        selected_sources=selected_sources,
    )


def _fmt_evidence_tag(evidence_ids: list[str]) -> str:
    if not evidence_ids:
        return ""
    return " " + " ".join(f"[{e}]" for e in evidence_ids)


def render_markdown(report: CompanyReport) -> str:
    name = report.company_identifiers.get("name") or "Company"
    lines: list[str] = []
    lines.append(f"## {name} — Company Intelligence Report")
    lines.append("")
    lines.append(f"**Generated:** {report.meta.get('generated_at', '')}")
    lines.append("")
    lines.append("### Objective")
    lines.append("")
    lines.append(str(report.meta.get("objective", "")).strip())
    lines.append("")

    lines.append("### Company Identifiers")
    lines.append("")
    if "headquarters" in report.company_identifiers:
        hq = report.company_identifiers["headquarters"]
        lines.append(f"- Headquarters: {hq.get('value','')}{_fmt_evidence_tag(hq.get('evidence_ids', []))}")
    else:
        lines.append("- Headquarters: Not found")
    lines.append("")

    lines.append("### Business Snapshot")
    lines.append("")
    for label, key in [
        ("Business Units", "business_units"),
        ("Products & Services", "products_services"),
        ("Target Industries", "target_industries"),
    ]:
        lines.append(f"#### {label}")
        items = report.business_snapshot.get(key) or []
        if not items:
            lines.append("- Not found")
        else:
            for it in items:
                lines.append(f"- {it.get('value','')}{_fmt_evidence_tag(it.get('evidence_ids', []))}")
        lines.append("")

    lines.append("### Leadership Signals")
    lines.append("")
    execs = (report.leadership_signals.get("executives") or []) if isinstance(report.leadership_signals, dict) else []
    if not execs:
        lines.append("- Not found")
    else:
        for e in execs:
            lines.append(f"- {e.get('name','')} — {e.get('title','')}{_fmt_evidence_tag(e.get('evidence_ids', []))}")
    lines.append("")

    lines.append("### Strategic Initiatives")
    lines.append("")
    inits = (report.strategic_initiatives.get("initiatives") or []) if isinstance(report.strategic_initiatives, dict) else []
    if not inits:
        lines.append("- Not found")
    else:
        for i in inits:
            detail = (i.get("details") or "").strip()
            if detail:
                lines.append(f"- {i.get('initiative','')}: {detail}{_fmt_evidence_tag(i.get('evidence_ids', []))}")
            else:
                lines.append(f"- {i.get('initiative','')}{_fmt_evidence_tag(i.get('evidence_ids', []))}")
    lines.append("")

    lines.append("### Sources (Evidence)")
    lines.append("")
    for e in report.evidence:
        title = f" — {e.title}" if e.title else ""
        lines.append(f"- [{e.id}] {e.url}{title}")
    lines.append("")

    lines.append("### Selected Sources")
    lines.append("")
    for s in report.selected_sources:
        lines.append(f"- {s.url} — {s.why}")
    lines.append("")

    return "\n".join(lines)


def write_report_files(report: CompanyReport, *, out_dir: Path | None = None) -> tuple[Path, Path]:
    root = _project_root()
    reports_dir = out_dir or (root / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    company_slug = slugify(str(report.company_identifiers.get("name") or "company"))
    
    # Create a folder for each company
    company_dir = reports_dir / company_slug
    company_dir.mkdir(parents=True, exist_ok=True)

    json_path = company_dir / "data.json"
    md_path = company_dir / "report.md"

    json_path.write_text(json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return json_path, md_path

