"""Stage C5 — Ground-truth fragment dispersal.

The nuance lever. Real answers aren't sitting in one document — pieces
are scattered across the corpus and across time, including inside
material that otherwise looks like noise. A nuanced question then
requires gathering and synthesising fragments, not single-shot
retrieval.

For a sample of significant events, this plants several SHORT "fragment"
artefacts, each mentioning ONE fact of the decision in passing (a Slack
callback months later, a doc comment, an email aside, a retro line),
dated AFTER the original decision. Each fragment is incidental
corroboration — it surfaces one aspect of the answer in a mundane,
noise-like context.

These are role="noise" but tagged with `fragments_event` so the
relationship is auditable. They enrich the corpus's dispersal: the same
ground truth now echoes across many places and times, so a retrieval
system must sift and corroborate rather than find one canonical record.

(A stronger variant — removing the fact from the primary so NO single
artefact suffices, with union-mode substrate validation — is the next
step if the dataset proves too easy. This version is additive and safe.)
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM

logger = logging.getLogger("helix_corpus.stage_c5")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c5"
COMPANY_ONE_LINER = (
    "Helix Logistics: B2B SaaS for mid-market freight-forwarding "
    "companies, founded in 2020, ~85 employees by 2025."
)
_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]

_FRAGMENT_GENRES = ["slack_thread", "notion_doc comment", "email aside", "retro line"]

SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"events": 4,   "fragments_per_event": 2},
    "medium": {"events": 25,  "fragments_per_event": 3},
    "large":  {"events": 140, "fragments_per_event": 4},
}


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    events = [
        json.loads(l) for l in (data_dir / "source_of_truth" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {
        "persona_by_id": {p["persona_id"]: p for p in personas},
        "events": events,
    }


def _facts_of(event: dict, pbi: dict) -> list[str]:
    """Decompose an event into individual fragmentable facts."""
    facts = []
    date = str(event.get("occurred_at", ""))[:10]
    dec = str(event.get("decision", "")).strip()
    reason = str(event.get("reason_canonical", "")).strip()
    if dec:
        facts.append(f'The decision made: "{dec[:200]}"')
    if reason:
        facts.append(f'The reason behind it: "{reason[:200]}"')
    if date:
        facts.append(f"That this was decided around {date}")
    for a in (event.get("alternatives_considered", []) or [])[:2]:
        facts.append(f'That an alternative considered (and rejected) was: "{str(a)[:120]}"')
    for pid in (event.get("participants", []) or [])[:2]:
        p = pbi.get(pid)
        if p:
            facts.append(f"That {p.get('display_name', pid)} was involved in this call")
    return facts


def _later_date(occurred: str, rng: random.Random) -> str:
    """A date 1-18 months after the event's occurred_at."""
    try:
        y, m = int(occurred[:4]), int(occurred[5:7])
    except (ValueError, IndexError):
        return occurred
    add = rng.randint(1, 18)
    m2 = m + add
    y2 = y + (m2 - 1) // 12
    m2 = ((m2 - 1) % 12) + 1
    y2 = min(y2, 2026)
    return f"{y2}-{m2:02d}-{rng.randint(1,28):02d}"


def _significant_events(events: list[dict]) -> list[dict]:
    cand = [e for e in events if str(e.get("decision", "")).strip() and (e.get("participants") or [])]
    cand.sort(key=lambda e: -(len(e.get("participants", []) or []) + len(e.get("alternatives_considered", []) or [])))
    return cand


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)
    pbi = inputs["persona_by_id"]

    frag_dir = data_root / "corpus" / "_fragments"
    frag_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_c5.jsonl")

    events = _significant_events(inputs["events"])[: params["events"]]
    rng = random.Random(46)
    logger.info("Stage C5: dispersing fragments for %d events", len(events))

    llm = HelixLLM()
    written = 0
    try:
        for event in events:
            facts = _facts_of(event, pbi)
            if not facts:
                continue
            rng.shuffle(facts)
            n = min(params["fragments_per_event"], len(facts))
            occurred = str(event.get("occurred_at", ""))[:10]
            for fi in range(n):
                slot_id = f"FRAG-{event['id']}-{fi}"
                if cp.is_done(slot_id):
                    continue
                fact = facts[fi]
                genre = rng.choice(_FRAGMENT_GENRES)
                mdate = _later_date(occurred, rng)
                try:
                    mmonth = _MONTHS[int(mdate[5:7])]
                except (ValueError, IndexError):
                    mmonth = ""
                # a plausible person to voice the callback
                ppool = [pbi[p]["display_name"] for p in (event.get("participants") or []) if p in pbi]
                person = rng.choice(ppool) if ppool else "someone on the team"
                prompt = _load_template("fragment_plant.md").format(
                    company_one_liner=COMPANY_ONE_LINER,
                    fact=fact,
                    mention_date=mdate,
                    mention_date_month=f"{mmonth} {mdate[:4]}",
                    genre=genre,
                    people=person,
                )
                text = await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=1200)
                if not text.strip():
                    cp.mark_done(slot_id, status="empty")
                    continue
                out_path = frag_dir / f"{slot_id}.md"
                out_path.write_text(
                    f"<!-- fragment of={event['id']} genre={genre} {mdate} role=noise -->\n\n" + text,
                    encoding="utf-8",
                )
                with index_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "slot_id": slot_id, "event_id": None, "role": "noise",
                        "genre": "slack_thread" if "slack" in genre else "notion_doc",
                        "fragments_event": event["id"], "author": None,
                        "path": str(out_path.relative_to(data_root)), "chars": len(text),
                    }, default=str) + "\n")
                cp.mark_done(slot_id, status="ok", chars=len(text))
                written += 1
                if written % 50 == 0:
                    logger.info("Stage C5: %d fragments written", written)

        logger.info("Stage C5 complete. %d fragments dispersed.", written)
    finally:
        await llm.aclose()
