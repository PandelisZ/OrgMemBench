"""Stage B6 — Topic-threaded supersession chains.

The 541 events were generated independently per window, so few form the
multi-year chains that C1/C3/C4/C6/HARD questions feed on (only 68
relations total → C3=3, C6=2, HARD=6). B6 manufactures the missing graph
richness: it picks recurring TOPICS that plausibly evolved over years and
generates an explicit chain of 3-5 linked decisions per topic, with the
temporal-memory structure the categories need:

- consecutive versions linked by supersedes / reverses / re_attempts
  (→ C1 supersession, C4 audit replay, HARD lineage)
- at least one retroactive correction per chain where allowed
  (corrects_event_id + retroactively_corrected_by → C3 bi-temporal)
- at least one contradiction-then-resolution, emitted as two disjoint-
  participant "stance" events + contradicts + resolved_by (→ C6)

Purely additive: appends events to events.jsonl and relations to
relations.jsonl with evidence_in_corpus slots, using a high seq range
(EV-<year>-900+) that cannot collide with existing IDs. After B6, re-run
Stage C (generates the new events' corpus), then E/F/repair.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM
from helix_corpus.parsers import parse_yaml_lenient, strip_code_fences, normalize_smart_quotes

logger = logging.getLogger("helix_corpus.stage_b6")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_b6"
COMPANY_ONE_LINER = (
    "Helix Logistics: B2B SaaS for mid-market freight-forwarding "
    "companies, founded in 2020, ~85 employees by 2025."
)

SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"n_topics": 3,  "versions_min": 3, "versions_max": 4},
    "medium": {"n_topics": 8,  "versions_min": 3, "versions_max": 5},
    "large":  {"n_topics": 18, "versions_min": 3, "versions_max": 5},
}

# Informal-primary dispersal: the load-bearing version decision lives in
# an informal genre, context in formal ones (matches the §4.2 rule).
_PRIMARY_GENRES = ["slack_thread", "meeting_transcript"]
_SECONDARY_GENRES = ["meeting_notes", "email_thread", "notion_doc"]


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_canon(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    skeleton = json.loads((canon / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {"skeleton": skeleton, "personas": personas,
            "persona_by_id": {p["persona_id"]: p for p in personas}}


def _year_arcs_block(skeleton: dict) -> str:
    return "\n".join(f"- {y}: {t}" for y, t in sorted(skeleton.get("year_arcs", {}).items()))


def _personas_block(personas: list[dict]) -> str:
    lines = []
    for p in personas:
        role = (p.get("role_history") or [{}])[0].get("role", "?")
        jy = p.get("joined_year", "?"); ly = p.get("left_year")
        span = f"{jy}-{ly}" if ly else f"{jy}+"
        lines.append(f"- {p['persona_id']} {p.get('display_name','?')} ({role}, {span})")
    return "\n".join(lines)


def _max_seq_by_year(events: list[dict]) -> dict[int, int]:
    mx: dict[int, int] = {}
    for e in events:
        m = re.match(r"EV-(\d{4})-(\d+)", str(e.get("id", "")))
        if m:
            y, s = int(m.group(1)), int(m.group(2))
            mx[y] = max(mx.get(y, 0), s)
    return mx


def _ym_to_date(ym: str) -> str:
    ym = str(ym).strip()
    m = re.match(r"(\d{4})-(\d{1,2})", ym)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-15"
    if re.match(r"\d{4}", ym):
        return f"{ym[:4]}-06-15"
    return "2023-06-15"


def _parse_chain(text: str) -> list[dict]:
    """Parse version blocks robustly. gpt-oss inconsistently uses ---
    separators vs blank lines (which would collapse blocks into one YAML
    doc with duplicate keys). So we split on each ``version:`` line —
    every block starts with one — and parse each block's key:value pairs.
    """
    text = strip_code_fences(normalize_smart_quotes(text))
    lines = text.splitlines()
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        if re.match(r"^\s*version\s*:", ln):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    # Fallback: if no version: lines found, try --- split
    if not blocks:
        blocks = [b.splitlines() for b in re.split(r"(?m)^\s*---\s*$", text) if b.strip()]

    versions = []
    for blk in blocks:
        rec = parse_yaml_lenient("\n".join(blk))
        rec = rec[0] if isinstance(rec, list) and rec else (rec if isinstance(rec, dict) else None)
        if rec and (rec.get("decision") or rec.get("year_month")):
            versions.append(rec)
    return versions


def _as_id_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip() for x in re.findall(r"P-\d+", v)]
    return []


_REL_MAP = {"supersedes": "supersedes", "reverses": "reverses", "re_attempts": "re_attempts",
            "reattempts": "re_attempts", "re-attempts": "re_attempts"}


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    canon = _load_canon(data_root)
    valid_ids = set(canon["persona_by_id"])

    events_file = data_root / "source_of_truth" / "events.jsonl"
    relations_file = data_root / "source_of_truth" / "relations.jsonl"
    events = [json.loads(l) for l in events_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    cp = Checkpoint(data_root / ".checkpoints" / "stage_b6.jsonl")

    # global seq counter in the 900+ range (collision-free)
    base_seq = max([900] + [s for s in _max_seq_by_year(events).values() if s >= 900]) + 1
    seq = max(900, base_seq)

    yblock = _year_arcs_block(canon["skeleton"])
    pblock = _personas_block(canon["personas"])
    tblock = "\n".join(
        f"- {t['year']}: {t['description']}" for t in canon["skeleton"].get("tooling", [])
    )

    llm = HelixLLM()
    new_events: list[dict] = []
    new_relations: list[dict] = []

    def _mk_event(year: int, month_date: str, deciders: list[str], decision: str,
                  reason: str, alts: list[str], topic: str, vlabel: str,
                  cat: str, n_slots: int = 3) -> dict:
        nonlocal seq
        eid = f"EV-{year}-{seq}"; seq += 1
        deciders = [d for d in deciders if d in valid_ids] or [next(iter(valid_ids))]
        slots = []
        for i in range(n_slots):
            genre = (_PRIMARY_GENRES if i == 0 else _SECONDARY_GENRES)[i % (len(_PRIMARY_GENRES) if i == 0 else len(_SECONDARY_GENRES))]
            slots.append({
                "slot_id": f"ART-{eid}-{i+1:03d}", "genre": genre,
                "role": "primary" if i == 0 else "secondary",
                "author": deciders[i % len(deciders)],
            })
        return {
            "id": eid, "type": "policy_decision", "occurred_at": month_date,
            "recorded_at": month_date, "participants": deciders,
            "decision": decision[:400], "reason_canonical": reason[:400],
            "alternatives_considered": [str(a)[:120] for a in (alts or [])][:4],
            "category_target": cat, "summary": f"{topic} — {vlabel}: {decision[:120]}",
            "evidence_in_corpus": slots,
        }

    try:
        # ---- B6.1: propose topics ----
        if not cp.is_done("topics"):
            tprompt = _load_template("propose_topics.md").format(
                company_one_liner=COMPANY_ONE_LINER, year_arcs_block=yblock,
                tooling_block=tblock, n_topics=params["n_topics"],
            )
            ttext = await llm.call_text(stage="B", user=tprompt, reasoning_effort="low", max_tokens=2000)
            topics = [l.strip().lstrip("-").strip() for l in ttext.splitlines() if l.strip().startswith("-")]
            topics = [t for t in topics if t][: params["n_topics"]]
            (data_root / "helix_canon" / "supersession_topics.json").write_text(
                json.dumps(topics, indent=2), encoding="utf-8")
            cp.mark_done("topics", count=len(topics))
        topics = json.loads((data_root / "helix_canon" / "supersession_topics.json").read_text(encoding="utf-8"))
        logger.info("B6: %d topics", len(topics))

        # ---- B6.2: per-topic chain ----
        for ti, topic_line in enumerate(topics):
            unit = f"chain-{ti}"
            if cp.is_done(unit):
                continue
            nver = params["versions_min"] + (ti % (params["versions_max"] - params["versions_min"] + 1))
            cprompt = _load_template("generate_chain.md").format(
                company_one_liner=COMPANY_ONE_LINER, topic_line=topic_line,
                year_arcs_block=yblock, personas_block=pblock, n_versions=nver,
            )
            ctext = await llm.call_text(stage="B", user=cprompt, reasoning_effort="medium", max_tokens=6000)
            versions = _parse_chain(ctext)
            versions = [v for v in versions if v.get("decision")]
            if len(versions) < 2:
                logger.warning("B6 chain %d (%s): only %d versions parsed — skipping", ti, topic_line[:40], len(versions))
                cp.mark_done(unit, status="skip-thin")
                continue
            versions.sort(key=lambda v: str(v.get("year_month", "")))
            topic_title = topic_line.split("|")[0].strip()

            ver_events: list[dict] = []
            chain_events_buf: list[dict] = []
            chain_relations_buf: list[dict] = []

            def _add_event(e: dict) -> None:
                chain_events_buf.append(e); new_events.append(e)

            def _add_rel(src: str, relation: str, tgt: str) -> None:
                r = {"source": src, "relation": relation, "target": tgt}
                chain_relations_buf.append(r); new_relations.append(r)

            for vi, v in enumerate(versions):
                ymd = _ym_to_date(v.get("year_month", ""))
                year = int(ymd[:4])
                cat = "C1" if vi > 0 else "C2"
                ev = _mk_event(year, ymd, _as_id_list(v.get("decider_ids")),
                               str(v.get("decision", "")), str(v.get("reason", "")),
                               v.get("alternatives", []), topic_title, f"v{vi+1}", cat)
                ver_events.append(ev)
                _add_event(ev)
                # link to previous
                if vi > 0:
                    rel = _REL_MAP.get(str(v.get("relation_to_previous", "")).strip().lower(), "supersedes")
                    _add_rel(ev["id"], rel, ver_events[vi-1]["id"])
                # retroactive correction
                cor = v.get("corrects_earlier_version")
                try:
                    cor_idx = int(cor) - 1
                except (TypeError, ValueError):
                    cor_idx = None
                if cor_idx is not None and 0 <= cor_idx < vi:
                    older = ver_events[cor_idx]
                    ev["corrects_event_id"] = older["id"]
                    ev["category_target"] = "C3"
                    _add_rel(older["id"], "retroactively_corrected_by", ev["id"])
                # contradiction → two disjoint stance events + resolved_by
                contr = v.get("contradiction")
                if contr and isinstance(contr, str):
                    pids = re.findall(r"P-\d+", contr)
                    pa = next((p for p in pids if p in valid_ids), None)
                    pb = next((p for p in pids if p in valid_ids and p != pa), None)
                    if pa and pb:
                        ya = int(_ym_to_date(v.get("year_month",""))[:4])
                        ea = _mk_event(ya, ymd, [pa], f"{pa} argued: {contr[:200]}", "position taken in the debate", [], topic_title, f"v{vi+1} stance A", "C6", n_slots=2)
                        eb = _mk_event(ya, ymd, [pb], f"{pb} argued the opposing view: {contr[:200]}", "opposing position", [], topic_title, f"v{vi+1} stance B", "C6", n_slots=2)
                        _add_event(ea); _add_event(eb)
                        _add_rel(ea["id"], "contradicts", eb["id"])
                        _add_rel(ea["id"], "resolved_by", ev["id"])
            # Append THIS chain's events+relations immediately (crash-safe:
            # the checkpoint mark below must only happen once persisted, so
            # an interruption never marks a chain done with unwritten data).
            with events_file.open("a", encoding="utf-8") as f:
                for e in chain_events_buf:
                    f.write(json.dumps(e, default=str) + "\n")
            with relations_file.open("a", encoding="utf-8") as f:
                for r in chain_relations_buf:
                    f.write(json.dumps(r, default=str) + "\n")
            cp.mark_done(unit, versions=len(versions), events=len(chain_events_buf))
            logger.info("B6 chain %d/%d '%s': %d versions, +%d events",
                        ti+1, len(topics), topic_title[:40], len(versions), len(chain_events_buf))

        logger.info("Stage B6 complete. +%d events, +%d relations this run.", len(new_events), len(new_relations))
    finally:
        await llm.aclose()
