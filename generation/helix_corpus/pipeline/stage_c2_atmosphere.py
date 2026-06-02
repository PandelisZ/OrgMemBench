"""Stage C2 — Background atmosphere generation.

The big noise lever for Large. Generates the everyday hum of a real
company workspace — Slack chatter and internal email volume that maps
to NO tracked event. This is the noise a memory system must sift
through to find the ground-truth signal.

Two batched generators (batching keeps the run tractable — one LLM call
produces ~10 Slack messages or ~5 email threads):

1. **Slack atmosphere**: for each (year, month) and each Slack channel
   ALIVE that month (per channel_timeline.jsonl), generate a batch of
   everyday messages. Channels born/renamed/archived across the
   company's life mean the atmosphere naturally evolves — a 2022
   project channel is busy then goes silent; a 2024 channel didn't
   exist in 2021.

2. **Internal email atmosphere**: for each (year, month, team),
   generate a batch of routine internal email threads. INTERNAL ONLY
   (per the noise-discipline rule — external/spam excluded).

Cadence is sampled, not exhaustive — we don't generate every channel
every month (that would be enormous); we sample a configurable number
of channel-months and team-months per the size's atmosphere budget.

Outputs: atmosphere artefacts under ``corpus/_atmosphere/`` and index
rows appended to ``corpus_index.jsonl`` with role="noise".
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

logger = logging.getLogger("helix_corpus.stage_c2")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c2"
CURRENT_YEAR = 2026
FOUNDING_FALLBACK = 2020
COMPANY_NAME = "Helix Logistics"
COMPANY_ARCHETYPE = (
    "B2B SaaS for mid-market freight-forwarding companies, "
    "founded in 2020, ~85 employees by 2025"
)
COMPANY_ONE_LINER = f"{COMPANY_NAME}: {COMPANY_ARCHETYPE}."

_TEAMS = [
    "Engineering", "Sales", "Product", "Customer Success",
    "Operations", "Marketing", "Finance", "People",
]

# Per-size atmosphere budget. Controls how much noise we generate.
# channel_months: how many (channel, month) Slack batches.
# team_months: how many (team, month) email batches.
# msgs_per_slack_batch / threads_per_email_batch: batch sizes.
SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"channel_months": 12,   "team_months": 8,   "msgs_per_slack_batch": 8,  "threads_per_email_batch": 3,
               "meeting_instances": 8,   "doc_pages": 6},
    "medium": {"channel_months": 80,   "team_months": 60,  "msgs_per_slack_batch": 10, "threads_per_email_batch": 4,
               "meeting_instances": 60,  "doc_pages": 40},
    # Large: atmosphere is the dominant token lever (~3M+ tokens).
    # channel_months high enough to take ~every alive channel-month;
    # large batches (35 Slack msgs, 8 email threads) per batch. Sampling
    # allows the same channel-month to recur, representing the many
    # parallel threads a busy channel carries in a month.
    # meeting_instances / doc_pages de-bias the noise away from
    # Slack/email — a real company runs a meeting cadence (all-hands,
    # syncs, planning, retros) that scales with headcount, and writes
    # routine wiki pages. Set 0 to skip.
    # Slack trimmed 2500->800: at ~16s/call it was the biggest, lowest-
    # value time sink. The high-value long-form (C4) carries the tokens
    # instead, landing ~4.5M in ~18h rather than ~5M in ~28h.
    "large":  {"channel_months": 800, "team_months": 700, "msgs_per_slack_batch": 35,
               "threads_per_email_batch": 8, "meeting_instances": 600, "doc_pages": 280},
}

# Background meeting types: (label, scope, min_year). Earlier-stage
# companies have fewer meeting types; the cadence + variety grow as the
# company scales. Group meetings only — no 1:1 / private content.
_MEETING_TYPES: list[tuple[str, str, int]] = [
    ("all-hands", "company-wide", 2021),
    ("engineering sync", "Engineering", 2021),
    ("standup", "team", 2022),
    ("sprint planning", "Engineering", 2022),
    ("sprint retro", "Engineering", 2022),
    ("pipeline review", "Sales", 2022),
    ("product review", "Product", 2022),
    ("hiring sync", "People", 2022),
    ("OKR planning", "company-wide", 2023),
    ("architecture / ADR review", "Engineering", 2023),
    ("cross-functional sync", "company-wide", 2023),
    ("board meeting", "leadership", 2023),
    ("finance review", "Finance", 2024),
    ("on-call handoff", "Engineering", 2025),
]

# Background meetings per MONTH by year — fewer when small, more at scale.
_MEETINGS_PER_MONTH: dict[int, int] = {
    2020: 2, 2021: 4, 2022: 8, 2023: 7, 2024: 9, 2025: 11, 2026: 11,
}

# Headcount note per year (rough), to colour meeting/doc tone.
_HEADCOUNT_NOTE: dict[int, str] = {
    2020: "~4 people (founding team)",
    2021: "~14 people",
    2022: "~47 people (hypergrowth)",
    2023: "~40 people (post-layoff)",
    2024: "~65 people",
    2025: "~85 people",
    2026: "~85 people",
}

# Routine wiki/Notion doc types.
_DOC_TYPES = [
    "status_page", "runbook", "onboarding_doc", "process_doc",
    "okr_page", "meeting_notes_index", "how_to",
]

# Per-size output token budget for the batched calls (bigger batches at
# Large need more room).
_SLACK_MAX_TOKENS = {"small": 3000, "medium": 3000, "large": 5000}
_EMAIL_MAX_TOKENS = {"small": 4000, "medium": 4000, "large": 8000}


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    skeleton = json.loads((canon / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    channels = []
    ch_path = canon / "channel_timeline.jsonl"
    if ch_path.exists():
        channels = [
            json.loads(l) for l in ch_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    customers = []
    for fn in ("customers.jsonl", "historical_customers.jsonl"):
        p = canon / fn
        if p.exists():
            customers.extend(
                json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()
            )
    # Events give us the real projects/topics in flight each year — used
    # to ground the atmosphere in the company's actual work that year.
    events = []
    ev_path = data_dir / "source_of_truth" / "events.jsonl"
    if ev_path.exists():
        events = [
            json.loads(l) for l in ev_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    return {
        "skeleton": skeleton, "personas": personas, "channels": channels,
        "customers": customers, "events": events,
    }


def _customers_active_in_year(customers: list[dict], year: int) -> list[str]:
    out = []
    for c in customers:
        try:
            first = int(c.get("first_year", 9999))
        except (TypeError, ValueError):
            continue
        if first > year:
            continue
        last = c.get("last_year")
        if last is not None:
            try:
                if int(last) < year:
                    continue
            except (TypeError, ValueError):
                pass
        if c.get("name"):
            out.append(c["name"])
    return out


def _year_context(year: int, inputs: dict) -> str:
    """A short brief on what the company is actually doing this year:
    the year arc/theme, the customers it has, and a sample of the real
    projects/decisions in flight — so atmosphere reads like real work
    that fits the company's situation, not generic chatter."""
    arcs = inputs["skeleton"].get("year_arcs", {})
    theme = arcs.get(year) or arcs.get(str(year)) or ""
    custs = _customers_active_in_year(inputs.get("customers", []), year)
    # Sample of this year's event topics (the real work in flight)
    topics = []
    for e in inputs.get("events", []):
        if str(e.get("occurred_at", ""))[:4] == str(year):
            s = str(e.get("summary", "")).strip()
            if s:
                topics.append(s[:90])
    random.shuffle(topics)
    lines = [f"- Year {year}: {theme}" if theme else f"- Year {year}"]
    if custs:
        sample_c = ", ".join(custs[:10])
        lines.append(f"- Customers this year include: {sample_c}")
    if topics:
        lines.append("- Real work/projects in flight this year (for flavour — do NOT restate as decisions):")
        for t in topics[:8]:
            lines.append(f"    • {t}")
    return "\n".join(lines)


