"""Load + normalize a company corpus into a uniform :class:`Artifact` stream.

This is the single fair normalization every adapter consumes; per-adapter
mapping to a system's native ingest shape happens downstream. We:
- read ``corpus_index.jsonl`` (one row per artifact),
- read each artifact file and strip its metadata header,
- derive a timestamp (event ``occurred_at`` for event-bound artifacts; else a
  date parsed from the artifact header for atmosphere / emergent / customer /
  fragment artifacts),
- resolve the author persona id to a display name.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import DATASETS_ROOT
from .schemas import Artifact

_HEADER_RE = re.compile(r"^\s*<!--.*?-->\s*", re.DOTALL)
_DATE_FULL = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_YM = re.compile(r"(\d{4})-(\d{2})(?!\d)")
_DATE_YQ = re.compile(r"(\d{4})[-\s]?Q([1-4])", re.IGNORECASE)
_QUARTER_MONTH = {1: "01", 2: "04", 3: "07", 4: "10"}


def tier_dir(tier: str, company: str = "helix") -> Path:
    d = DATASETS_ROOT / company / tier
    if not d.exists():
        raise FileNotFoundError(f"No dataset at {d}")
    return d


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


@lru_cache(maxsize=8)
def _events_index(tier: str, company: str) -> dict[str, str]:
    """event_id -> occurred_at (ISO date)."""
    rows = _read_jsonl(tier_dir(tier, company) / "source_of_truth" / "events.jsonl")
    return {r["id"]: str(r.get("occurred_at", ""))[:10] for r in rows if r.get("id")}


@lru_cache(maxsize=8)
def _persona_index(tier: str, company: str) -> dict[str, str]:
    """persona_id -> display_name."""
    rows = _read_jsonl(tier_dir(tier, company) / "helix_canon" / "personas.jsonl")
    return {r["persona_id"]: r.get("display_name", r["persona_id"]) for r in rows if r.get("persona_id")}


def _strip_header(text: str) -> str:
    return _HEADER_RE.sub("", text, count=1).strip()


def _parse_date(header_region: str) -> str | None:
    m = _DATE_FULL.search(header_region)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DATE_YQ.search(header_region)
    if m:
        return f"{m.group(1)}-{_QUARTER_MONTH[int(m.group(2))]}-01"
    m = _DATE_YM.search(header_region)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    return None


def _derive_timestamp(row: dict, raw_text: str, events_idx: dict[str, str]) -> str | None:
    ev = row.get("event_id")
    if ev and events_idx.get(ev):
        return events_idx[ev]
    # Non-event artifact: parse a date from the header (first ~300 chars).
    return _parse_date(raw_text[:300])


def load_corpus(tier: str, company: str = "helix") -> list[Artifact]:
    """Return the normalized artifact stream for one company tier."""
    base = tier_dir(tier, company)
    index = _read_jsonl(base / "corpus_index.jsonl")
    events_idx = _events_index(tier, company)
    persona_idx = _persona_index(tier, company)

    artifacts: list[Artifact] = []
    for row in index:
        path = base / row["path"]
        if not path.exists():
            continue
        raw_text = path.read_text(encoding="utf-8")
        author_id = row.get("author")
        artifacts.append(
            Artifact(
                slot_id=row["slot_id"],
                company=company,
                source_type=row.get("genre", "unknown"),
                text=_strip_header(raw_text),
                timestamp=_derive_timestamp(row, raw_text, events_idx),
                author=persona_idx.get(author_id) if author_id else None,
                thread_id=row.get("event_id") or row.get("emergent_pattern") or row.get("customer_id"),
                role=row.get("role"),
                raw=row,
            )
        )
    return artifacts


def corpus_stats(tier: str, company: str = "helix") -> dict:
    arts = load_corpus(tier, company)
    n_dated = sum(1 for a in arts if a.timestamp)
    total_chars = sum(len(a.text) for a in arts)
    from collections import Counter
    return {
        "company": company,
        "tier": tier,
        "n_artifacts": len(arts),
        "n_dated": n_dated,
        "total_chars": total_chars,
        "approx_tokens": total_chars // 4,
        "by_source_type": dict(Counter(a.source_type for a in arts)),
        "by_role": dict(Counter(a.role for a in arts)),
    }
