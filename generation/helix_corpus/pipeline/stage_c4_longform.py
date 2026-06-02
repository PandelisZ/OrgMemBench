"""Stage C4 — Long-form artefacts (the big-token, high-value lever).

The corpus's biggest, densest artefacts — the ones a real company
produces and the ones that hold (and disperse) ground truth:

1. **Verbatim meeting transcripts** for significant decisions. A real
   hour-long meeting transcript runs many thousands of words. The
   ground truth (decision, reason, alternatives, who-argued-what, date)
   is woven THROUGH the dialogue rather than stated once — so a system
   must follow the whole conversation, not grab a snippet. These are
   added to the event's evidence_in_corpus so questions reference them.

2. **Long-form documents** (PRD, RFC, architecture decision, detailed
   postmortem, board-deck narrative, strategy memo, annual plan, QBR
   deck). 3-6k words each. A MIX:
   - event-tied (carry the event's ground truth → added to evidence)
   - standalone (rich tangential noise, role=noise)

Run AFTER the base pipeline (Phase 1) completes. It appends evidence
slots to events.jsonl, so Stage E must be re-run afterwards to fold the
new artefacts into the questions, then Stage F + repair.

Token-dominant: at Large ~150 transcripts (~7k words) + ~270 docs
(~3k words) ≈ ~1.9M words ≈ ~2.5M tokens of valuable + noisy volume.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM

logger = logging.getLogger("helix_corpus.stage_c4")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c4"
COMPANY_NAME = "Helix Logistics"
COMPANY_ONE_LINER = (
    f"{COMPANY_NAME}: B2B SaaS for mid-market freight-forwarding "
    "companies, founded in 2020, ~85 employees by 2025."
)

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]

# Long-form doc genres. event-tied docs use the decision-bearing ones;
# standalone noise docs use the broader set.
_EVENT_DOC_TYPES = ["PRD", "RFC / architecture decision", "postmortem", "strategy memo"]
_STANDALONE_DOC_TYPES = [
    "PRD", "RFC / architecture decision", "postmortem", "strategy memo",
    "board deck narrative", "annual plan", "QBR deck",
]
_STANDALONE_TOPICS = [
    "Platform reliability", "Onboarding funnel", "Pricing model",
    "Data pipeline", "Security posture", "Hiring plan", "GTM strategy",
    "Customer health", "Infrastructure cost", "Mobile app", "API v2",
    "Internationalisation", "Compliance (SOC2)", "Churn analysis",
]

SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"transcripts": 4,   "event_docs": 3,   "standalone_docs": 4},
    "medium": {"transcripts": 20,  "event_docs": 15,  "standalone_docs": 20},
    # Long-form has the highest tokens-per-call (chunked ~3,300-word
    # transcripts, ~2,400-word docs). Transcripts + event_docs are
    # high-value (ground-truth-bearing) so kept high; standalone docs
    # are noise, trimmed 240->110 since the run was projecting ~6M
    # tokens (over the ~5M target).
    "large":  {"transcripts": 220, "event_docs": 120, "standalone_docs": 110},
}

# Output budgets — these are the LONG artefacts. gpt-oss wraps up around
# ~1,300 words per call regardless of max_tokens, so we CHUNK: generate
# the artefact in continued segments to reach genuine length.
_TRANSCRIPT_MAX_TOKENS = 6000
_DOC_MAX_TOKENS = 6000
_TRANSCRIPT_PARTS = 3   # ~3 × ~1.3k words ≈ ~4k-word transcripts
_DOC_PARTS = 2          # ~2 × ~1.2k words ≈ ~2.5k-word docs


async def _gen_long(
    llm: HelixLLM, base_prompt: str, parts: int, max_tokens: int, kind: str,
) -> str:
    """Generate a long artefact in continued segments. gpt-oss caps each
    call at ~1,300 words, so we ask it to continue from the tail of the
    previous segment to reach genuine length."""
    segments: list[str] = []
    first = await llm.call_text(stage="C", user=base_prompt, reasoning_effort="low", max_tokens=max_tokens)
    if not first.strip():
        return ""
    segments.append(first.strip())
    for _ in range(parts - 1):
        tail = "\n".join(segments[-1].splitlines()[-12:])
        cont_prompt = (
            f"{base_prompt}\n\n# CONTINUE\n\nYou have already written the start of this "
            f"{kind}. Here are its last lines:\n\n{tail}\n\nContinue from exactly there — "
            "more of the same artefact (further debate/sections/turns, then move toward "
            "resolution/conclusion/action items). Do NOT repeat earlier content, do NOT "
            "rewrite the header. Output only the continuation."
        )
        nxt = await llm.call_text(stage="C", user=cont_prompt, reasoning_effort="low", max_tokens=max_tokens)
        if not nxt.strip():
            break
        segments.append(nxt.strip())
    return "\n\n".join(segments)


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    skeleton = json.loads((canon / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    events = [
        json.loads(l) for l in (data_dir / "source_of_truth" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {
        "skeleton": skeleton,
        "personas": personas,
        "persona_by_id": {p["persona_id"]: p for p in personas},
        "events": events,
    }


def _era_for(year: int, eras: list[dict]) -> dict:
    for e in eras:
        try:
            if int(e["start"][:4]) <= year <= int(e["end"][:4]):
                return e
        except (KeyError, ValueError, IndexError):
            continue
    return eras[0] if eras else {"name": "?", "discipline_level": "medium"}


def _names(persona_by_id: dict, ids: list[str]) -> list[str]:
    out = []
    for pid in ids:
        p = persona_by_id.get(pid)
        out.append(p.get("display_name", pid) if p else pid)
    return out


def _significant_events(events: list[dict]) -> list[dict]:
    """Events worth a verbatim transcript: a real decision with ≥2
    people in the room. Ranked by richness (participants + alternatives)."""
    cand = []
    for e in events:
        dec = str(e.get("decision", "")).strip()
        parts = e.get("participants", []) or []
        if dec and len(parts) >= 2:
            score = len(parts) + len(e.get("alternatives_considered", []) or [])
            cand.append((score, e))
    cand.sort(key=lambda x: -x[0])
    return [e for _, e in cand]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


async def _gen_transcript(llm: HelixLLM, event: dict, inputs: dict) -> str:
    pbi = inputs["persona_by_id"]
    date = str(event.get("occurred_at", ""))[:10]
    try:
        month = _MONTHS[int(date[5:7])]
    except (ValueError, IndexError):
        month = ""
    parts = _names(pbi, event.get("participants", [])[:6])
    alts = event.get("alternatives_considered", []) or []
    prompt = _load_template("verbatim_transcript.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        event_summary=str(event.get("summary", ""))[:200],
        event_date=date,
        event_date_month=month,
        decision=str(event.get("decision", ""))[:300],
        reason=str(event.get("reason_canonical", ""))[:300],
        alternatives="; ".join(str(a)[:80] for a in alts[:4]) or "(none recorded)",
        participants=", ".join(parts) or "the team",
    )
    return await _gen_long(llm, prompt, _TRANSCRIPT_PARTS, _TRANSCRIPT_MAX_TOKENS, "transcript")


async def _gen_event_doc(llm: HelixLLM, event: dict, doc_type: str, inputs: dict) -> str:
    pbi = inputs["persona_by_id"]
    date = str(event.get("occurred_at", ""))[:10]
    year = int(date[:4]) if date[:4].isdigit() else 2023
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    authors = _names(pbi, event.get("participants", [])[:3])
    alts = event.get("alternatives_considered", []) or []
    gt = (
        "# Ground truth to embed (every fact MUST appear, woven naturally)\n\n"
        f"- Decision: {str(event.get('decision',''))[:300]}\n"
        f"- Reason: {str(event.get('reason_canonical',''))[:300]}\n"
        f"- Date: {date}\n"
        f"- Alternatives considered: {'; '.join(str(a)[:80] for a in alts[:4]) or '(none)'}\n"
        f"- People involved: {', '.join(authors) or 'the team'}\n"
    )
    prompt = _load_template("longform_document.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        doc_type=doc_type,
        topic=str(event.get("summary", ""))[:160],
        doc_date=date,
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        authors_block="\n".join(f"- {a}" for a in authors) or "- the team",
        ground_truth_block=gt,
    )
    return await _gen_long(llm, prompt, _DOC_PARTS, _DOC_MAX_TOKENS, "document")


async def _gen_standalone_doc(
    llm: HelixLLM, doc_type: str, topic: str, year: int, inputs: dict,
) -> str:
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    personas = [
        p for p in inputs["personas"]
        if str(p.get("joined_year", "9999")).isdigit() and int(p["joined_year"]) <= year
    ]
    random.shuffle(personas)
    authors = [p.get("display_name", "?") for p in personas[:3]]
    prompt = _load_template("longform_document.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        doc_type=doc_type,
        topic=f"{topic} ({year})",
        doc_date=f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        authors_block="\n".join(f"- {a}" for a in authors) or "- the team",
        ground_truth_block="",  # standalone = noise, no ground truth to embed
    )
    return await _gen_long(llm, prompt, _DOC_PARTS, _DOC_MAX_TOKENS, "document")


def _append_evidence_slot(events_file: Path, event_id: str, slot: dict) -> None:
    """Append a new evidence_in_corpus slot to one event in events.jsonl."""
    events = [
        json.loads(l) for l in events_file.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    for e in events:
        if e["id"] == event_id:
            e.setdefault("evidence_in_corpus", []).append(slot)
            break
    with events_file.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, default=str) + "\n")


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)

    lf_dir = data_root / "corpus" / "_longform"
    lf_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"
    events_file = data_root / "source_of_truth" / "events.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_c4.jsonl")

    sig_events = _significant_events(inputs["events"])
    rng = random.Random(45)
    years = sorted(int(y) for y in inputs["skeleton"]["year_arcs"].keys())

    llm = HelixLLM()
    written = 0
    try:
        # --- Verbatim transcripts (event-tied, big) ---
        for event in sig_events[: params["transcripts"]]:
            slot_id = f"ART-{event['id']}-transcript"
            if cp.is_done(slot_id):
                continue
            text = await _gen_transcript(llm, event, inputs)
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            out_path = lf_dir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- longform transcript event={event['id']} role=primary genre=meeting_transcript -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": event["id"], "role": "secondary",
                    "genre": "meeting_transcript", "author": None,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            _append_evidence_slot(events_file, event["id"], {
                "slot_id": slot_id, "genre": "meeting_transcript", "role": "secondary",
            })
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 20 == 0:
                logger.info("Stage C4: %d long-form artefacts written", written)

        # --- Event-tied long-form docs (carry ground truth) ---
        doc_events = sig_events[: params["event_docs"]]
        for i, event in enumerate(doc_events):
            doc_type = _EVENT_DOC_TYPES[i % len(_EVENT_DOC_TYPES)]
            slot_id = f"ART-{event['id']}-doc"
            if cp.is_done(slot_id):
                continue
            text = await _gen_event_doc(llm, event, doc_type, inputs)
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            out_path = lf_dir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- longform doc event={event['id']} type={doc_type} role=secondary -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": event["id"], "role": "secondary",
                    "genre": "notion_doc", "author": None,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            _append_evidence_slot(events_file, event["id"], {
                "slot_id": slot_id, "genre": "notion_doc", "role": "secondary",
            })
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 20 == 0:
                logger.info("Stage C4: %d long-form artefacts written", written)

        # --- Standalone long-form docs (rich noise) ---
        for i in range(params["standalone_docs"]):
            doc_type = rng.choice(_STANDALONE_DOC_TYPES)
            topic = rng.choice(_STANDALONE_TOPICS)
            year = rng.choice(years)
            slug = re.sub(r"[^a-z0-9]+", "-", f"{doc_type}-{topic}".lower()).strip("-")
            slot_id = f"LF-doc-{slug}-{year}-{i:04d}"
            if cp.is_done(slot_id):
                continue
            text = await _gen_standalone_doc(llm, doc_type, topic, year, inputs)
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            out_path = lf_dir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- longform standalone doc_type={doc_type} topic={topic} {year} role=noise -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": None, "role": "noise",
                    "genre": "notion_doc", "author": None,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 20 == 0:
                logger.info("Stage C4: %d long-form artefacts written", written)

        logger.info("Stage C4 complete. %d long-form artefacts written.", written)
    finally:
        await llm.aclose()