def _era_for(year: int, eras: list[dict]) -> dict:
    for e in eras:
        try:
            if int(e["start"][:4]) <= year <= int(e["end"][:4]):
                return e
        except (KeyError, ValueError, IndexError):
            continue
    return eras[0] if eras else {"name": "?", "discipline_level": "medium"}


def _tooling_active(year: int, tooling: list[dict]) -> str:
    active = [t["description"] for t in tooling if int(t.get("year", 9999)) <= year]
    return "; ".join(active[-6:]) or "(early tooling)"


def _ym_in_range(created: str, archived: str | None, year: int, month: int) -> bool:
    """Is (year, month) within [created, archived)?"""
    target = year * 12 + month
    try:
        cy, cm = int(created[:4]), int(created[5:7])
        cstart = cy * 12 + cm
    except (ValueError, TypeError, IndexError):
        return False
    if target < cstart:
        return False
    if archived:
        try:
            ay, am = int(archived[:4]), int(archived[5:7])
            aend = ay * 12 + am
            if target >= aend:
                return False
        except (ValueError, TypeError, IndexError):
            pass
    return True


def _personas_active_in_year(personas: list[dict], year: int, team: str | None = None) -> list[dict]:
    out = []
    for p in personas:
        joined = p.get("joined_year")
        try:
            joined = int(joined)
        except (TypeError, ValueError):
            continue
        if joined > year:
            continue
        left = p.get("left_year")
        if left is not None:
            try:
                if int(left) < year:
                    continue
            except (TypeError, ValueError):
                pass
        out.append(p)
    return out


