from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    v = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    v = "-".join(part for part in v.split("-") if part)
    return v or "company"


@dataclass(frozen=True)
class SerpResult:
    title: str
    url: str
    snippet: str
    position: int | None = None


@dataclass(frozen=True)
class SelectedUrl:
    url: str
    why: str


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    url: str
    title: str | None = None
    snippet: str | None = None


@dataclass(frozen=True)
class Fact:
    value: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class Executive:
    name: str
    title: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class Initiative:
    initiative: str
    details: str | None
    evidence_ids: list[str]


@dataclass
class CompanyReport:
    meta: dict[str, Any]
    company_identifiers: dict[str, Any]
    business_snapshot: dict[str, Any]
    leadership_signals: dict[str, Any]
    strategic_initiatives: dict[str, Any]
    evidence: list[EvidenceItem]
    selected_sources: list[SelectedUrl]

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [asdict(e) for e in self.evidence]
        d["selected_sources"] = [asdict(s) for s in self.selected_sources]
        return d


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out

