"""Stage C — Corpus generation.

The bulk-volume stage. For each event in the source-of-truth graph,
walk its ``evidence_in_corpus[]`` slot list and generate the actual
artefact text for each slot, via a per-genre prompt template
parameterised by:

- the artefact's genre (slack_thread, adr, meeting_notes, etc.)
- the author's persona profile (voice markers, signature phrases)
- the window's tooling context + doc-discipline era
- the event's canonical facts (decision, reason, participants) as a
  hard constraint
- the artefact's role (primary / secondary / noise) in the evidence trail

Outputs under ``data/corpus/``:

* ``<event_id>/<slot_id>.md`` — one Markdown file per artefact.
* ``corpus_index.jsonl`` — one record per artefact mapping it to its
  source-of-truth event ID and role.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM

logger = logging.getLogger("helix_corpus.stage_c")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c"
CURRENT_YEAR = 2026
COMPANY_NAME = "Helix Logistics"
COMPANY_ARCHETYPE = (
    "B2B SaaS for mid-market freight-forwarding companies, "
    "founded in 2020, ~85 employees by 2025"
)
COMPANY_ONE_LINER = f"{COMPANY_NAME}: {COMPANY_ARCHETYPE}."


SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"max_artefacts_per_event": 4, "background_per_event": 3,  "max_total": 200},
    "medium": {"max_artefacts_per_event": 5, "background_per_event": 10, "max_total": 4000},
    "large":  {"max_artefacts_per_event": 6, "background_per_event": 25, "max_total": 55000},
}


# Genre → template filename + per-genre output token target.
# Templates have been calibrated for gpt-oss output sizes:
GENRE_TEMPLATES: dict[str, dict[str, Any]] = {
    "slack_thread":         {"file": "slack_thread.md",        "max_tokens": 3000},
    "meeting_notes":        {"file": "meeting_notes.md",       "max_tokens": 3000},
    "meeting_transcript":   {"file": "meeting_transcript.md",  "max_tokens": 6000},
    "adr":                  {"file": "adr.md",                 "max_tokens": 4000},
    "rfc":                  {"file": "rfc.md",                 "max_tokens": 4000},
    "retrospective":        {"file": "retrospective.md",       "max_tokens": 3000},
    "postmortem":           {"file": "postmortem.md",          "max_tokens": 5000},
    "email_thread":         {"file": "email_thread.md",        "max_tokens": 3000},
    "customer_call_notes":  {"file": "customer_call_notes.md", "max_tokens": 3000},
    "sales_crm_entry":      {"file": "sales_crm_entry.md",     "max_tokens": 1500},
    "notion_doc":           {"file": "notion_doc.md",          "max_tokens": 4000},
    "incident_report":      {"file": "incident_report.md",     "max_tokens": 3000},
}

# Aliases so common genre tokens map to the right template
_GENRE_ALIASES: dict[str, str] = {
    "slack": "slack_thread",
    "notion": "notion_doc",
    "transcript": "meeting_transcript",
    "notes": "meeting_notes",
    "crm": "sales_crm_entry",
    "email": "email_thread",
    "call": "customer_call_notes",
    "post-mortem": "postmortem",
    "ticket": "sales_crm_entry",  # fallback
}


# Genre → testimony-type mapping (matches Stage E's _testimony_type
# heuristic). Lets us prefix every artefact with an explicit testimony
# marker the C5 answerer can read.
_GENRE_TESTIMONY_TYPE: dict[str, str] = {
    # Direct testimony: people speaking in their own voice in real time
    "slack_thread": "direct",
    "meeting_transcript": "direct",
    "email_thread": "direct",
    "customer_call_transcript": "direct",
    # Inference: summarising or interpreting what others said/decided
    "postmortem": "inferred",
    "retrospective": "inferred",
    "adr": "inferred",
    "rfc": "inferred",
    "notion_doc": "inferred",
    "incident_report": "inferred",
    "meeting_notes": "inferred",
    "customer_call_notes": "inferred",
    "sales_crm_entry": "inferred",
}


def _testimony_header(genre: str, slot_id: str, author: str, event_id: str, role: str) -> str:
    """A short metadata block prefixed to every generated artefact.

    Carries the testimony-type classification + provenance so the
    answerer in Stage F can read it from the artefact body. Format is
    HTML-comment style so it doesn't interfere with the human-readable
    Markdown that follows.
    """
    testimony = _GENRE_TESTIMONY_TYPE.get(genre, "direct")
    return (
        f"<!-- artefact_metadata\n"
        f"slot_id: {slot_id}\n"
        f"event_id: {event_id}\n"
        f"genre: {genre}\n"
        f"role: {role}\n"
        f"author: {author}\n"
        f"testimony_type: {testimony}\n"
        f"-->\n\n"
    )


def _resolve_genre(raw: str) -> str:
    """Normalise a slot's genre string to a template key."""
    if not raw:
        return "slack_thread"
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if key in GENRE_TEMPLATES:
        return key
    if key in _GENRE_ALIASES:
        return _GENRE_ALIASES[key]
    # Try partial match
    for k in GENRE_TEMPLATES:
        if k in key or key in k:
            return k
    return "slack_thread"  # default


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


