"""Stage D — Cross-reference + noise injection.

Per design doc §8: this stage is **mostly rule-driven**. It walks the
source-of-truth graph's relationship edges (relations.jsonl) and, for
each edge, either:

1. **Inserts a cross-reference** into an artefact associated with the
   source event, pointing at an artefact associated with the target
   event. gpt-oss generates only the short phrase that goes inline
   (5-30 words, genre-appropriate).
2. **Injects a stale citation** when a `supersedes` edge means a later
   artefact should plausibly cite the superseded original AS IF IT
   WERE CURRENT — the §4.2 dispersal noise mechanism that gives the
   benchmark its bite.

The corpus is augmented in place (appending a "## Cross-references"
section to existing artefact files), and a manifest
``noise_manifest.jsonl`` records every insertion for downstream
evidence-trail computation.

Outputs under ``data/``:

* ``corpus/<event_id>/<slot_id>.md`` — modified with appended refs.
* ``noise_manifest.jsonl`` — one record per insertion.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM

logger = logging.getLogger("helix_corpus.stage_d")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_d"


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Loading + lookups
# ---------------------------------------------------------------------------


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    sot_dir = data_dir / "source_of_truth"
    canon_dir = data_dir / "helix_canon"

    events = [
        json.loads(line)
        for line in (sot_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    relations = [
        json.loads(line)
        for line in (sot_dir / "relations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    personas = [
        json.loads(line)
        for line in (canon_dir / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    skeleton = json.loads((canon_dir / "skeleton.json").read_text(encoding="utf-8"))

    corpus_index: list[dict] = []
    idx_path = data_dir / "corpus_index.jsonl"
    if idx_path.exists():
        corpus_index = [
            json.loads(line)
            for line in idx_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    return {
        "events": events,
        "events_by_id": {e["id"]: e for e in events},
        "relations": relations,
        "personas": personas,
        "persona_by_id": {p["persona_id"]: p for p in personas},
        "skeleton": skeleton,
        "corpus_index": corpus_index,
    }


def _artefacts_for_event(corpus_index: list[dict], event_id: str) -> list[dict]:
    return [r for r in corpus_index if r["event_id"] == event_id]


def _era_for(year: int, eras: list[dict]) -> dict[str, Any]:
    for e in eras:
        try:
            start = int(e["start"][:4])
            end = int(e["end"][:4])
        except (KeyError, ValueError, IndexError):
            continue
        if start <= year <= end:
            return e
    return eras[0] if eras else {"name": "?", "discipline_level": "medium"}


# ---------------------------------------------------------------------------
# Cross-reference injection
# ---------------------------------------------------------------------------


async def _generate_cross_ref(
    llm: HelixLLM,
    relation: dict,
    source_artefact: dict,
    target_artefact: dict,
    inputs: dict,
) -> str | None:
    """One LLM call → one cross-reference phrase."""
    src_evt = inputs["events_by_id"].get(source_artefact["event_id"], {})
    tgt_evt = inputs["events_by_id"].get(target_artefact["event_id"], {})

    src_author = inputs["persona_by_id"].get(source_artefact.get("author", ""), {})
    skeleton = inputs["skeleton"]
    try:
        src_year = int(str(src_evt.get("occurred_at", ""))[:4])
    except (ValueError, TypeError):
        src_year = 2024
    era = _era_for(src_year, skeleton.get("eras", []))

    prompt = _load_template("cross_reference_phrase.md").format(
        source_genre=source_artefact.get("genre", "?"),
        source_author_name=src_author.get("display_name", source_artefact.get("author", "?")),
        source_event_summary=src_evt.get("summary", "?")[:200],
        source_date=str(src_evt.get("occurred_at", "?")),
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        target_genre=target_artefact.get("genre", "?"),
        target_event_summary=tgt_evt.get("summary", "?")[:200],
        target_date=str(tgt_evt.get("occurred_at", "?")),
        target_slot_id=target_artefact.get("slot_id", "?"),
        relation_type=relation.get("relation", "?"),
    )
    text = await llm.call_text(
        stage="D",
        user=prompt,
        reasoning_effort="low",
        max_tokens=400,
    )
    # Take just the first non-empty line — phrase should be inline-sized.
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("```"):
            return line
    return None


async def _generate_stale_citation(
    llm: HelixLLM,
    source_artefact: dict,
    stale_target_artefact: dict,
    superseder_event: dict,
    inputs: dict,
) -> str | None:
    """One LLM call → one stale-citation phrase."""
    src_evt = inputs["events_by_id"].get(source_artefact["event_id"], {})
    tgt_evt = inputs["events_by_id"].get(stale_target_artefact["event_id"], {})
    src_author = inputs["persona_by_id"].get(source_artefact.get("author", ""), {})

    prompt = _load_template("stale_citation.md").format(
        source_genre=source_artefact.get("genre", "?"),
        source_author_name=src_author.get("display_name", source_artefact.get("author", "?")),
        source_event_summary=src_evt.get("summary", "?")[:200],
        source_date=str(src_evt.get("occurred_at", "?")),
        target_genre=stale_target_artefact.get("genre", "?"),
        target_event_summary=tgt_evt.get("summary", "?")[:200],
        target_date=str(tgt_evt.get("occurred_at", "?")),
        superseder_event_summary=superseder_event.get("summary", "?")[:200],
        superseder_date=str(superseder_event.get("occurred_at", "?")),
    )
    text = await llm.call_text(
        stage="D",
        user=prompt,
        reasoning_effort="low",
        max_tokens=400,
    )
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("```"):
            return line
    return None


def _append_section(path: Path, header: str, body: str) -> None:
    """Append a section to an existing artefact file."""
    existing = path.read_text(encoding="utf-8").rstrip()
    sep = "\n\n---\n\n" if not existing.endswith("---") else "\n\n"
    new_block = f"{header}\n{body}\n"
    path.write_text(existing + sep + new_block, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Run Stage D — rule-driven cross-refs + stale citations."""
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)
    noise_manifest_path = data_root / "noise_manifest.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_d.jsonl")

    llm = HelixLLM()
    inserted_xrefs = 0
    inserted_stale = 0

    try:
        # --- Pass 1: cross-references from relationship edges ---
        for rel in inputs["relations"]:
            source_evt = inputs["events_by_id"].get(rel["source"])
            target_evt = inputs["events_by_id"].get(rel["target"])
            if not source_evt or not target_evt:
                continue

            src_artefacts = _artefacts_for_event(inputs["corpus_index"], rel["source"])
            tgt_artefacts = _artefacts_for_event(inputs["corpus_index"], rel["target"])
            if not src_artefacts or not tgt_artefacts:
                continue

            # Pick the source's PRIMARY artefact (most authoritative slot)
            # to host the cross-reference; pick any target artefact to point at.
            src_primary = next(
                (a for a in src_artefacts if a.get("role") == "primary"),
                src_artefacts[0],
            )
            tgt_primary = next(
                (a for a in tgt_artefacts if a.get("role") == "primary"),
                tgt_artefacts[0],
            )

            unit_id = f"xref-{rel['source']}->{rel['target']}-{rel['relation']}"
            if cp.is_done(unit_id):
                continue

            phrase = await _generate_cross_ref(llm, rel, src_primary, tgt_primary, inputs)
            if not phrase:
                logger.warning("Stage D xref %s: empty phrase", unit_id)
                cp.mark_done(unit_id, status="empty")
                continue

            # Append the cross-reference section to the source artefact
            art_path = data_root / src_primary["path"]
            _append_section(art_path, "## Cross-references", f"- ({rel['relation']}) {phrase}")

            # Manifest entry
            record = {
                "kind": "cross_reference",
                "source_artefact": src_primary["slot_id"],
                "source_path": src_primary["path"],
                "target_artefact": tgt_primary["slot_id"],
                "target_path": tgt_primary["path"],
                "relation": rel["relation"],
                "phrase": phrase,
            }
            with noise_manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp.mark_done(unit_id, status="ok", phrase=phrase[:120])
            inserted_xrefs += 1
            logger.info(
                "Stage D xref %s [%s] -> %s",
                src_primary["slot_id"], rel["relation"], tgt_primary["slot_id"],
            )

        # --- Pass 2: stale citations for supersession chains ---
        # For each `supersedes` edge: the TARGET (older) event is the stale
        # reference. Pick an artefact from AFTER the superseder's date and
        # have it cite the stale event as if it were current.
        for rel in inputs["relations"]:
            if rel["relation"] not in ("supersedes", "reverses"):
                continue
            superseder_evt = inputs["events_by_id"].get(rel["source"])
            stale_target_evt = inputs["events_by_id"].get(rel["target"])
            if not superseder_evt or not stale_target_evt:
                continue

            # Find candidate "later" artefacts that could plausibly cite
            # the stale doc — anything dated AFTER the superseder.
            superseder_date_str = str(superseder_evt.get("occurred_at", ""))[:10]
            later_artefacts = [
                a for a in inputs["corpus_index"]
                if str(inputs["events_by_id"].get(a["event_id"], {}).get("occurred_at", ""))[:10]
                > superseder_date_str
                and a["event_id"] not in (rel["source"], rel["target"])
            ]
            if not later_artefacts:
                continue

            # Pick a secondary artefact (less central) — stale citations
            # most often appear in onboarding docs, customer emails, etc,
            # not in primary canonical docs.
            host = next(
                (a for a in later_artefacts if a.get("role") == "secondary"),
                later_artefacts[0],
            )
            stale_target_arts = _artefacts_for_event(inputs["corpus_index"], rel["target"])
            if not stale_target_arts:
                continue
            stale_target = stale_target_arts[0]

            unit_id = f"stale-{rel['target']}-in-{host['slot_id']}"
            if cp.is_done(unit_id):
                continue

            phrase = await _generate_stale_citation(
                llm, host, stale_target, superseder_evt, inputs,
            )
            if not phrase:
                logger.warning("Stage D stale %s: empty phrase", unit_id)
                cp.mark_done(unit_id, status="empty")
                continue

            art_path = data_root / host["path"]
            _append_section(art_path, "## Background", phrase)

            record = {
                "kind": "stale_citation",
                "host_artefact": host["slot_id"],
                "host_path": host["path"],
                "stale_target_artefact": stale_target["slot_id"],
                "stale_target_event": rel["target"],
                "superseder_event": rel["source"],
                "phrase": phrase,
            }
            with noise_manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp.mark_done(unit_id, status="ok", phrase=phrase[:120])
            inserted_stale += 1
            logger.info(
                "Stage D stale-citation in %s [cites stale %s; actually superseded by %s]",
                host["slot_id"], rel["target"], rel["source"],
            )

        logger.info(
            "Stage D complete. %d cross-references + %d stale citations inserted.",
            inserted_xrefs, inserted_stale,
        )
    finally:
        await llm.aclose()
