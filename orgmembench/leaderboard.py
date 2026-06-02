"""Render results/ into a versioned leaderboard.md (the screenshot artifact).

Reads each ``results/<system>/<company>-<tier>.json`` (a serialized RunResult),
and emits a per-tier table: the 5D metrics + accuracy breakdown + per-public-
category scores (N/A where a system lacks the required capability). The
``reference`` dev fixture is excluded from the public leaderboard.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import RESULTS_ROOT
from .schemas import CATEGORY_INFO

_PUBLIC_CATS = [info[0] for info in CATEGORY_INFO.values()]
_CORE_COLS = [
    ("accuracy_mean", "Acc"),
    ("exact_match_rate", "EM"),
    ("semantic_mean", "Sem"),
    ("hallucination_rate", "Halluc"),
    ("latency_ms_p50", "p50ms"),
    ("latency_ms_p95", "p95ms"),
    ("cost_per_query_usd", "$/q"),
    ("tokens_stored", "Tok.stored"),
    ("ingest_seconds", "Ingest.s"),
]


def _load_all() -> list[dict]:
    out = []
    if not RESULTS_ROOT.exists():
        return out
    for f in RESULTS_ROOT.glob("*/*.json"):
        try:
            run = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if run.get("system") == "reference":
            continue
        out.append(run)
    return out


def _fmt(v) -> str:
    if v == "N/A" or v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:.1f}"
    return str(v)


def build_leaderboard() -> str:
    runs = _load_all()
    lines = ["# OrgMemBench leaderboard", ""]
    if not runs:
        lines.append("_No results yet. Run a system to populate this._")
        return "\n".join(lines) + "\n"

    tiers = sorted({r["tier"] for r in runs})
    for tier in tiers:
        rows = [r for r in runs if r["tier"] == tier]
        lines.append(f"## Tier: {tier}")
        lines.append("")
        header = ["System (version)"] + [c[1] for c in _CORE_COLS] + _PUBLIC_CATS
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for r in sorted(rows, key=lambda x: x.get("metrics", {}).get("accuracy_mean", 0), reverse=True):
            m = r.get("metrics", {})
            name = f"{r['system']} ({r.get('system_version', '?')})"
            if m.get("dry_run") or r.get("dry_run"):
                name += " [dry-run]"
            cells = [name] + [_fmt(m.get(k)) for k, _ in _CORE_COLS]
            by_cat = m.get("by_category", {})
            cells += [_fmt(by_cat.get(c, "—")) for c in _PUBLIC_CATS]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_leaderboard(path: Path | None = None) -> Path:
    path = path or (RESULTS_ROOT / "leaderboard.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_leaderboard(), encoding="utf-8")
    return path