def _persona_block(personas: list[dict], limit: int = 12) -> str:
    lines = []
    for p in personas[:limit]:
        role = (p.get("role_history") or [{}])[0].get("role", "?")
        lines.append(f"- {p.get('display_name','?')} ({role})")
    return "\n".join(lines) or "(team members)"


# ---------------------------------------------------------------------------
# Slack atmosphere
# ---------------------------------------------------------------------------


async def _gen_slack_batch(
    llm: HelixLLM, channel: dict, year: int, month: int, inputs: dict,
    n_msgs: int, max_tokens: int,
) -> str:
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    personas = _personas_active_in_year(inputs["personas"], year)
    random.shuffle(personas)
    prompt = _load_template("atmosphere_slack.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        channel_name=channel.get("channel", "#general"),
        channel_purpose=channel.get("purpose", "general chatter"),
        channel_team=channel.get("team", "company-wide"),
        year_month=f"{year}-{month:02d}",
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        tooling_active=_tooling_active(year, inputs["skeleton"].get("tooling", [])),
        personas_block=_persona_block(personas),
        n_messages=n_msgs,
        year_context=_year_context(year, inputs),
    )
    return await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=max_tokens)


async def _gen_email_batch(
    llm: HelixLLM, team: str, year: int, month: int, inputs: dict,
    n_threads: int, max_tokens: int,
) -> str:
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    personas = _personas_active_in_year(inputs["personas"], year)
    random.shuffle(personas)
    prompt = _load_template("atmosphere_email.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        team=team,
        year_month=f"{year}-{month:02d}",
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        personas_block=_persona_block(personas),
        n_threads=n_threads,
        year_context=_year_context(year, inputs),
    )
    return await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Background meetings + routine wiki docs (de-bias from Slack/email)
# ---------------------------------------------------------------------------


def _meeting_plan(years: list[int], rng: random.Random, target: int) -> list[tuple[str, str, int, int]]:
    """Build (meeting_type, scope, year, month) instances scaled by era
    cadence, capped at target. Only meeting types available in that year."""
    plan: list[tuple[str, str, int, int]] = []
    for y in years:
        per_month = _MEETINGS_PER_MONTH.get(y, 6)
        avail = [(label, scope) for (label, scope, miny) in _MEETING_TYPES if y >= miny]
        if not avail:
            continue
        for m in range(1, 13):
            for _ in range(per_month):
                label, scope = rng.choice(avail)
                plan.append((label, scope, y, m))
    rng.shuffle(plan)
    return plan[:target]


async def _gen_meeting_batch(
    llm: HelixLLM, meeting_type: str, scope: str, year: int, month: int,
    inputs: dict, max_tokens: int,
) -> str:
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    personas = _personas_active_in_year(inputs["personas"], year)
    random.shuffle(personas)
    day = random.randint(1, 28)
    prompt = _load_template("atmosphere_meeting.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        meeting_type=meeting_type,
        attendee_scope=scope,
        meeting_date=f"{year}-{month:02d}-{day:02d}",
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        headcount_note=_HEADCOUNT_NOTE.get(year, ""),
        personas_block=_persona_block(personas, limit=14),
        year_context=_year_context(year, inputs),
    )
    return await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=max_tokens)


