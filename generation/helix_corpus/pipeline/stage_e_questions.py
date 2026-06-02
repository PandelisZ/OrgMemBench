"""Stage E — Question generation from the source-of-truth graph.

Per design doc §9: **the answers are deterministic graph projections,
not LLM regenerations.** Code samples events by category-structural
property, computes the canonical answer from graph fields, and only
asks gpt-oss to phrase the question text and the rubric criteria.

For each benchmark category C1-C6:

* C1 (supersession-with-reason): sample events with a `supersedes`
  edge incoming → answer = (prior_value, current_value, change_date,
  change_reason).
* C2 (decision provenance): sample strategic_decision events with
  ≥2 alternatives_considered → answer = (deciders, decision_date,
  alternatives, deciding_factor).
* C3 (bi-temporal disambiguation): sample events with a
  `retroactively_corrected_by` edge → answer = (original_value,
  corrected_value, original_recorded_at, correction_recorded_at,
  true_occurred_at).
* C4 (audit replay): pick an as-of date, project all facts true on
  that date for a topic, identify which have since been
  superseded → answer = (as_of_facts, changed_facts, replacements).
* C5 (justification chains): sample events with ≥3
  evidence_in_corpus entries → answer = (evidence_artefact_ids,
  testimony_vs_inference_attribution).
* C6 (contradiction-with-attribution): sample
  contradiction_episode events that have a `contradicts` edge →
  answer = (party_a, party_a_claim, party_a_date, party_b,
  party_b_claim, party_b_date, resolution_status).

gpt-oss role: write 3 paraphrases of each question + write the
rubric sub-points instantiated against the ground-truth answer.

Outputs under ``data/`` :

* ``questions_draft.jsonl`` — one question per line. Marked "draft"
  until Stage F validates.
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
from helix_corpus.parsers import normalize_smart_quotes, strip_code_fences
from helix_corpus.schemas import RelationType

logger = logging.getLogger("helix_corpus.stage_e")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_e"
CURRENT_YEAR = 2026


# ---------------------------------------------------------------------------
# Size parameters
# ---------------------------------------------------------------------------

SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"per_category": 3,  "max_total": 20,  "hard_target": 2},
    "medium": {"per_category": 15, "max_total": 100, "hard_target": 6},
    # Large: recorded (T1/T2) set targets ~75; the ~30 EMERGENT (T3)
    # questions from Stage G bring the total to ~100+. B6's supersession
    # chains now supply C1/C3/C4/C6/HARD candidates, so per-category and
    # hard_target can be filled.
    "large":  {"per_category": 12, "max_total": 85, "hard_target": 18},
}

# Sub-point structures per category (from v2 design §3.1).
CATEGORY_SUBPOINTS: dict[str, list[str]] = {
    "C1": ["current_value", "prior_value", "change_date", "change_reason"],
    "C2": ["decider", "decision_date", "alternatives_set", "deciding_factor"],
    "C3": ["current_belief", "version_dates", "historical_belief"],
    "C4": ["asof_facts_set", "changed_facts_set", "replacements"],
    "C5": ["evidence_set_recall", "testimony_vs_inference", "no_hallucination"],
    "C6": ["per_source_claim", "per_source_timing", "resolution_status"],
    # HARD lineage: trace an entire chain — one sub-point per chain step
    # plus a "current state" sub-point. Instantiated dynamically.
    "HARD": ["full_chain_recall", "per_step_who", "per_step_when", "per_step_why", "current_state"],
}


def _difficulty_for(evidence_count: int, chain_len: int = 1) -> str:
    """Difficulty tier from evidence breadth + chain depth.

    easy: answer in 1-2 artefacts. medium: 3-5. hard: 6+ artefacts OR
    a chain of 3+ linked events (cross-year synthesis).
    """
    if chain_len >= 3 or evidence_count >= 6:
        return "hard"
    if evidence_count >= 3:
        return "medium"
    return "easy"


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Graph loading + indexing
# ---------------------------------------------------------------------------


def _load_graph(data_dir: Path) -> dict[str, Any]:
    sot_dir = data_dir / "source_of_truth"
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
    canon_dir = data_dir / "helix_canon"
    personas = [
        json.loads(line)
        for line in (canon_dir / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "events": events,
        "relations": relations,
        "personas": personas,
        "events_by_id": {e["id"]: e for e in events},
        "persona_by_id": {p["persona_id"]: p for p in personas},
    }


def _index_relations(relations: list[dict]) -> dict[str, dict[str, list[str]]]:
    """Build relation indices.

    Returns dict: {edge_type: {"by_source": {src_id: [target_ids]},
                               "by_target": {target_id: [source_ids]}}}.
    """
    idx: dict[str, dict[str, dict[str, list[str]]]] = defaultdict(
        lambda: {"by_source": defaultdict(list), "by_target": defaultdict(list)}
    )
    for r in relations:
        rel = r["relation"]
        idx[rel]["by_source"][r["source"]].append(r["target"])
        idx[rel]["by_target"][r["target"]].append(r["source"])
    # Materialise as plain dicts for safety
    return {
        rel: {
            "by_source": dict(v["by_source"]),
            "by_target": dict(v["by_target"]),
        }
        for rel, v in idx.items()
    }


# ---------------------------------------------------------------------------
# Per-category candidate sampling + ground-truth projection
# ---------------------------------------------------------------------------


def _personas_to_names(graph: dict, persona_ids: list[str]) -> list[str]:
    out = []
    for pid in persona_ids:
        p = graph["persona_by_id"].get(pid)
        if p:
            out.append(p.get("display_name", pid))
        else:
            out.append(pid)
    return out


def _candidates_c1(graph: dict, idx: dict) -> list[dict]:
    """C1: events with a `supersedes` incoming OR outgoing edge.

    For each pair (A supersedes B), the question is about the topic
    of B, with prior_value = B.decision and current_value = A.decision.
    """
    out = []
    for rel_type in (RelationType.SUPERSEDES, RelationType.REVERSES):
        for src, targets in idx.get(rel_type, {}).get("by_source", {}).items():
            src_evt = graph["events_by_id"].get(src)
            if not src_evt:
                continue
            for tgt in targets:
                tgt_evt = graph["events_by_id"].get(tgt)
                if not tgt_evt:
                    continue
                out.append({
                    "kind": "C1",
                    "source_event": src_evt,
                    "target_event": tgt_evt,
                    "topic": tgt_evt.get("summary", "")[:120],
                    "prior_value": tgt_evt.get("decision", ""),
                    "current_value": src_evt.get("decision", ""),
                    "change_date": str(src_evt.get("occurred_at", "")),
                    "change_reason": src_evt.get("reason_canonical", ""),
                    "evidence_artefacts": [
                        s.get("slot_id") for s in src_evt.get("evidence_in_corpus", [])
                        if isinstance(s, dict)
                    ] + [
                        s.get("slot_id") for s in tgt_evt.get("evidence_in_corpus", [])
                        if isinstance(s, dict)
                    ],
                })
    return out


def _candidates_c2(graph: dict) -> list[dict]:
    """C2: strategic_decision events with ≥2 alternatives_considered."""
    out = []
    for e in graph["events"]:
        if e.get("type") != "strategic_decision":
            continue
        alts = e.get("alternatives_considered", []) or []
        if len(alts) < 2:
            continue
        out.append({
            "kind": "C2",
            "event": e,
            "topic": e.get("summary", "")[:120],
            "decision": e.get("decision", ""),
            "deciders": _personas_to_names(graph, e.get("participants", [])),
            "decision_date": str(e.get("occurred_at", "")),
            "alternatives": alts,
            "decision_reason": e.get("reason_canonical", ""),
            "evidence_artefacts": [
                s.get("slot_id") for s in e.get("evidence_in_corpus", [])
                if isinstance(s, dict)
            ],
        })
    return out


def _candidates_c3(graph: dict, idx: dict) -> list[dict]:
    """C3: events with a `retroactively_corrected_by` outgoing edge."""
    out = []
    for src, targets in idx.get(RelationType.RETROACTIVELY_CORRECTED_BY, {}).get("by_source", {}).items():
        src_evt = graph["events_by_id"].get(src)
        if not src_evt:
            continue
        for tgt in targets:
            tgt_evt = graph["events_by_id"].get(tgt)
            if not tgt_evt:
                continue
            out.append({
                "kind": "C3",
                "topic": src_evt.get("summary", "")[:120],
                "original_value": src_evt.get("decision", ""),
                "original_recorded_at": str(src_evt.get("recorded_at", src_evt.get("occurred_at", ""))),
                "corrected_value": tgt_evt.get("decision", ""),
                "correction_recorded_at": str(tgt_evt.get("recorded_at", tgt_evt.get("occurred_at", ""))),
                "true_occurred_at": str(src_evt.get("occurred_at", "")),
                "evidence_artefacts": [
                    s.get("slot_id") for s in src_evt.get("evidence_in_corpus", []) if isinstance(s, dict)
                ] + [
                    s.get("slot_id") for s in tgt_evt.get("evidence_in_corpus", []) if isinstance(s, dict)
                ],
            })
    return out


def _candidates_c4(graph: dict, idx: dict) -> list[dict]:
    """C4: audit replay — pick supersession-chains, ask "as of <middle date>".

    For a chain A → supersedes → B → supersedes → C, when asked
    "what did we know as of (a date between A and B)", the answer is:
    - asof_facts: B's value (was current at that date)
    - changed_facts: B's value (has since been superseded)
    - replacements: A's value (and onward in the chain)
    - evidence: ALL artefacts from every event in the chain — the
      system-under-test must navigate the whole chain to answer
      correctly, not just the two adjacent events.
    """
    from datetime import datetime, timedelta

    out = []
    by_source = idx.get(RelationType.SUPERSEDES, {}).get("by_source", {})
    by_target = idx.get(RelationType.SUPERSEDES, {}).get("by_target", {})

    def _walk_chain_back(start: str, visited: set) -> list[str]:
        """Walk all supersedes targets reachable from `start` (older versions)."""
        if start in visited:
            return []
        visited.add(start)
        chain = [start]
        for older in by_source.get(start, []):
            chain.extend(_walk_chain_back(older, visited))
        return chain

    def _walk_chain_forward(start: str, visited: set) -> list[str]:
        """Walk all supersedes sources from `start` (newer versions)."""
        if start in visited:
            return []
        visited.add(start)
        chain = [start]
        for newer in by_target.get(start, []):
            chain.extend(_walk_chain_forward(newer, visited))
        return chain

    for src, targets in by_source.items():
        src_evt = graph["events_by_id"].get(src)
        if not src_evt:
            continue
        for tgt in targets:
            tgt_evt = graph["events_by_id"].get(tgt)
            if not tgt_evt:
                continue
            try:
                tgt_date = datetime.fromisoformat(str(tgt_evt.get("occurred_at", "")))
                as_of = (tgt_date + timedelta(days=30)).date().isoformat()
            except (ValueError, TypeError):
                continue

            # Full chain: older versions reachable from tgt (was current
            # at as_of) + newer versions reachable from src (replacements).
            older_chain = _walk_chain_back(tgt, set())
            newer_chain = _walk_chain_forward(src, set())
            full_chain_ids = list({*older_chain, *newer_chain})

            # Evidence: gather from EVERY event in the chain. The
            # system must reconstruct as_of state from the whole trail,
            # not just one edge.
            evidence: list[str] = []
            for eid in full_chain_ids:
                e = graph["events_by_id"].get(eid)
                if not e:
                    continue
                for s in e.get("evidence_in_corpus", []) or []:
                    if isinstance(s, dict) and s.get("slot_id"):
                        evidence.append(s["slot_id"])

            # asof_facts: tgt's value (current at as_of). May extend
            # to include any older sibling that was also current then,
            # but at v0.1 we keep it to tgt.
            # changed_facts: tgt's value + anything reachable via
            # newer_chain (i.e. all the things superseded since).
            # replacements: the most-recent value (the head of
            # newer_chain).
            head_event = (
                graph["events_by_id"].get(newer_chain[-1])
                if newer_chain else src_evt
            )

            out.append({
                "kind": "C4",
                "topic": tgt_evt.get("summary", "")[:120],
                "as_of_date": as_of,
                "asof_facts": [tgt_evt.get("decision", "")],
                "changed_facts": [
                    graph["events_by_id"].get(eid, {}).get("decision", "")
                    for eid in older_chain + newer_chain
                    if eid != newer_chain[-1] if newer_chain
                ],
                "replacements": [head_event.get("decision", "")],
                "chain_event_ids": full_chain_ids,
                "evidence_artefacts": evidence,
            })
    return out


# Testimony-type heuristic by genre (see design doc §9 C5).
# Direct testimony = artefacts where speakers/authors say things in
# their own voice in real time. Inference = artefacts that summarise
# or interpret what others said/decided after the fact.
_TESTIMONY_GENRES = {
    "slack_thread", "meeting_transcript", "email_thread",
    "customer_call_transcript",
}
_INFERENCE_GENRES = {
    "postmortem", "retrospective", "adr", "rfc", "notion_doc",
    "incident_report", "meeting_notes", "customer_call_notes",
    "sales_crm_entry",
}


def _testimony_type(genre: str) -> str:
    g = (genre or "").lower().strip()
    if g in _TESTIMONY_GENRES:
        return "direct_testimony"
    if g in _INFERENCE_GENRES:
        return "inference"
    return "unknown"


def _candidates_c5(graph: dict) -> list[dict]:
    """C5: events with ≥3 evidence_in_corpus entries — justification chains.

    Each evidence slot is tagged direct_testimony vs inference by genre
    so the question's rubric can grade per-artefact attribution.
    """
    out = []
    for e in graph["events"]:
        evidence = e.get("evidence_in_corpus", []) or []
        if len(evidence) < 3:
            continue
        evidence_with_types = []
        for s in evidence:
            if not isinstance(s, dict):
                continue
            g = s.get("genre", "?")
            evidence_with_types.append({
                "slot_id": s.get("slot_id"),
                "genre": g,
                "role": s.get("role", "?"),
                "author": s.get("author", "?"),
                "testimony_type": _testimony_type(g),
            })
        out.append({
            "kind": "C5",
            "claim": e.get("decision", ""),
            "topic": e.get("summary", "")[:120],
            "evidence_summary": [
                f"{i+1}. {ev['genre']} by {ev['author']} ({ev['role']}) "
                f"→ {ev['testimony_type']}"
                for i, ev in enumerate(evidence_with_types)
            ],
            "evidence_types": [ev["genre"] for ev in evidence_with_types],
            "testimony_attribution": [
                {"slot_id": ev["slot_id"], "testimony_type": ev["testimony_type"]}
                for ev in evidence_with_types
            ],
            "inferential_steps": e.get("reason_canonical", ""),
            "evidence_artefacts": [ev["slot_id"] for ev in evidence_with_types if ev["slot_id"]],
        })
    return out


def _candidates_c6(graph: dict, idx: dict) -> list[dict]:
    """C6: contradiction_episode events with a `contradicts` edge.

    The C6 question shape requires TWO DIFFERENT PEOPLE making the
    contradictory claims (Party A vs Party B). When both events involve
    the same person, we either pick disjoint participants OR drop the
    candidate — a person contradicting themselves over time doesn't fit
    the "contradiction-with-attribution" probe shape.
    """
    out = []
    for src, targets in idx.get(RelationType.CONTRADICTS, {}).get("by_source", {}).items():
        src_evt = graph["events_by_id"].get(src)
        if not src_evt:
            continue
        for tgt in targets:
            tgt_evt = graph["events_by_id"].get(tgt)
            if not tgt_evt:
                continue
            src_participants = src_evt.get("participants", []) or []
            tgt_participants = tgt_evt.get("participants", []) or []
            if not src_participants or not tgt_participants:
                continue

            # Prefer a party from each side who is NOT in the other side.
            # If no disjoint participant exists, skip — this contradiction
            # isn't between two named parties.
            src_unique = [p for p in src_participants if p not in tgt_participants]
            tgt_unique = [p for p in tgt_participants if p not in src_participants]
            if not src_unique or not tgt_unique:
                logger.debug(
                    "C6 skipping %s↔%s: no disjoint participants "
                    "(src=%s tgt=%s)", src, tgt, src_participants, tgt_participants,
                )
                continue
            party_a = src_unique[0]
            party_b = tgt_unique[0]
            party_a_name = _personas_to_names(graph, [party_a])[0]
            party_b_name = _personas_to_names(graph, [party_b])[0]
            if party_a_name == party_b_name:
                # Shouldn't happen given disjoint filter, but belt-and-
                # braces in case persona names collide across IDs.
                continue

            # Check if a resolved_by edge exists from src or tgt
            resolution_status = "unresolved"
            resolution_details = ""
            resolved_from_src = idx.get(RelationType.RESOLVED_BY, {}).get("by_source", {}).get(src, [])
            resolved_from_tgt = idx.get(RelationType.RESOLVED_BY, {}).get("by_source", {}).get(tgt, [])
            if resolved_from_src or resolved_from_tgt:
                resolver_id = (resolved_from_src + resolved_from_tgt)[0]
                resolver_evt = graph["events_by_id"].get(resolver_id, {})
                resolution_status = "resolved"
                resolution_details = resolver_evt.get("decision", "")

            out.append({
                "kind": "C6",
                "topic": src_evt.get("summary", "")[:120],
                "party_a": party_a,
                "party_a_name": party_a_name,
                "party_a_claim": src_evt.get("decision", ""),
                "party_a_date": str(src_evt.get("occurred_at", "")),
                "party_b": party_b,
                "party_b_name": party_b_name,
                "party_b_claim": tgt_evt.get("decision", ""),
                "party_b_date": str(tgt_evt.get("occurred_at", "")),
                "resolution_status": resolution_status,
                "resolution_details": resolution_details,
                "evidence_artefacts": [
                    s.get("slot_id") for s in src_evt.get("evidence_in_corpus", []) if isinstance(s, dict)
                ] + [
                    s.get("slot_id") for s in tgt_evt.get("evidence_in_corpus", []) if isinstance(s, dict)
                ],
            })
    return out


# ---------------------------------------------------------------------------
# HARD lineage candidates — walk long supersession/reversal chains
# ---------------------------------------------------------------------------


def _candidates_hard(graph: dict, idx: dict) -> list[dict]:
    """Find chains of length ≥3 (supersedes/reverses/re_attempts) and
    build 'trace the complete lineage' questions over them.

    These are the hard, multi-hop, cross-year questions only a system
    with full lineage memory can answer — the answer is spread across
    every event in the chain and all their artefacts.
    """
    chain_rels = (RelationType.SUPERSEDES, RelationType.REVERSES, RelationType.RE_ATTEMPTS)
    # Build forward adjacency over chain relations: target (older) → source (newer)
    nxt: dict[str, list[str]] = defaultdict(list)
    for rel in chain_rels:
        for src, targets in idx.get(rel, {}).get("by_source", {}).items():
            for tgt in targets:
                # src is newer, tgt is older → edge older→newer
                nxt[tgt].append(src)

    # Find chain roots (events with no incoming chain edge pointing to them
    # as a "newer" — i.e. not the source of any chain edge) then walk forward.
    all_sources = {s for rel in chain_rels for s in idx.get(rel, {}).get("by_source", {})}
    all_targets = {t for rel in chain_rels for ts in idx.get(rel, {}).get("by_source", {}).values() for t in ts}
    roots = all_targets - all_sources  # oldest events in chains

    out = []
    seen_chains: set[tuple] = set()
    for root in roots:
        # Walk the longest path forward from root
        chain = [root]
        cur = root
        guard = 0
        while nxt.get(cur) and guard < 20:
            cur = nxt[cur][0]  # follow first newer version
            chain.append(cur)
            guard += 1
        if len(chain) < 3:
            continue
        key = tuple(chain)
        if key in seen_chains:
            continue
        seen_chains.add(key)

        chain_events = [graph["events_by_id"].get(e) for e in chain]
        chain_events = [e for e in chain_events if e]
        if len(chain_events) < 3:
            continue

        evidence = []
        for e in chain_events:
            for s in e.get("evidence_in_corpus", []) or []:
                if isinstance(s, dict) and s.get("slot_id"):
                    evidence.append(s["slot_id"])

        years = sorted({str(e.get("occurred_at", ""))[:4] for e in chain_events if e.get("occurred_at")})
        out.append({
            "kind": "HARD",
            "topic": chain_events[0].get("summary", "")[:120],
            "chain_length": len(chain_events),
            "year_span": f"{years[0]}-{years[-1]}" if years else "?",
            "chain_steps": [
                {
                    "id": e["id"],
                    "date": str(e.get("occurred_at", "")),
                    "decision": str(e.get("decision", ""))[:200],
                    "reason": str(e.get("reason_canonical", ""))[:150],
                    "participants": _personas_to_names(graph, e.get("participants", [])),
                }
                for e in chain_events
            ],
            "evidence_artefacts": evidence,
        })
    # Longest chains first
    out.sort(key=lambda c: -c["chain_length"])
    return out


# ---------------------------------------------------------------------------
# Phrasing + rubric LLM calls
# ---------------------------------------------------------------------------


_PARAPHRASE_RE = re.compile(r"###\s*Q:\s*(.+?)(?=\n###\s*Q:|\Z)", re.DOTALL)


def _parse_paraphrases(text: str) -> list[str]:
    text = normalize_smart_quotes(strip_code_fences(text)).strip()
    return [m.group(1).strip() for m in _PARAPHRASE_RE.finditer(text)]


_LEAK_TOKEN_RE = re.compile(r"[A-Za-z0-9'-]+")
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "and", "or",
    "what", "when", "who", "why", "how", "which", "is", "was", "were",
    "did", "do", "does", "did", "as", "by", "be", "been", "being", "this",
    "that", "these", "those", "with", "from", "into", "about", "you",
}


def _leak_score(question: str, answer_text: str) -> float:
    """Token overlap ratio between question and answer (excluding stopwords).

    A high score means the question leaks the answer. Returns 0..1.
    """
    q_tokens = {t.lower() for t in _LEAK_TOKEN_RE.findall(question) if t.lower() not in _STOPWORDS}
    a_tokens = {t.lower() for t in _LEAK_TOKEN_RE.findall(answer_text) if t.lower() not in _STOPWORDS}
    if not q_tokens or not a_tokens:
        return 0.0
    overlap = q_tokens & a_tokens
    return len(overlap) / max(1, len(a_tokens))


def _pick_best_paraphrase(paraphrases: list[str], answer_text: str) -> str | None:
    """Pick the paraphrase with the lowest leak score, given a tied length tie-break."""
    if not paraphrases:
        return None
    scored = [(_leak_score(p, answer_text), -len(p), p) for p in paraphrases]
    scored.sort()  # lowest leak first
    return scored[0][2]


async def _phrase_question(
    llm: HelixLLM, candidate: dict,
) -> tuple[str | None, list[str]]:
    """LLM call to phrase the question. Returns (chosen, all_paraphrases)."""
    cat = candidate["kind"]
    if cat == "C1":
        prompt = _load_template("c1_supersession_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            prior_value=candidate["prior_value"][:300],
            current_value=candidate["current_value"][:300],
            change_date=candidate["change_date"],
            change_reason=candidate["change_reason"][:300],
        )
        answer_text = " ".join([
            candidate["prior_value"], candidate["current_value"],
            candidate["change_date"], candidate["change_reason"],
        ])
    elif cat == "C2":
        prompt = _load_template("c2_decision_provenance_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            decision=candidate["decision"][:300],
            participants_names=", ".join(candidate["deciders"]),
            decision_date=candidate["decision_date"],
            alternatives="; ".join(candidate["alternatives"]),
            decision_reason=candidate["decision_reason"][:300],
        )
        answer_text = " ".join([
            candidate["decision"], "; ".join(candidate["deciders"]),
            candidate["decision_date"], "; ".join(candidate["alternatives"]),
            candidate["decision_reason"],
        ])
    elif cat == "C3":
        prompt = _load_template("c3_bitemporal_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            original_value=candidate["original_value"][:300],
            original_recorded_at=candidate["original_recorded_at"],
            corrected_value=candidate["corrected_value"][:300],
            correction_recorded_at=candidate["correction_recorded_at"],
            true_occurred_at=candidate["true_occurred_at"],
        )
        answer_text = " ".join([
            candidate["original_value"], candidate["corrected_value"],
            candidate["original_recorded_at"], candidate["correction_recorded_at"],
        ])
    elif cat == "C4":
        prompt = _load_template("c4_audit_replay_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            as_of_date=candidate["as_of_date"],
            asof_facts_block="; ".join(candidate["asof_facts"][:3]),
            changed_facts_block="; ".join(candidate["changed_facts"][:3]),
            replacements_block="; ".join(candidate["replacements"][:3]),
        )
        answer_text = " ".join(
            candidate["asof_facts"] + candidate["changed_facts"] + candidate["replacements"]
        )
    elif cat == "C5":
        prompt = _load_template("c5_justification_phrasing.md").format(
            claim_one_liner=candidate["claim"][:160],
            topic_one_liner=candidate["topic"],
            evidence_summary_block="\n".join(candidate["evidence_summary"]),
            evidence_types=", ".join(set(candidate["evidence_types"])),
            inferential_steps=candidate["inferential_steps"][:200],
        )
        answer_text = " ".join(candidate["evidence_summary"]) + " " + candidate["claim"]
    elif cat == "C6":
        prompt = _load_template("c6_contradiction_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            party_a_name=candidate["party_a_name"],
            party_a_claim=candidate["party_a_claim"][:200],
            party_a_date=candidate["party_a_date"],
            party_b_name=candidate["party_b_name"],
            party_b_claim=candidate["party_b_claim"][:200],
            party_b_date=candidate["party_b_date"],
            resolution_status=candidate["resolution_status"],
            resolution_details=candidate["resolution_details"][:200],
        )
        answer_text = " ".join([
            candidate["party_a_claim"], candidate["party_b_claim"],
            candidate["resolution_details"],
        ])
    elif cat == "HARD":
        chain_block = "\n".join(
            f"  {i+1}. [{s['date']}] {s['decision']} "
            f"(by {', '.join(s['participants']) or '?'}; reason: {s['reason']})"
            for i, s in enumerate(candidate["chain_steps"])
        )
        prompt = _load_template("hard_lineage_phrasing.md").format(
            topic_one_liner=candidate["topic"],
            chain_length=candidate["chain_length"],
            year_span=candidate["year_span"],
            chain_block=chain_block,
        )
        answer_text = " ".join(
            f"{s['decision']} {s['date']} {' '.join(s['participants'])} {s['reason']}"
            for s in candidate["chain_steps"]
        )
    else:
        return None, []

    text = await llm.call_text(
        stage="E",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=3000,
        temperature=0.7,
    )
    paraphrases = _parse_paraphrases(text)
    chosen = _pick_best_paraphrase(paraphrases, answer_text)
    return chosen, paraphrases


_RUBRIC_LINE_RE = re.compile(
    r"^[-*]\s*([A-Z0-9]+\.sub\d+)\s*\|\s*([0-9.]+)\s*\|\s*(.+?)(?:\s*\|\s*FAIL:\s*(.+))?$"
)


async def _generate_rubric(
    llm: HelixLLM, candidate: dict, question_text: str, ground_truth: dict,
) -> list[dict]:
    """LLM call to generate the rubric sub-points."""
    cat = candidate["kind"]
    subpoints_list = ", ".join(CATEGORY_SUBPOINTS[cat])
    gt_block = "\n".join(f"  - {k}: {json.dumps(v, default=str)[:200]}" for k, v in ground_truth.items())

    prompt = _load_template("rubric_subpoints.md").format(
        question_text=question_text,
        ground_truth_block=gt_block,
        category=cat,
        subpoint_structure=subpoints_list,
    )
    text = await llm.call_text(
        stage="E",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=2500,
    )
    text = strip_code_fences(text)
    rubric: list[dict] = []
    for line in text.splitlines():
        m = _RUBRIC_LINE_RE.match(line.strip())
        if not m:
            continue
        sub_id, max_pts, criterion, fail_criterion = m.groups()
        try:
            max_score = float(max_pts)
        except ValueError:
            continue
        rubric.append({
            "id": sub_id,
            "max_score": max_score,
            "criterion": criterion.strip(),
            "fail_criterion": (fail_criterion or "").strip() or None,
        })
    return rubric


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Run Stage E: generate questions from the source-of-truth graph."""
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size: {size}; expected one of {list(SIZE_PARAMS)}")
    params = SIZE_PARAMS[size]

    data_root = Path(data_dir)
    out_file = data_root / "questions_draft.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_e.jsonl")

    graph = _load_graph(data_root)
    idx = _index_relations(graph["relations"])

    # Load the corpus index so we can filter evidence_artefact_ids
    # against what was ACTUALLY written by Stage C. Stage C occasionally
    # fails to write a slot (empty content; HTTP retry that didn't
    # recover); Stage B's event records still reference those slot_ids
    # in evidence_in_corpus. We filter at question-creation time so
    # questions only reference real on-disk artefacts.
    corpus_index_path = data_root / "corpus_index.jsonl"
    on_disk_slots: set[str] = set()
    if corpus_index_path.exists():
        for line in corpus_index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            on_disk_slots.add(rec["slot_id"])
        logger.info("Stage E: loaded %d on-disk slot_ids from corpus_index", len(on_disk_slots))
    else:
        logger.warning("Stage E: corpus_index.jsonl missing — cannot filter evidence_artefact_ids")

    # Sample candidates per category
    candidates_by_cat: dict[str, list[dict]] = {
        "C1": _candidates_c1(graph, idx),
        "C2": _candidates_c2(graph),
        "C3": _candidates_c3(graph, idx),
        "C4": _candidates_c4(graph, idx),
        "C5": _candidates_c5(graph),
        "C6": _candidates_c6(graph, idx),
    }

    target_per_cat = params["per_category"]
    max_total = params["max_total"]
    hard_target = params.get("hard_target", 0)

    # Cap per category at the target (or what we can produce)
    selected: list[dict] = []
    for cat, cands in candidates_by_cat.items():
        logger.info(
            "Stage E candidates for %s: %d available (target %d)",
            cat, len(cands), target_per_cat,
        )
        selected.extend(cands[:target_per_cat])

    # HARD multi-hop lineage questions (cross-year chain synthesis).
    if hard_target > 0:
        hard_cands = _candidates_hard(graph, idx)
        logger.info(
            "Stage E candidates for HARD: %d available (target %d)",
            len(hard_cands), hard_target,
        )
        selected.extend(hard_cands[:hard_target])

    if len(selected) > max_total:
        selected = selected[:max_total]

    llm = HelixLLM()
    questions: list[dict] = []
    if out_file.exists():
        questions = [
            json.loads(line)
            for line in out_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        logger.info("Stage E: %d questions already on disk", len(questions))

    try:
        for idx_q, cand in enumerate(selected, start=1):
            qid = f"Q-{idx_q:04d}"
            unit_id = f"q-{qid}"
            if cp.is_done(unit_id):
                continue

            # Phrase + pick best paraphrase
            chosen, paraphrases = await _phrase_question(llm, cand)
            if not chosen:
                logger.warning("Stage E %s (%s): no paraphrase parsed — skipping", qid, cand["kind"])
                cp.mark_done(unit_id, status="skip-no-paraphrase")
                continue

            # Ground-truth structured answer (the deterministic projection)
            ground_truth = _project_ground_truth(cand)

            # Rubric
            rubric = await _generate_rubric(llm, cand, chosen, ground_truth)
            if not rubric:
                logger.warning("Stage E %s: no rubric parsed — keeping question with empty rubric", qid)

            # Filter evidence to slots actually on disk. If on_disk_slots
            # is empty (corpus_index missing), pass through unfiltered —
            # Stage F will still catch this.
            raw_evidence = list({a for a in cand.get("evidence_artefacts", []) if a})
            if on_disk_slots:
                filtered_evidence = [sid for sid in raw_evidence if sid in on_disk_slots]
                if len(filtered_evidence) < len(raw_evidence):
                    logger.info(
                        "Stage E %s: filtered %d → %d evidence_artefact_ids (skipped %d missing on disk)",
                        qid, len(raw_evidence), len(filtered_evidence),
                        len(raw_evidence) - len(filtered_evidence),
                    )
                # If filtering wiped ALL evidence, drop the question
                if not filtered_evidence:
                    logger.warning(
                        "Stage E %s [%s]: ALL %d evidence artefacts missing on disk; skipping question",
                        qid, cand["kind"], len(raw_evidence),
                    )
                    cp.mark_done(unit_id, status="skip-no-evidence")
                    continue
                evidence_for_record = filtered_evidence
            else:
                evidence_for_record = raw_evidence

            difficulty = _difficulty_for(
                len(evidence_for_record),
                chain_len=cand.get("chain_length", 1),
            )
            record = {
                "id": qid,
                "category": cand["kind"],
                "difficulty": difficulty,
                "text": chosen,
                "paraphrases": paraphrases,
                "ground_truth_answer": ground_truth,
                "rubric_subpoints": rubric,
                "evidence_artefact_ids": evidence_for_record,
                "metadata": {
                    "leak_score": _leak_score(chosen, " ".join(str(v) for v in ground_truth.values())),
                    "chain_length": cand.get("chain_length", 1),
                },
            }
            questions.append(record)
            with out_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp.mark_done(unit_id, status="ok", category=cand["kind"])
            logger.info("Stage E wrote %s [%s] leak=%.2f", qid, cand["kind"], record["metadata"]["leak_score"])

        # Summary report
        per_cat = defaultdict(int)
        per_diff = defaultdict(int)
        for q in questions:
            per_cat[q["category"]] += 1
            per_diff[q.get("difficulty", "?")] += 1
        logger.info(
            "Stage E complete. %d questions written. Per category: %s. Per difficulty: %s",
            len(questions), dict(per_cat), dict(per_diff),
        )
    finally:
        await llm.aclose()


def _project_ground_truth(candidate: dict) -> dict:
    """Project the candidate's category-specific fields into a uniform
    ground_truth_answer dict for storage."""
    cat = candidate["kind"]
    if cat == "C1":
        return {
            "current_value": candidate["current_value"],
            "prior_value": candidate["prior_value"],
            "change_date": candidate["change_date"],
            "change_reason": candidate["change_reason"],
        }
    if cat == "C2":
        return {
            "decision": candidate["decision"],
            "deciders": candidate["deciders"],
            "decision_date": candidate["decision_date"],
            "alternatives": candidate["alternatives"],
            "deciding_factor": candidate["decision_reason"],
        }
    if cat == "C3":
        return {
            "original_value": candidate["original_value"],
            "corrected_value": candidate["corrected_value"],
            "original_recorded_at": candidate["original_recorded_at"],
            "correction_recorded_at": candidate["correction_recorded_at"],
            "true_occurred_at": candidate["true_occurred_at"],
        }
    if cat == "C4":
        return {
            "as_of_date": candidate["as_of_date"],
            "asof_facts": candidate["asof_facts"],
            "changed_facts": candidate["changed_facts"],
            "replacements": candidate["replacements"],
        }
    if cat == "C5":
        return {
            "claim": candidate["claim"],
            "evidence_summary": candidate["evidence_summary"],
            "evidence_types": candidate["evidence_types"],
            "testimony_attribution": candidate.get("testimony_attribution", []),
            "inferential_steps": candidate["inferential_steps"],
        }
    if cat == "C6":
        return {
            "party_a": candidate["party_a_name"],
            "party_a_claim": candidate["party_a_claim"],
            "party_a_date": candidate["party_a_date"],
            "party_b": candidate["party_b_name"],
            "party_b_claim": candidate["party_b_claim"],
            "party_b_date": candidate["party_b_date"],
            "resolution_status": candidate["resolution_status"],
            "resolution_details": candidate["resolution_details"],
        }
    if cat == "HARD":
        return {
            "topic": candidate["topic"],
            "chain_length": candidate["chain_length"],
            "year_span": candidate["year_span"],
            "chain_steps": candidate["chain_steps"],
            "current_state": candidate["chain_steps"][-1]["decision"] if candidate.get("chain_steps") else "",
        }
    return {}