_SHARED_HEADER = _load_template("_shared_header.md")


# ---------------------------------------------------------------------------
# Loading + indexing
# ---------------------------------------------------------------------------


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    sot_dir = data_dir / "source_of_truth"
    events = [
        json.loads(line)
        for line in (sot_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    canon_dir = data_dir / "helix_canon"
    skeleton = json.loads((canon_dir / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(line)
        for line in (canon_dir / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "events": events,
        "skeleton": skeleton,
        "personas": personas,
        "persona_by_id": {p["persona_id"]: p for p in personas},
    }


def _tooling_active_in(year: int, tooling_timeline: list[dict]) -> list[str]:
    """Return tooling adopted by ``year``."""
    active: dict[str, str] = {}
    for t in sorted(tooling_timeline, key=lambda x: (x["year"], x.get("quarter") or 1)):
        if int(t["year"]) > year:
            break
        # Description often includes a "replaced X" parenthetical — keep latest per
        # category by overwriting. Without explicit category we just collect.
        active[t["description"]] = t["description"]
    return list(active.values())


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
# Per-artefact generation
# ---------------------------------------------------------------------------


def _format_voice_markers(p: dict) -> str:
    vm = p.get("voice_markers", {}) or {}
    return (
        f"hedging={vm.get('hedging_frequency','?')}, "
        f"formality={vm.get('formality','?')}, "
        f"emoji={vm.get('emoji_use','?')}, "
        f"typical_length={vm.get('typical_message_length_words','?')} words, "
        f"writes_long_docs={vm.get('writes_long_docs','?')}"
    )


def _format_signature_phrases(p: dict) -> str:
    phrases = p.get("signature_phrases", []) or []
    return "; ".join(f'"{x}"' for x in phrases[:5]) or "(none recorded)"


def _build_shared_header(
    event: dict,
    slot: dict,
    author: dict,
    skeleton: dict,
    canon: dict | None = None,
) -> str:
    """Render the shared-header preamble inserted into every genre prompt."""
    occurred = str(event.get("occurred_at", ""))
    try:
        year = int(occurred[:4])
    except (ValueError, TypeError):
        year = CURRENT_YEAR

    era = _era_for(year, skeleton.get("eras", []))
    tooling = _tooling_active_in(year, skeleton.get("tooling", []))

    participants_block = ", ".join(event.get("participants", []))

    base = _SHARED_HEADER.format(
        company_one_liner=COMPANY_ONE_LINER,
        year=year,
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        tooling_active="; ".join(tooling) or "(none)",
        event_id=event.get("id", "?"),
        event_type=event.get("type", "?"),
        event_date=occurred,
        event_decision=str(event.get("decision", ""))[:600],
        event_reason=str(event.get("reason_canonical", ""))[:400],
        participants_names=participants_block or "(none)",
        author_id=author.get("persona_id", "?"),
        author_name=author.get("display_name", "?"),
        author_role=(author.get("role_history") or [{}])[0].get("role", "?"),
        author_voice_markers=_format_voice_markers(author),
        author_signature_phrases=_format_signature_phrases(author),
        role=slot.get("role", "primary"),
        slot_id=slot.get("slot_id", "?"),
    )

    # C3 BI-TEMPORAL EXPANSION: when this event corrects an earlier one,
    # explicitly add the prior event's context so the corpus artefact
    # narrates BOTH the original recorded understanding AND the
    # correction (with dates). Without this, C3 corpus artefacts only
    # state the correction half — the answerer can't recover what was
    # originally believed or when.
    corrects_id = event.get("corrects_event_id")
    if corrects_id and canon:
        events_by_id = {e["id"]: e for e in canon.get("events", [])}
        prior = events_by_id.get(corrects_id)
        if prior:
            base += (
                "\n\n## RETROACTIVE-CORRECTION CONTEXT (C3 — bi-temporal)\n\n"
                f"This event RETROACTIVELY CORRECTS the recorded understanding "
                f"of an earlier event:\n"
                f"  - Prior event ID: {corrects_id}\n"
                f"  - Prior event date: {prior.get('occurred_at', '?')}\n"
                f"  - Original recorded understanding (what we believed at "
                f"  {prior.get('occurred_at', '?')}): "
                f"{str(prior.get('decision', ''))[:400]}\n"
                f"  - Correction (what we now believe, as of "
                f"  {occurred}): {str(event.get('decision', ''))[:400]}\n\n"
                "Your generated artefact MUST narrate BOTH timelines: state "
                "what was originally believed (with the prior date) AND the "
                "correction (with this event's date). Use explicit language "
                "like 'previously we believed X' / 'we now understand Y' / "
                "'as of [date] the correct account is Z'. The reader must be "
                "able to recover both states + both dates from this artefact "
                "alone."
            )
    return base


async def _generate_artefact(
    llm: HelixLLM,
    event: dict,
    slot: dict,
    canon: dict,
) -> str:
    """One LLM call → one artefact body. Returns the raw artefact text."""
    genre = _resolve_genre(slot.get("genre", ""))
    cfg = GENRE_TEMPLATES[genre]

    author_id = slot.get("author") or (event.get("participants") or [None])[0]
    author = canon["persona_by_id"].get(author_id, {"persona_id": author_id or "?", "display_name": "?"})

    shared = _build_shared_header(event, slot, author, canon["skeleton"], canon=canon)

    body_template = _load_template(cfg["file"])
    prompt = body_template.format(shared_header=shared)

    # Reasoning effort: medium for high-stakes long-form (adr / postmortem),
    # low for short fast-fill (slack, crm).
    effort = "medium" if genre in {"adr", "postmortem", "rfc", "notion_doc", "meeting_transcript"} else "low"

    text = await llm.call_text(
        stage="C",
        user=prompt,
        reasoning_effort=effort,
        max_tokens=cfg["max_tokens"],
    )
    return text.strip(), genre


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Run Stage C: generate corpus artefacts from event evidence slots."""
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size: {size}; expected one of {list(SIZE_PARAMS)}")
    params = SIZE_PARAMS[size]

    data_root = Path(data_dir)
    corpus_dir = data_root / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"

    cp = Checkpoint(data_root / ".checkpoints" / "stage_c.jsonl")

    # Slots already in corpus_index were generated by a prior stage
    # (original Stage C, C4 long-form which appends -transcript/-doc
    # slots to events, or a previous partial run). NEVER regenerate them
    # — doing so duplicates the slot_id and can shadow a rich C4
    # transcript with a short Stage C artefact. This guard makes Stage C
    # safe to re-run after B6 adds new events (it generates ONLY the new
    # slots).
    existing_index_slots: set[str] = set()
    if index_file.exists():
        for line in index_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    existing_index_slots.add(json.loads(line)["slot_id"])
                except (json.JSONDecodeError, KeyError):
                    pass

    canon = _load_inputs(data_root)
    events = canon["events"]
    logger.info("Stage C: %d events to instantiate (%d slots already in corpus_index, will skip)",
                len(events), len(existing_index_slots))

    llm = HelixLLM()
    written = 0
    skipped_no_slots = 0

    try:
        for event in events:
            event_id = event.get("id")
            if not event_id:
                continue
            slots = event.get("evidence_in_corpus", []) or []
            slots = [s for s in slots if isinstance(s, dict)]
            if not slots:
                skipped_no_slots += 1
                continue

            # Cap slots per event to keep Small bounded
            slots = slots[: params["max_artefacts_per_event"]]

            event_dir = corpus_dir / event_id
            event_dir.mkdir(parents=True, exist_ok=True)

            for slot_idx, slot in enumerate(slots):
                slot_id = slot.get("slot_id") or f"ART-{event_id}-{slot_idx + 1:03d}"
                slot["slot_id"] = slot_id

                unit_id = f"{event_id}/{slot_id}"
                if cp.is_done(unit_id):
                    continue
                # Already generated by a prior stage (C4/original/partial) —
                # skip to avoid duplicate slot_ids in corpus_index.
                if slot_id in existing_index_slots:
                    cp.mark_done(unit_id, status="skip-already-indexed")
                    continue

                try:
                    text, resolved_genre = await _generate_artefact(llm, event, slot, canon)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Stage C %s failed: %s", unit_id, exc)
                    cp.mark_done(unit_id, status="error", error=str(exc)[:200])
                    continue

                if not text:
                    logger.warning("Stage C %s returned empty content", unit_id)
                    cp.mark_done(unit_id, status="empty")
                    continue

                # Write artefact file with testimony-type header prefix.
                # The header is HTML-comment style so it doesn't disrupt
                # the human-readable Markdown body but IS visible to the
                # Stage F answerer reading the file.
                header = _testimony_header(
                    genre=resolved_genre,
                    slot_id=slot_id,
                    author=str(slot.get("author") or (event.get("participants") or [None])[0] or "?"),
                    event_id=event_id,
                    role=str(slot.get("role", "primary")),
                )
                out_path = event_dir / f"{slot_id}.md"
                out_path.write_text(header + text, encoding="utf-8")

                # Append to index
                index_record = {
                    "slot_id": slot_id,
                    "event_id": event_id,
                    "role": slot.get("role", "primary"),
                    "genre": resolved_genre,
                    "author": slot.get("author") or (event.get("participants") or [None])[0],
                    "path": str(out_path.relative_to(data_root)),
                    "chars": len(text),
                }
                with index_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(index_record, default=str) + "\n")
                cp.mark_done(unit_id, status="ok", chars=len(text), genre=resolved_genre)
                written += 1
                logger.info(
                    "Stage C wrote %s [%s/%s %dch]",
                    unit_id, resolved_genre, slot.get("role", "primary"), len(text),
                )

                if written >= params["max_total"]:
                    logger.warning("Stage C hit max_total=%d cap; stopping", params["max_total"])
                    break

            if written >= params["max_total"]:
                break

        logger.info(
            "Stage C complete. %d artefacts written, %d events skipped (no slots)",
            written, skipped_no_slots,
        )
    finally:
        await llm.aclose()