async def _gen_doc_batch(
    llm: HelixLLM, doc_type: str, topic: str, year: int, month: int,
    inputs: dict, max_tokens: int,
) -> str:
    era = _era_for(year, inputs["skeleton"].get("eras", []))
    personas = _personas_active_in_year(inputs["personas"], year)
    random.shuffle(personas)
    prompt = _load_template("atmosphere_doc.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        doc_type=doc_type,
        topic=topic,
        doc_date=f"{year}-{month:02d}-{random.randint(1,28):02d}",
        era_name=era.get("name", "?"),
        era_discipline_level=era.get("discipline_level", "medium"),
        personas_block=_persona_block(personas, limit=10),
        year_context=_year_context(year, inputs),
    )
    return await llm.call_text(stage="C", user=prompt, reasoning_effort="low", max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)

    if not inputs["channels"]:
        logger.warning("Stage C2: no channel_timeline.jsonl — run Stage A first. Skipping atmosphere.")
        return

    atm_dir = data_root / "corpus" / "_atmosphere"
    atm_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_c2.jsonl")

    # Build the set of (channel, year, month) candidates where the channel
    # is alive. If the requested channel_months exceeds the unique alive
    # set, sample WITH REPLACEMENT — a busy channel-month carries many
    # parallel threads, so multiple batches per (channel, month) is
    # realistic. A per-(channel,month) batch index disambiguates slot_ids.
    years = sorted(int(y) for y in inputs["skeleton"]["year_arcs"].keys())
    rng = random.Random(42)  # deterministic sampling
    slack_max = _SLACK_MAX_TOKENS.get(size, 3000)
    email_max = _EMAIL_MAX_TOKENS.get(size, 4000)

    alive: list[tuple[dict, int, int]] = []
    for ch in inputs["channels"]:
        for y in years:
            for m in range(1, 13):
                if _ym_in_range(ch.get("created", ""), ch.get("archived"), y, m):
                    alive.append((ch, y, m))
    rng.shuffle(alive)

    target = params["channel_months"]
    slack_plan: list[tuple[dict, int, int, int]] = []  # (ch, y, m, batch_idx)
    if not alive:
        slack_plan = []
    elif target <= len(alive):
        slack_plan = [(ch, y, m, 0) for ch, y, m in alive[:target]]
    else:
        # take all alive at least once, then recur (with replacement)
        batch_idx_counter: dict[tuple, int] = {}
        for ch, y, m in alive:
            batch_idx_counter[(ch["channel"], y, m)] = 0
            slack_plan.append((ch, y, m, 0))
        while len(slack_plan) < target:
            ch, y, m = rng.choice(alive)
            key = (ch["channel"], y, m)
            batch_idx_counter[key] = batch_idx_counter.get(key, 0) + 1
            slack_plan.append((ch, y, m, batch_idx_counter[key]))

    email_candidates: list[tuple[str, int, int]] = [
        (team, y, m) for team in _TEAMS for y in years for m in range(1, 13)
    ]
    rng.shuffle(email_candidates)
    email_candidates = email_candidates[: params["team_months"]]

    logger.info(
        "Stage C2: %d slack batches (%d unique alive channel-months) + %d team-months to generate",
        len(slack_plan), len(alive), len(email_candidates),
    )

    llm = HelixLLM()
    written = 0
    try:
        # --- Slack atmosphere ---
        for ch, y, m, batch_idx in slack_plan:
            ch_slug = re.sub(r"[^a-z0-9]+", "-", ch.get("channel", "general").lower()).strip("-")
            suffix = f"-{batch_idx}" if batch_idx else ""
            slot_id = f"ATM-slack-{ch_slug}-{y}{m:02d}{suffix}"
            if cp.is_done(slot_id):
                continue
            text = await _gen_slack_batch(
                llm, ch, y, m, inputs, params["msgs_per_slack_batch"], slack_max,
            )
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            out_path = atm_dir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- atmosphere slack channel={ch.get('channel')} {y}-{m:02d} role=noise -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": None, "role": "noise",
                    "genre": "slack_thread", "author": None,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 50 == 0:
                logger.info("Stage C2: %d atmosphere artefacts written", written)

        # --- Internal email atmosphere ---
        for team, y, m in email_candidates:
            slot_id = f"ATM-email-{team.lower().replace(' ','-')}-{y}{m:02d}"
            if cp.is_done(slot_id):
                continue
            text = await _gen_email_batch(
                llm, team, y, m, inputs, params["threads_per_email_batch"], email_max,
            )
            if not text.strip():
                cp.mark_done(slot_id, status="empty")
                continue
            out_path = atm_dir / f"{slot_id}.md"
            out_path.write_text(
                f"<!-- atmosphere internal-email team={team} {y}-{m:02d} role=noise -->\n\n" + text,
                encoding="utf-8",
            )
            with index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "slot_id": slot_id, "event_id": None, "role": "noise",
                    "genre": "email_thread", "author": None,
                    "path": str(out_path.relative_to(data_root)), "chars": len(text),
                }, default=str) + "\n")
            cp.mark_done(slot_id, status="ok", chars=len(text))
            written += 1
            if written % 50 == 0:
                logger.info("Stage C2: %d atmosphere artefacts written", written)

        # --- Background meetings (de-bias from Slack/email) ---
        meeting_target = params.get("meeting_instances", 0)
        if meeting_target:
            mplan = _meeting_plan(years, random.Random(43), meeting_target)
            logger.info("Stage C2: %d background meetings to generate", len(mplan))
            for i, (mtype, scope, y, m) in enumerate(mplan):
                mslug = re.sub(r"[^a-z0-9]+", "-", mtype.lower()).strip("-")
                slot_id = f"ATM-meeting-{mslug}-{y}{m:02d}-{i:04d}"
                if cp.is_done(slot_id):
                    continue
                text = await _gen_meeting_batch(llm, mtype, scope, y, m, inputs, slack_max)
                if not text.strip():
                    cp.mark_done(slot_id, status="empty")
                    continue
                out_path = atm_dir / f"{slot_id}.md"
                out_path.write_text(
                    f"<!-- atmosphere meeting type={mtype} scope={scope} {y}-{m:02d} role=noise -->\n\n" + text,
                    encoding="utf-8",
                )
                with index_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "slot_id": slot_id, "event_id": None, "role": "noise",
                        "genre": "meeting_notes", "author": None,
                        "path": str(out_path.relative_to(data_root)), "chars": len(text),
                    }, default=str) + "\n")
                cp.mark_done(slot_id, status="ok", chars=len(text))
                written += 1
                if written % 50 == 0:
                    logger.info("Stage C2: %d atmosphere artefacts written", written)

        # --- Routine wiki / Notion docs ---
        doc_target = params.get("doc_pages", 0)
        if doc_target:
            drng = random.Random(44)
            topics = _TEAMS + ["Platform", "Release process", "On-call", "Security", "Data"]
            dplan = []
            for _ in range(doc_target):
                dt = drng.choice(_DOC_TYPES)
                topic = drng.choice(topics)
                y = drng.choice(years)
                m = drng.randint(1, 12)
                dplan.append((dt, topic, y, m))
            logger.info("Stage C2: %d routine wiki docs to generate", len(dplan))
            for i, (dt, topic, y, m) in enumerate(dplan):
                dslug = re.sub(r"[^a-z0-9]+", "-", f"{dt}-{topic}".lower()).strip("-")
                slot_id = f"ATM-doc-{dslug}-{y}{m:02d}-{i:04d}"
                if cp.is_done(slot_id):
                    continue
                text = await _gen_doc_batch(llm, dt, topic, y, m, inputs, slack_max)
                if not text.strip():
                    cp.mark_done(slot_id, status="empty")
                    continue
                out_path = atm_dir / f"{slot_id}.md"
                out_path.write_text(
                    f"<!-- atmosphere wiki doc_type={dt} topic={topic} {y}-{m:02d} role=noise -->\n\n" + text,
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
                if written % 50 == 0:
                    logger.info("Stage C2: %d atmosphere artefacts written", written)

        logger.info("Stage C2 complete. %d atmosphere artefacts written.", written)
    finally:
        await llm.aclose()
