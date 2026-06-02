"""Stage B — Source-of-truth graph generation.

The load-bearing artefact of the whole benchmark: the parallel record
of what *actually* happened at Helix. Every benchmark question's
answer is a deterministic projection from this graph (see design doc §6
and §9).

Four passes:

* B1 — master timeline: per (year, quarter, team) window, gpt-oss
  writes event sketches as structured Markdown blocks.
* B2 — event expansion: each sketch → full YAML event record with
  ``decision``, ``reason_canonical``, ``alternatives_considered``,
  ``evidence_in_corpus`` slot list.
* B3 — cross-event linking: gpt-oss reads the whole event set and
  emits ``A -> relation -> B`` triples.
* B4 — coverage gap-fill: per-category coverage check; if any
  category is below target, gpt-oss generates more event sketches
  for that category (which then go back through B2).

Outputs under ``data/source_of_truth/``:

* ``events.jsonl`` — one event per line (final, after B2 + B4).
* ``relations.jsonl`` — one triple per line.
* ``coverage_report.json`` — per-category, per-year, per-team counts.
* ``.checkpoints/`` — resume state.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM
from helix_corpus.parsers import (
    parse_triples_line,
    parse_yaml_lenient,
    strip_code_fences,
)
from helix_corpus.schemas import Event, Relation, RelationType

logger = logging.getLogger("helix_corpus.stage_b")

# Paths
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_b"
CURRENT_YEAR = 2026
COMPANY_NAME = "Helix Logistics"
COMPANY_ARCHETYPE = (
    "B2B SaaS for mid-market freight-forwarding companies, "
    "founded in 2020, ~85 employees by 2025"
)
COMPANY_ONE_LINER = f"{COMPANY_NAME}: {COMPANY_ARCHETYPE}."


# ---------------------------------------------------------------------------
# Size parameters
# ---------------------------------------------------------------------------

SIZE_PARAMS: dict[str, dict[str, Any]] = {
    "small": {
        "window_event_count": 6,
        "per_category_target": 5,
        "team_set": ["Engineering"],
    },
    "medium": {
        "window_event_count": 8,
        "per_category_target": 50,
        "team_set": ["Engineering", "Sales", "Product", "Customer Success", "Operations"],
    },
    "large": {
        # Additive on Medium: Large is seeded from the Medium dataset
        # (its middle-year events are the dense core, preserved). Stage B
        # Large generates the OTHER 5 years only — so EV-<year> IDs never
        # collide with Medium's middle-year EV-<middle> IDs (next_seq
        # resets to 1 each run). ~4 events × 5yr × 8team × 2q ≈ 320 new
        # events; with Medium's ~157 → ~480 total (~3x, not 20x —
        # ground-truth grows modestly; volume comes from C2/C3).
        "window_event_count": 4,
        "per_category_target": 80,
        "team_set": ["Engineering", "Sales", "Product", "Customer Success",
                     "Operations", "Marketing", "Finance", "People"],
        "additive_exclude_middle_year": True,
        "quarters": [2, 4],
    },
}


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Canon loading + window selection
# ---------------------------------------------------------------------------


def _load_canon(data_dir: Path) -> dict[str, Any]:
    """Load all Stage A artefacts the Stage B runner needs."""
    canon_dir = data_dir / "helix_canon"

    skeleton = json.loads((canon_dir / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(line)
        for line in (canon_dir / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    customers = [
        json.loads(line)
        for line in (canon_dir / "customers.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    historical_customers: list[dict] = []
    hc_path = canon_dir / "historical_customers.jsonl"
    if hc_path.exists():
        historical_customers = [
            json.loads(line)
            for line in hc_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    depth_arcs_path = canon_dir / "depth_arcs.md"
    depth_arcs = depth_arcs_path.read_text(encoding="utf-8") if depth_arcs_path.exists() else ""

    return {
        "skeleton": skeleton,
        "personas": personas,
        "customers": customers,
        "historical_customers": historical_customers,
        "depth_arcs": depth_arcs,
    }


def _pick_windows(canon: dict, size: str) -> list[tuple[int, int, str]]:
    """Pick the (year, quarter, team) windows to traverse for this size."""
    params = SIZE_PARAMS[size]
    skeleton = canon["skeleton"]
    year_arcs = skeleton["year_arcs"]
    teams = params["team_set"]

    candidate_years = sorted(int(y) for y in year_arcs.keys())

    if size == "small":
        # One mid-period quarter on Engineering. Prefer a year in a
        # medium-or-high discipline era.
        middle = candidate_years[1:-1] if len(candidate_years) > 2 else candidate_years
        eras = skeleton["eras"]
        for y in middle:
            for e in eras:
                start_y = int(e["start"][:4])
                end_y = int(e["end"][:4])
                if start_y <= y <= end_y and e["discipline_level"] in ("medium", "high"):
                    return [(y, 2, teams[0])]
        return [(middle[len(middle) // 2], 2, teams[0])]

    if size == "medium":
        # 1 year × all teams × 4 quarters
        chosen_year = candidate_years[len(candidate_years) // 2]
        return [(chosen_year, q, t) for q in range(1, 5) for t in teams]

    # large (additive): all years EXCEPT the middle one (which Medium
    # already generated as the dense core in the seed). Excluding the
    # middle year guarantees EV-<year> IDs don't collide with Medium's
    # EV-<middle> IDs. Subset of quarters keeps ground-truth growth
    # modest; the token volume comes from C2 atmosphere + C3 depth.
    middle_year = candidate_years[len(candidate_years) // 2]
    quarters = params.get("quarters", [1, 2, 3, 4])
    if params.get("additive_exclude_middle_year"):
        chosen_years = [y for y in candidate_years if y != middle_year]
    else:
        chosen_years = candidate_years
    return [(y, q, t) for y in chosen_years for q in quarters for t in teams]


def _personas_active_in_year(personas: list[dict], year: int) -> list[dict]:
    """Filter personas to those active in the given year."""
    out: list[dict] = []
    for p in personas:
        joined = p.get("joined_year")
        if joined is None:
            continue
        try:
            joined = int(joined)
        except (TypeError, ValueError):
            continue
        if joined > year:
            continue
        left = p.get("left_year")
        if left is not None:
            try:
                left = int(left)
            except (TypeError, ValueError):
                continue
            if left < year:
                continue
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_personas_block(personas: list[dict], limit: int = 25) -> str:
    lines = []
    for p in personas[:limit]:
        role = p.get("role_history", [{}])[0].get("role", "?")
        lines.append(f"- {p['persona_id']} {p.get('display_name', '?')} — {role}")
    return "\n".join(lines) or "(no personas active this window)"


def _format_customers_block(active: list[dict], historical: list[dict], year: int) -> str:
    lines = []
    for c in active:
        fy = c.get("first_year", 0)
        try:
            fy = int(fy)
        except (TypeError, ValueError):
            fy = 0
        if fy <= year:
            lines.append(f"- {c.get('customer_id','?')} {c.get('name','?')} ({c.get('industry','?')})")
    for c in historical:
        try:
            fy = int(c.get("first_year", 0))
            ly = int(c.get("last_year", year + 1))
        except (TypeError, ValueError):
            continue
        if fy <= year <= ly:
            lines.append(
                f"- {c.get('customer_id','?')} {c.get('name','?')} (historical, "
                f"outcome: {c.get('outcome','?')})"
            )
    return "\n".join(lines) or "(no customers relevant this window)"


# ---------------------------------------------------------------------------
# Pass B1 — Master timeline
# ---------------------------------------------------------------------------


_EVENT_BLOCK_RE = re.compile(
    r"##\s+(EV-\d{4}-\d+).*?(?=\n##\s+EV-|\Z)",
    re.DOTALL,
)


def _normalise_category(raw) -> str | None:
    """Normalise a category_target value to C1..C6 or None.

    Accepts strings ("C1", "c2", "C3 (decision provenance)") and stray
    integers / numerics (gpt-oss sometimes copies a count from the
    prompt into this field — we treat any pure-number as ambiguous
    and downgrade to None rather than letting it through schema).
    """
    if raw is None:
        return None
    # Numeric / int-like: not a valid category
    if isinstance(raw, (int, float)):
        return None
    s = str(raw).strip()
    if s.isdigit():
        return None
    s_up = s.upper()
    if s_up in {"C1", "C2", "C3", "C4", "C5", "C6"}:
        return s_up
    if s_up in {"NONE", "N/A", ""}:
        return None
    m = re.match(r"C[1-6]", s_up)
    if m:
        return m.group(0)
    return None


def _parse_event_sketches(text: str) -> list[dict]:
    """Parse B1 output into a list of event-sketch dicts."""
    text = strip_code_fences(text)
    out: list[dict] = []
    for block_match in _EVENT_BLOCK_RE.finditer(text):
        block = block_match.group(0).strip()
        lines = block.splitlines()
        m_id = re.match(r"##\s+(EV-\d{4}-\d+)", lines[0])
        if not m_id:
            continue
        event_id = m_id.group(1)

        fields: dict[str, str] = {}
        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kv = re.match(r"([a-zA-Z_]+)\s*:\s*(.+)$", line)
            if kv:
                fields[kv.group(1).lower().strip()] = kv.group(2).strip()

        parts_raw = fields.get("participants", "")
        parts = [
            p.strip().strip("[],")
            for p in re.split(r"[,\s]+", parts_raw)
            if p.strip().strip("[],")
        ]
        parts = [p for p in parts if re.match(r"^P-\d{4}$", p)]

        sketch = {
            "id": event_id,
            "type": (fields.get("type", "").strip().lower() or "strategic_decision"),
            "occurred_at": fields.get("occurred_at", "").strip(),
            "participants": parts,
            "summary": fields.get("summary", "").strip(),
            "category_target": _normalise_category(fields.get("category_target", "")),
            "_raw_block": block,
        }
        # Capture the corrects_event_id field if present (C3 retroactive
        # corrections, set by B4 gap-fill). Validation that the target
        # event actually exists is deferred to relation-derivation time.
        corrects = fields.get("corrects_event_id", "").strip()
        if corrects:
            m = re.match(r"(EV-\d{4}-\d+)", corrects)
            if m:
                sketch["corrects_event_id"] = m.group(1)
        out.append(sketch)
    return out


async def _pass_b1_window(
    llm: HelixLLM,
    year: int,
    quarter: int,
    team: str,
    canon: dict,
    target_event_count: int,
    next_event_seq: int,
) -> list[dict]:
    """Run B1 for one (year, quarter, team) window. Returns sketches."""
    personas_window = _personas_active_in_year(canon["personas"], year)
    personas_block = _format_personas_block(personas_window)
    customers_block = _format_customers_block(
        canon["customers"], canon["historical_customers"], year,
    )
    depth_arcs_summary = canon["depth_arcs"][:800] if canon["depth_arcs"] else "(none)"

    year_arcs = canon["skeleton"]["year_arcs"]
    year_theme = year_arcs.get(str(year)) or year_arcs.get(year, "(no theme)")

    era = next(
        (e for e in canon["skeleton"]["eras"]
         if int(e["start"][:4]) <= year <= int(e["end"][:4])),
        canon["skeleton"]["eras"][0],
    )

    prompt = _load_template("b1_master_timeline.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        year=year,
        quarter=quarter,
        team=team,
        era_name=era["name"],
        era_discipline_level=era["discipline_level"],
        year_theme=year_theme,
        personas_window_block=personas_block,
        customers_window_block=customers_block,
        depth_arcs_summary=depth_arcs_summary,
        target_event_count=target_event_count,
    )

    text = await llm.call_text(
        stage="B",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=8000,
    )
    sketches = _parse_event_sketches(text)
    for offset, sk in enumerate(sketches):
        sk["id"] = f"EV-{year}-{next_event_seq + offset:03d}"

    logger.info(
        "B1 %d-Q%d %s: %d sketches (target %d)",
        year, quarter, team, len(sketches), target_event_count,
    )
    return sketches


# ---------------------------------------------------------------------------
# Pass B2 — Event expansion
# ---------------------------------------------------------------------------


async def _pass_b2_expand(llm: HelixLLM, sketch: dict, canon: dict) -> dict | None:
    """Expand one B1 sketch into a full YAML Event record."""
    persona_map = {p["persona_id"]: p for p in canon["personas"]}
    participants_block = "\n".join(
        f"- {pid} {persona_map.get(pid, {}).get('display_name', '?')}: "
        f"{persona_map.get(pid, {}).get('role_history', [{}])[0].get('role', '?')}"
        for pid in sketch.get("participants", [])
    ) or "(no participants linked)"

    customer_block = "(no customer in this event)"
    for c in canon["customers"] + canon["historical_customers"]:
        name = c.get("name", "")
        if name and name in sketch.get("summary", ""):
            customer_block = (
                f"- {c.get('customer_id', '?')} {name}: {c.get('industry', '?')}"
            )
            break

    year = int(sketch["id"].split("-")[1])
    year_arcs = canon["skeleton"]["year_arcs"]
    year_arc_block = year_arcs.get(str(year), year_arcs.get(year, "(no arc)"))

    era = next(
        (e for e in canon["skeleton"]["eras"]
         if int(e["start"][:4]) <= year <= int(e["end"][:4])),
        canon["skeleton"]["eras"][0],
    )
    era_block = f"{era['name']} ({era['discipline_level']} discipline): {era['characterisation']}"

    prompt = _load_template("b2_event_expansion.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        year_arc_block=year_arc_block,
        era_block=era_block,
        participants_block=participants_block,
        customer_block=customer_block,
        event_sketch=sketch["_raw_block"],
        event_id=sketch["id"],
    )

    text = await llm.call_text(
        stage="B",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=6000,
    )
    parsed = parse_yaml_lenient(text)
    if not parsed:
        logger.warning("B2 %s: no parseable YAML, retrying once", sketch["id"])
        text2 = await llm.call_text(
            stage="B",
            user=prompt + "\n\nIMPORTANT: emit ONLY the YAML document, no preamble.",
            reasoning_effort="low",
            max_tokens=6000,
        )
        parsed = parse_yaml_lenient(text2)
        if not parsed:
            logger.error("B2 %s: failed twice — skipping", sketch["id"])
            return None

    record = parsed[0]
    record["id"] = sketch["id"]
    if "type" in record and isinstance(record.get("type"), str):
        record["type"] = record["type"].strip().lower()
    record.setdefault("type", sketch["type"])
    record.setdefault("occurred_at", sketch["occurred_at"])
    record.setdefault("summary", sketch["summary"])
    # Re-normalise category_target on the FINAL record. The B4 gapfill
    # prompt's directive format ("- C1: 5 new events") tempts gpt-oss to
    # copy the count (5) into the category_target field. Always run the
    # normaliser on the model's output, then fall back to the sketch.
    record["category_target"] = _normalise_category(record.get("category_target")) or sketch.get("category_target")
    record.setdefault("participants", sketch["participants"])
    record.setdefault("recorded_at", record.get("occurred_at"))
    # Propagate the C3 correction pointer if present
    if sketch.get("corrects_event_id"):
        record["corrects_event_id"] = sketch["corrects_event_id"]

    try:
        Event(**{
            k: v for k, v in record.items()
            if k in {"id", "type", "occurred_at", "recorded_at", "participants",
                     "decision", "reason_canonical", "alternatives_considered",
                     "category_target", "summary", "evidence_in_corpus",
                     "doc_dispersal_pattern"}
        })
    except ValidationError as exc:
        logger.warning("B2 %s: Pydantic validation issues: %s", sketch["id"], str(exc)[:200])

    return record


# ---------------------------------------------------------------------------
# Pass B3 — Cross-event linking
# ---------------------------------------------------------------------------


_B3_CHUNK_SIZE = 50  # events per chunk for the within-chunk linking pass
_B5_CHUNK_SIZE = 80  # events per chunk for the retroactive-correction pass


async def _pass_b5_retroactive_corrections(
    llm: HelixLLM, events: list[dict],
) -> list[dict]:
    """Dedicated pass: ask gpt-oss to find retroactive corrections.

    B3 mentions ``retroactively_corrected_by`` in its closed enum but
    in practice never produces any — gpt-oss tends to default to
    ``supersedes`` or ``caused_by`` when the bi-temporal correction
    concept is one of seven options in a long prompt. Giving it a
    dedicated pass with one-shot definition + examples + explicit
    "≥3 months apart" constraint produces actual results.
    """
    valid_ids = {e["id"] for e in events}
    occurred = {e["id"]: str(e.get("occurred_at", "")) for e in events}

    sorted_events = sorted(events, key=lambda e: str(e.get("occurred_at", "")))
    chunks = [
        sorted_events[i:i + _B5_CHUNK_SIZE]
        for i in range(0, len(sorted_events), _B5_CHUNK_SIZE)
    ]
    logger.info(
        "B5 retroactive-correction probe: %d events → %d chunks",
        len(events), len(chunks),
    )

    all_triples: dict[tuple[str, str, str], None] = {}

    for chunk_idx, chunk in enumerate(chunks):
        events_block = "\n".join(
            f"- {e['id']} ({e.get('type', '?')}, "
            f"{str(e.get('occurred_at', ''))[:10]}): "
            f"{e.get('summary', '?')[:160]}"
            for e in chunk
        )
        prompt = _load_template("b5_retroactive_corrections.md").format(
            events_block=events_block,
        )
        text = await llm.call_text(
            stage="B",
            user=prompt,
            reasoning_effort="medium",  # this IS a reasoning task
            max_tokens=4000,
        )
        if "NO_RETROACTIVE_CORRECTIONS" in text:
            logger.info("B5 chunk %d/%d: no retroactive corrections found", chunk_idx + 1, len(chunks))
            continue
        triples = parse_triples_line(text)

        valid_chunk = 0
        for src, rel, tgt in triples:
            # Force the relation to retroactively_corrected_by even if
            # gpt-oss emitted a different relation in the triple line —
            # this is the dedicated pass for that one relation type.
            if src not in valid_ids or tgt not in valid_ids:
                continue
            # Date ordering: target must be AT LEAST 90 days AFTER source.
            src_d = occurred.get(src, "")
            tgt_d = occurred.get(tgt, "")
            try:
                from datetime import date
                src_date = date.fromisoformat(src_d[:10])
                tgt_date = date.fromisoformat(tgt_d[:10])
                if (tgt_date - src_date).days < 90:
                    continue
            except (ValueError, TypeError):
                continue
            try:
                Relation(
                    source=src,
                    relation=RelationType.RETROACTIVELY_CORRECTED_BY,
                    target=tgt,
                )
            except ValidationError:
                continue
            key = (src, RelationType.RETROACTIVELY_CORRECTED_BY, tgt)
            all_triples[key] = None
            valid_chunk += 1
        logger.info(
            "B5 chunk %d/%d: %d valid retroactive corrections / %d raw triples",
            chunk_idx + 1, len(chunks), valid_chunk, len(triples),
        )

    out = [
        {"source": s, "relation": r, "target": t}
        for (s, r, t) in all_triples.keys()
    ]
    logger.info("B5 complete: %d retroactive-correction edges", len(out))
    return out


async def _pass_b3_link(
    llm: HelixLLM, events: list[dict],
) -> list[dict]:
    """Generate relationship triples across all events.

    Chunks the events list into batches of ~_B3_CHUNK_SIZE for the
    within-chunk linking calls (gpt-oss returns zero output when fed
    all 163 Medium events in one shot — too many candidate pairs to
    reason over, reasoning channel exhausts the output budget).

    After per-chunk passes, runs one cross-chunk pass with only
    compact event IDs + summaries to catch supersession chains and
    contradictions that span chunks (e.g. a 2024 ADR superseding a
    2022 ADR — they fall in different temporal chunks).
    """
    valid_ids = {e["id"] for e in events}
    occurred = {e["id"]: str(e.get("occurred_at", "")) for e in events}
    valid_rels = RelationType.all()

    # Relation date-ordering rules:
    # - "source replaces target": source must be LATER than target.
    #   Edges: supersedes, reverses, re_attempts, resolved_by, caused_by
    #   (A caused_by B → B is the cause = earlier; A is the effect = later).
    # - "source corrected by target": target must be LATER than source.
    #   Edges: retroactively_corrected_by (A corrected by B → A is older,
    #   B is the later correction).
    # - No ordering: contradicts (two parties can disagree at any time
    #   relative to each other).
    _SOURCE_AFTER_TARGET = {
        RelationType.SUPERSEDES, RelationType.REVERSES,
        RelationType.RE_ATTEMPTS, RelationType.RESOLVED_BY,
        RelationType.CAUSED_BY,
    }
    _TARGET_AFTER_SOURCE = {
        RelationType.RETROACTIVELY_CORRECTED_BY,
    }

    def _filter_triples(triples: list[tuple[str, str, str]]) -> list[dict]:
        out: list[dict] = []
        for src, rel, tgt in triples:
            if src not in valid_ids or tgt not in valid_ids:
                continue
            if rel not in valid_rels:
                continue
            if rel in _SOURCE_AFTER_TARGET:
                if occurred[src] and occurred[tgt] and occurred[src] <= occurred[tgt]:
                    continue
            elif rel in _TARGET_AFTER_SOURCE:
                if occurred[src] and occurred[tgt] and occurred[src] >= occurred[tgt]:
                    continue
            try:
                Relation(source=src, relation=rel, target=tgt)
            except ValidationError:
                continue
            out.append({"source": src, "relation": rel, "target": tgt})
        return out

    # Sort events chronologically so each chunk represents a coherent
    # time slice — supersession chains within a chunk get caught here;
    # the cross-chunk pass picks up the longer chains.
    sorted_events = sorted(events, key=lambda e: str(e.get("occurred_at", "")))
    chunks = [
        sorted_events[i:i + _B3_CHUNK_SIZE]
        for i in range(0, len(sorted_events), _B3_CHUNK_SIZE)
    ]
    logger.info(
        "B3 linking: %d events → %d chunks of ~%d each",
        len(events), len(chunks), _B3_CHUNK_SIZE,
    )

    all_triples: dict[tuple[str, str, str], None] = {}

    # --- Within-chunk passes ---
    for chunk_idx, chunk in enumerate(chunks):
        events_block = "\n".join(
            f"- {e['id']} ({e.get('type', '?')}, {e.get('occurred_at', '?')}): "
            f"{e.get('summary', '?')[:140]}"
            for e in chunk
        )
        expected_count = len(chunk)
        expected_relations = max(2, expected_count // 4)
        prompt = _load_template("b3_cross_event_linking.md").format(
            company_one_liner=COMPANY_ONE_LINER,
            events_block=events_block,
            expected_count=expected_count,
            expected_relations=expected_relations,
        )
        # reasoning_effort=low + selectivity directive in the prompt.
        # v0.3-experiment-1: medium effort burned the 8000-token output
        # budget on reasoning and emitted 0 triples even at Small.
        # v0.2's low-effort produced 264 raw / 153 valid (58% raw→valid,
        # 97% within-chunk), so the edge quality was fine — the
        # downstream C1 question quality issue was about supersedes
        # semantics in the EVENTS, not the linking pass itself.
        selective_prompt = prompt + (
            "\n\nIMPORTANT — be SELECTIVE. Only emit a triple if BOTH "
            "events satisfy the relation's strict criteria with high "
            "confidence. Better to skip a borderline pair than to "
            "emit a weak edge. Quality > quantity."
        )
        text = await llm.call_text(
            stage="B",
            user=selective_prompt,
            reasoning_effort="low",
            max_tokens=8000,
        )
        chunk_triples = parse_triples_line(text)
        valid = _filter_triples(chunk_triples)
        for t in valid:
            all_triples[(t["source"], t["relation"], t["target"])] = None
        logger.info(
            "B3 chunk %d/%d: %d valid / %d raw triples",
            chunk_idx + 1, len(chunks), len(valid), len(chunk_triples),
        )

    # --- Cross-chunk pass (if multiple chunks) ---
    # Feed ONLY compact IDs + dates + 60-char summaries so the prompt
    # stays small enough that gpt-oss can return content. This pass
    # specifically targets long-range supersession chains and
    # cross-year contradictions that within-chunk passes miss.
    if len(chunks) > 1:
        compact_block = "\n".join(
            f"- {e['id']} {str(e.get('occurred_at', ''))[:10]} "
            f"({e.get('type', '?')}): {e.get('summary', '?')[:60]}"
            for e in sorted_events
        )
        cross_prompt = _load_template("b3_cross_event_linking.md").format(
            company_one_liner=COMPANY_ONE_LINER,
            events_block=compact_block,
            expected_count=len(sorted_events),
            expected_relations=max(5, len(sorted_events) // 8),
        )
        cross_prompt += (
            "\n\nFOCUS ON LONG-RANGE RELATIONSHIPS: this pass exists to "
            "catch supersession chains and contradictions that span "
            "different years. Within-year edges have already been "
            "captured; emit ONLY triples where source and target are "
            "in different calendar years.\n"
        )
        text = await llm.call_text(
            stage="B",
            user=cross_prompt,
            reasoning_effort="low",
            max_tokens=8000,
        )
        cross_triples = parse_triples_line(text)
        cross_valid = _filter_triples(cross_triples)
        new_cross = 0
        for t in cross_valid:
            key = (t["source"], t["relation"], t["target"])
            if key not in all_triples:
                all_triples[key] = None
                new_cross += 1
        logger.info(
            "B3 cross-chunk pass: %d valid / %d raw; %d new beyond chunks",
            len(cross_valid), len(cross_triples), new_cross,
        )

    out = [
        {"source": s, "relation": r, "target": t}
        for (s, r, t) in all_triples.keys()
    ]
    logger.info(
        "B3 cross-event linking complete: %d valid triples / %d events",
        len(out), len(events),
    )
    return out


# ---------------------------------------------------------------------------
# Pass B4 — Coverage gap-fill
# ---------------------------------------------------------------------------


def _compute_coverage(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for e in events:
        tgt = e.get("category_target")
        if tgt:
            counts[tgt] += 1
    return dict(counts)


async def _pass_b4_gapfill(
    llm: HelixLLM,
    events: list[dict],
    canon: dict,
    per_category_target: int,
    next_event_seq: int,
) -> list[dict]:
    """Generate event sketches for under-target categories."""
    coverage = _compute_coverage(events)
    targets = {f"C{i}": per_category_target for i in range(1, 7)}
    gaps = {
        cat: targets[cat] - coverage.get(cat, 0)
        for cat in targets
        if targets[cat] > coverage.get(cat, 0)
    }
    if not gaps:
        logger.info("B4: per-category coverage already meets target (%s)", per_category_target)
        return []

    total_to_generate = min(sum(gaps.values()), 20)
    gapfill_directives = []
    remaining = total_to_generate
    for cat, gap in sorted(gaps.items(), key=lambda kv: -kv[1]):
        ask = min(gap, max(1, remaining // max(1, len(gaps))))
        ask = min(ask, remaining)
        if ask <= 0:
            continue
        # Phrase the directive so gpt-oss can't mistake the count for
        # the category code. Old format "- C1: 5 new events" tempted
        # the model to emit `category_target: 5` instead of
        # `category_target: C1`. New format puts the category code in
        # a clearly-labelled output-value slot.
        gapfill_directives.append(
            f"- Generate {ask} new events with `category_target: {cat}` "
            f"(currently {coverage.get(cat, 0)}/{targets[cat]}). "
            f"Write the literal string `{cat}` in the category_target field."
        )
        remaining -= ask

    coverage_block = "\n".join(
        f"- {cat}: {coverage.get(cat, 0)} / {targets[cat]}"
        for cat in sorted(targets)
    )
    targets_block = "\n".join(f"- {cat}: {targets[cat]}" for cat in sorted(targets))
    events_summary_block = "\n".join(
        f"- {e['id']} ({e.get('category_target', 'none')}, {e.get('occurred_at', '?')}): "
        f"{e.get('summary', '?')[:100]}"
        for e in events[-30:]
    )
    relations_summary_block = "(no relations yet)"
    personas_summary = "\n".join(
        f"- {p['persona_id']} {p.get('display_name', '?')}"
        for p in canon["personas"][:30]
    )
    customers_summary = "\n".join(
        f"- {c.get('customer_id', '?')} {c.get('name', '?')}"
        for c in canon["customers"] + canon["historical_customers"]
    )

    skeleton = canon["skeleton"]
    min_year = skeleton["founding_year"]
    max_year = CURRENT_YEAR - 1

    prompt = _load_template("b4_coverage_gapfill.md").format(
        coverage_block=coverage_block,
        targets_block=targets_block,
        events_summary_block=events_summary_block,
        relations_summary_block=relations_summary_block,
        personas_summary=personas_summary,
        customers_summary=customers_summary,
        gapfill_directives_block="\n".join(gapfill_directives),
        min_year=min_year,
        max_year=max_year,
    )

    text = await llm.call_text(
        stage="B",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=10000,
    )
    sketches = _parse_event_sketches(text)
    for offset, sk in enumerate(sketches):
        try:
            y = int(sk["occurred_at"][:4])
        except (ValueError, IndexError):
            y = max_year
        sk["id"] = f"EV-{y}-{next_event_seq + offset:03d}"

    logger.info("B4: generated %d gap-fill sketches across categories %s",
                len(sketches), list(gaps.keys()))
    return sketches


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Run all four passes of Stage B."""
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size: {size}; expected one of {list(SIZE_PARAMS)}")
    params = SIZE_PARAMS[size]

    data_root = Path(data_dir)
    out_dir = data_root / "source_of_truth"
    out_dir.mkdir(parents=True, exist_ok=True)

    events_file = out_dir / "events.jsonl"
    relations_file = out_dir / "relations.jsonl"
    coverage_file = out_dir / "coverage_report.json"

    cp_b1 = Checkpoint(out_dir / ".checkpoints" / "b1.jsonl")
    cp_b2 = Checkpoint(out_dir / ".checkpoints" / "b2.jsonl")
    cp_b3 = Checkpoint(out_dir / ".checkpoints" / "b3.jsonl")
    cp_b4 = Checkpoint(out_dir / ".checkpoints" / "b4.jsonl")

    canon = _load_canon(data_root)
    windows = _pick_windows(canon, size)
    logger.info("Stage B starting: size=%s, %d window(s)", size, len(windows))

    llm = HelixLLM()
    try:
        # ----- B1: sketches across all windows -----
        all_sketches: list[dict] = []
        next_seq = 1
        for year, quarter, team in windows:
            unit_id = f"b1-{year}-Q{quarter}-{team}"
            if cp_b1.is_done(unit_id):
                logger.info("B1 %s already done, skipping", unit_id)
                continue
            sketches = await _pass_b1_window(
                llm, year, quarter, team, canon,
                target_event_count=params["window_event_count"],
                next_event_seq=next_seq,
            )
            all_sketches.extend(sketches)
            next_seq += max(len(sketches), 1)
            cp_b1.mark_done(unit_id, sketch_count=len(sketches))

        sketches_path = out_dir / "b1_sketches.jsonl"
        if all_sketches:
            with sketches_path.open("a", encoding="utf-8") as f:
                for sk in all_sketches:
                    f.write(json.dumps(sk, default=str) + "\n")

        # ----- B2: expand each sketch -----
        events: list[dict] = []
        if events_file.exists():
            events = [
                json.loads(line)
                for line in events_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            logger.info("B2: %d events already on disk", len(events))

        for sk in all_sketches:
            unit_id = f"b2-{sk['id']}"
            if cp_b2.is_done(unit_id):
                continue
            record = await _pass_b2_expand(llm, sk, canon)
            if record is None:
                cp_b2.mark_done(unit_id, status="skipped")
                continue
            events.append(record)
            with events_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp_b2.mark_done(unit_id, status="ok")
            logger.info("B2 expanded %s (total events: %d)", sk["id"], len(events))

        # ----- B4: coverage gap-fill (before B3 so links span the final set) -----
        if not cp_b4.is_done("b4-gapfill"):
            extra = await _pass_b4_gapfill(
                llm, events, canon,
                per_category_target=params["per_category_target"],
                next_event_seq=next_seq,
            )
            for sk in extra:
                record = await _pass_b2_expand(llm, sk, canon)
                if record is None:
                    continue
                events.append(record)
                with events_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
            cp_b4.mark_done("b4-gapfill", new_events=len(extra))

        # ----- B3: link across the final event set -----
        cp_b5 = Checkpoint(out_dir / ".checkpoints" / "b5.jsonl")
        relations: list[dict] = []
        if cp_b3.is_done("b3-link") and relations_file.exists():
            relations = [
                json.loads(line)
                for line in relations_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            logger.info("B3 already done; %d relations on disk", len(relations))
        else:
            relations = await _pass_b3_link(llm, events)
            with relations_file.open("w", encoding="utf-8") as f:
                for r in relations:
                    f.write(json.dumps(r, default=str) + "\n")
            cp_b3.mark_done("b3-link", relation_count=len(relations))

        # ----- B5: dedicated retroactive-correction probe -----
        # Runs AFTER B3 so we add to the relations rather than replace.
        # B3's prompt mentions retroactively_corrected_by but rarely
        # produces it; B5 is targeted at that one relation type.
        if not cp_b5.is_done("b5-retroactive"):
            retro = await _pass_b5_retroactive_corrections(llm, events)
            # Append to relations_file + in-memory list
            with relations_file.open("a", encoding="utf-8") as f:
                for r in retro:
                    f.write(json.dumps(r, default=str) + "\n")
            relations.extend(retro)
            cp_b5.mark_done("b5-retroactive", relation_count=len(retro))
        else:
            logger.info("B5 already done; skipping")

        # ----- Code-derived relations from event fields -----
        # When an event's record carries `corrects_event_id` (set by B4
        # gap-fill for C3 events), derive a retroactively_corrected_by
        # edge from the corrected event → this correction. This is a
        # deterministic edge — no LLM call required — and ensures C3
        # gets links even when B5 fails to identify them by inference.
        valid_ids = {e["id"] for e in events}
        derived_edges: list[dict] = []
        seen_edges = {(r["source"], r["relation"], r["target"]) for r in relations}
        for e in events:
            target_id = e.get("corrects_event_id")
            if not target_id or target_id not in valid_ids:
                continue
            src = target_id  # the OLDER event being corrected
            tgt = e["id"]    # the LATER correcting event
            key = (src, RelationType.RETROACTIVELY_CORRECTED_BY, tgt)
            if key in seen_edges:
                continue
            try:
                Relation(source=src, relation=key[1], target=tgt)
            except ValidationError:
                continue
            derived_edges.append({"source": src, "relation": key[1], "target": tgt})
            seen_edges.add(key)
        if derived_edges:
            with relations_file.open("a", encoding="utf-8") as f:
                for r in derived_edges:
                    f.write(json.dumps(r, default=str) + "\n")
            relations.extend(derived_edges)
            logger.info(
                "B-derived: %d retroactively_corrected_by edges from event "
                "`corrects_event_id` fields", len(derived_edges),
            )

        # ----- Coverage report -----
        coverage = _compute_coverage(events)
        per_year: dict[str, int] = defaultdict(int)
        for e in events:
            occ = e.get("occurred_at")
            if occ is None:
                continue
            # YAML parsing may emit a datetime.date object; stringify
            # before slicing the year.
            year_str = str(occ)[:4]
            if year_str.isdigit():
                per_year[year_str] += 1
        report = {
            "size": size,
            "total_events": len(events),
            "per_category": coverage,
            "per_year": dict(per_year),
            "total_relations": len(relations),
            "per_category_target": params["per_category_target"],
        }
        coverage_file.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

        logger.info(
            "Stage B complete. events=%d relations=%d per_category=%s",
            len(events), len(relations), coverage,
        )
    finally:
        await llm.aclose()
