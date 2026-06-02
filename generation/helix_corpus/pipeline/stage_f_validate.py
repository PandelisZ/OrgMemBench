"""Stage F — Substrate validation.

The role of Stage F is to check that **the generation prompts did what
we asked them to do** — i.e. each evidence artefact actually carries
the canonical facts its slot in the source-of-truth graph said it
would carry. This is a per-artefact substrate check, not a
"can-you-answer-the-question-from-the-corpus" check.

Why this re-framing matters: an earlier Stage F implementation gave
gpt-oss the full evidence-artefact dump for each question and scored
whether it could recover the canonical answer. That was, in effect,
running a long-context baseline against the corpus — exactly the
capability context-graph memory exists to OUT-perform. Treating those
failures as "the data is bad" was wrong: the failures are the SIGNAL
the eventual Phase 8 harness will measure when comparing systems
(graphify vs Mem0 vs vector vs long-context).

So Stage F now does only what it should: confirm generation worked.

Three checks:

1. **Per-artefact substrate check** (LLM, one small call per artefact):
   For each evidence artefact, load JUST that artefact's text and a
   short list of canonical facts that should be present (derived from
   the event's record). Ask gpt-oss yes/no/partial for each fact.

2. **Per-question structural check** (no LLM):
   - Schema sanity (well-formed Question record).
   - Every evidence_artefact_id resolves to a real artefact on disk.
   - Roll-up: does the question's evidence trail collectively contain
     all its canonical answer's key facts (computed from the per-
     artefact results)?

3. **Per-question memorisation check** (LLM, one short call per
   question, no corpus context): if gpt-oss answers the question
   correctly without any evidence, the question is solvable from
   world knowledge alone and gets dropped.

Outputs:
  - artefact_validation_report.jsonl: one record per artefact
  - question_validation_report.jsonl: one record per question
  - benchmark_v0.0.jsonl: passing question set (substrate-complete +
    not memorisable)
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM
from helix_corpus.parsers import strip_code_fences

logger = logging.getLogger("helix_corpus.stage_f")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_f"

# Memorisation: if gpt-oss scores ≥ this without corpus, drop the
# question — it's world-knowledge solvable.
MEMORISATION_THRESHOLD = 0.5

# Substrate completeness: roll-up of per-fact yes/no/partial across all
# of a question's evidence artefacts. A question is "substrate-
# complete" if its canonical facts each appear (yes or partial) in at
# least ONE of its evidence artefacts.
SUBSTRATE_COMPLETE_REQUIRED = 0.7  # fraction of canonical facts that must be present

# EMERGENT (Tier-3) questions validate in UNION mode: the answer is a
# pattern with N facets, each *exhibited* (not stated) in scattered
# evidence artefacts. A facet is covered if ANY of its evidence artefacts
# exhibits it; the question passes if at least this fraction of facets
# are covered (allows one weak facet without failing the whole question).
EMERGENT_FACET_REQUIRED = 0.8


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


_FACET_YES_RE = re.compile(r"\b(yes|present|exhibited|supported)\b", re.I)


async def _check_one_facet(llm: HelixLLM, facet: str, artefact_text: str) -> bool:
    """Does this artefact EXHIBIT the facet (a behaviour), even implicitly?"""
    prompt = _load_template("emergent_facet_check.md").format(
        facet=facet, artefact_text=artefact_text[:4000],
    )
    out = await llm.call_text(stage="F", user=prompt, reasoning_effort="low", max_tokens=600)
    first = (out or "").strip().splitlines()[0] if out.strip() else ""
    return bool(_FACET_YES_RE.search(first))


async def _check_emergent_facets(
    llm: HelixLLM, q: dict, index_by_slot: dict, data_root: Path,
) -> list[bool]:
    """Union-mode: each facet is covered if ANY of its evidence artefacts
    exhibits it. Returns one bool per facet."""
    facets = (q.get("ground_truth_answer", {}) or {}).get("facets", []) or []
    # facet_index -> evidence_ids, from the rubric sub-points
    facet_ev: dict[int, list[str]] = {}
    for sp in q.get("rubric_subpoints", []) or []:
        if isinstance(sp, dict) and "facet_index" in sp:
            facet_ev[sp["facet_index"]] = sp.get("evidence_ids", []) or []
    all_ev = q.get("evidence_artefact_ids", []) or []
    results: list[bool] = []
    for fi, facet in enumerate(facets):
        ev_ids = facet_ev.get(fi) or all_ev
        covered = False
        for sid in ev_ids:
            rec = index_by_slot.get(sid)
            if not rec:
                continue
            path = data_root / rec["path"]
            if not path.exists():
                continue
            if await _check_one_facet(llm, facet, path.read_text(encoding="utf-8")):
                covered = True
                break
        results.append(covered)
    return results


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    questions = [
        json.loads(line)
        for line in (data_dir / "questions_draft.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Tier-3 EMERGENT questions live in a separate file (Stage G); fold
    # them into the validated set so the benchmark is the union of
    # recorded (T1/T2) + emergent (T3) questions.
    emergent_path = data_dir / "emergent_questions.jsonl"
    if emergent_path.exists():
        questions += [
            json.loads(line)
            for line in emergent_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    corpus_index = [
        json.loads(line)
        for line in (data_dir / "corpus_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events = [
        json.loads(line)
        for line in (data_dir / "source_of_truth" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    personas = []
    personas_path = data_dir / "helix_canon" / "personas.jsonl"
    if personas_path.exists():
        personas = [
            json.loads(line)
            for line in personas_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return {
        "questions": questions,
        "corpus_index": corpus_index,
        "events": events,
        "personas": personas,
        "index_by_slot": {r["slot_id"]: r for r in corpus_index},
        "events_by_id": {e["id"]: e for e in events},
        "persona_by_id": {p["persona_id"]: p for p in personas},
    }


# ---------------------------------------------------------------------------
# Per-artefact substrate check
# ---------------------------------------------------------------------------


def _canonical_facts_for_artefact(
    artefact_record: dict, event: dict, events_by_id: dict[str, dict],
    persona_by_id: dict[str, dict] | None = None,
) -> list[str]:
    """Compute the list of canonical facts the artefact's slot was
    supposed to embed.

    Different roles get different fact lists:
    - primary: decision + reason + participants + date + alternatives
    - secondary: at least topic + participants + decision hint
    - For events with corrects_event_id: ALSO the prior event's
      decision + the bi-temporal date pair.
    """
    role = (artefact_record.get("role") or "primary").lower()
    facts: list[str] = []

    decision = str(event.get("decision", "")).strip()
    reason = str(event.get("reason_canonical", "")).strip()
    participants = event.get("participants", []) or []
    occurred = str(event.get("occurred_at", "")).strip()
    summary = str(event.get("summary", "")).strip()
    alternatives = event.get("alternatives_considered", []) or []

    # Topic / decision — required for any non-noise role
    if decision:
        facts.append(f"The decision: \"{decision[:200]}\"")
    if role == "primary" and reason:
        facts.append(f"The reason: \"{reason[:200]}\"")

    # Participants — at least one named. Resolve persona IDs → display
    # names: artefacts use human-readable names ("Maya Patel"), so the
    # check (and any deterministic repair append) must use names, not
    # the P-XXXX IDs.
    if participants:
        pmap = persona_by_id or {}
        resolved = []
        for pid in participants[:3]:
            p = pmap.get(pid)
            resolved.append(p.get("display_name", pid) if p else pid)
        names_for_check = ", ".join(resolved)
        facts.append(f"At least one participant by name (any of: {names_for_check})")

    # Date — required for primary, optional for secondary
    if occurred and role == "primary":
        facts.append(f"The date: {occurred}")

    # Alternatives — required for strategic_decision primary artefacts
    if role == "primary" and alternatives and event.get("type") == "strategic_decision":
        alt_str = "; ".join(str(a)[:80] for a in alternatives[:3])
        facts.append(f"At least one alternative considered (any of: {alt_str})")

    # C3 bi-temporal: if this event corrects a prior one, the artefact
    # should narrate BOTH timelines.
    corrects = event.get("corrects_event_id")
    if corrects and role == "primary":
        prior = events_by_id.get(corrects, {})
        if prior:
            prior_dec = str(prior.get("decision", ""))[:200]
            prior_date = str(prior.get("occurred_at", ""))
            facts.append(
                f"The PRIOR (now-corrected) understanding from {prior_date}: \"{prior_dec}\""
            )
            facts.append(f"BOTH dates referenced: {prior_date} (prior) AND {occurred} (correction)")

    return facts


_FACT_LINE_RE = re.compile(
    r"^\s*FACT\s+(\d+)\s*:\s*(yes|partial|no)\b[^\w]*(.*)?$",
    re.IGNORECASE,
)


def _parse_fact_results(text: str, n_facts: int) -> list[dict]:
    """Parse the per-fact yes/no/partial output from the LLM."""
    text = strip_code_fences(text)
    results: list[dict] = [{"verdict": "no", "justification": "no response"} for _ in range(n_facts)]
    for line in text.splitlines():
        m = _FACT_LINE_RE.match(line.strip())
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if 0 <= idx < n_facts:
            verdict = m.group(2).strip().lower()
            justification = (m.group(3) or "").strip()
            results[idx] = {"verdict": verdict, "justification": justification[:200]}
    return results


async def _check_artefact_substrate(
    llm: HelixLLM,
    artefact_record: dict,
    artefact_text: str,
    facts: list[str],
) -> list[dict]:
    """One LLM call: yes/no/partial per canonical fact."""
    if not facts:
        return []

    fact_list = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts))
    prompt = _load_template("artefact_substrate_check.md").format(
        artefact_text=artefact_text[:5000],  # cap so long meeting-transcripts stay bounded
        fact_list=fact_list,
    )
    text = await llm.call_text(
        stage="F",
        user=prompt,
        reasoning_effort="low",  # mechanical text-presence check, not reasoning
        max_tokens=1500,
    )
    return _parse_fact_results(text, len(facts))


# ---------------------------------------------------------------------------
# Per-question memorisation check
# ---------------------------------------------------------------------------


async def _check_memorisation(llm: HelixLLM, question: dict) -> tuple[float, str]:
    """Ask gpt-oss to answer the question with NO corpus. If it scores
    high, the question is solvable from world knowledge alone.

    Scoring here is approximate: we ask gpt-oss to produce an answer
    without corpus, then we count how many key answer tokens (named
    entities, dates, specific numbers) appear in the produced answer.
    No judge LLM needed — pure code on the produced text.
    """
    prompt = _load_template("memorisation.md").format(question_text=question["text"])
    text = await llm.call_text(
        stage="F",
        user=prompt,
        reasoning_effort="low",
        max_tokens=800,
    )
    return _score_memorisation(text, question.get("ground_truth_answer", {})), text


_TOK_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]{3,}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{4}\b")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "they",
    "you", "what", "when", "who", "why", "how", "which", "was", "were",
    "did", "does", "into", "about", "system", "company", "team",
}


def _score_memorisation(candidate_text: str, ground_truth: dict) -> float:
    """Fraction of distinctive answer tokens that appear in candidate.

    Distinctive = capitalised words ≥4 chars, ISO dates, year numbers.
    Stopwords excluded.
    """
    candidate_text = candidate_text.lower()
    if "i do not know" in candidate_text or "the evidence does not" in candidate_text:
        return 0.0

    gt_text = " ".join(str(v) for v in ground_truth.values())
    gt_tokens = {
        t.lower()
        for t in _TOK_RE.findall(gt_text)
        if t.lower() not in _STOPWORDS
    }
    if not gt_tokens:
        return 0.0

    cand_lower = candidate_text
    hits = sum(1 for t in gt_tokens if t in cand_lower)
    return hits / len(gt_tokens)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Stage F: substrate validation + memorisation drop."""
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)

    artefact_report_path = data_root / "artefact_validation_report.jsonl"
    question_report_path = data_root / "question_validation_report.jsonl"
    final_path = data_root / "benchmark_v0.0.jsonl"

    cp_art = Checkpoint(data_root / ".checkpoints" / "stage_f_artefacts.jsonl")
    cp_q = Checkpoint(data_root / ".checkpoints" / "stage_f_questions.jsonl")

    llm = HelixLLM()

    try:
        # ----- Pass 1: per-artefact substrate check -----
        # Iterate the corpus_index records (one per artefact).
        artefact_reports: dict[str, dict] = {}
        if artefact_report_path.exists():
            for line in artefact_report_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                artefact_reports[r["slot_id"]] = r

        for art in inputs["corpus_index"]:
            slot_id = art["slot_id"]
            if cp_art.is_done(slot_id):
                continue
            event = inputs["events_by_id"].get(art["event_id"])
            if not event:
                logger.warning("Stage F: slot %s references missing event %s, skipping",
                               slot_id, art["event_id"])
                cp_art.mark_done(slot_id, status="missing-event")
                continue
            facts = _canonical_facts_for_artefact(
                art, event, inputs["events_by_id"], inputs.get("persona_by_id"),
            )
            if not facts:
                # Noise artefact: nothing to check.
                cp_art.mark_done(slot_id, status="noise-no-check")
                continue
            art_path = data_root / art["path"]
            if not art_path.exists():
                logger.warning("Stage F: missing artefact file %s", art_path)
                cp_art.mark_done(slot_id, status="missing-file")
                continue
            text = art_path.read_text(encoding="utf-8")
            results = await _check_artefact_substrate(llm, art, text, facts)
            verdict_counts = Counter(r["verdict"] for r in results)
            n_yes = verdict_counts.get("yes", 0)
            n_partial = verdict_counts.get("partial", 0)
            score = (n_yes + 0.5 * n_partial) / max(1, len(facts))
            record = {
                "slot_id": slot_id,
                "event_id": art["event_id"],
                "role": art.get("role"),
                "genre": art.get("genre"),
                "fact_count": len(facts),
                "yes": n_yes,
                "partial": n_partial,
                "no": verdict_counts.get("no", 0),
                "score": round(score, 3),
                "facts": [
                    {"fact": f, "verdict": r["verdict"], "justification": r["justification"]}
                    for f, r in zip(facts, results)
                ],
            }
            with artefact_report_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            artefact_reports[slot_id] = record
            cp_art.mark_done(slot_id, status="ok", score=score)
            logger.info(
                "Stage F artefact %s [%s/%s]: %d/%d facts present (yes=%d partial=%d no=%d) score=%.2f",
                slot_id, art.get("genre"), art.get("role"),
                n_yes + n_partial, len(facts), n_yes, n_partial, verdict_counts.get("no", 0), score,
            )

        # ----- Pass 2: per-question structural + roll-up + memorisation -----
        question_reports: list[dict] = []
        for q in inputs["questions"]:
            qid = q["id"]
            if cp_q.is_done(qid):
                continue

            # Structural sanity
            schema_ok = bool(q.get("text")) and bool(q.get("category")) and bool(q.get("ground_truth_answer"))

            # ---- EMERGENT (Tier-3) union-mode validation ----
            # The answer is a pattern of facets, each *exhibited* across
            # scattered evidence (event_id=None, so the per-artefact
            # substrate check doesn't apply). A facet is covered if ANY of
            # its evidence artefacts exhibits it; pass if enough facets are
            # covered. No memorisation check (the answer isn't leaked).
            if q.get("category") == "EMERGENT" or (q.get("metadata", {}) or {}).get("validation_mode") == "union":
                all_ev_ids = q.get("evidence_artefact_ids", []) or []
                present_ev_ids = [s for s in all_ev_ids if s in inputs["index_by_slot"]]
                facet_cov = await _check_emergent_facets(llm, q, inputs["index_by_slot"], data_root)
                n_facets = len(facet_cov)
                covered = sum(1 for c in facet_cov if c)
                facet_frac = covered / max(1, n_facets)
                fc_complete = n_facets > 0 and facet_frac >= EMERGENT_FACET_REQUIRED
                if not schema_ok:
                    disposition = "fail_schema"
                elif not present_ev_ids:
                    disposition = "fail_no_evidence_on_disk"
                elif not fc_complete:
                    disposition = "fail_substrate_incomplete"
                else:
                    disposition = "pass"
                record = {
                    "question_id": qid, "category": "EMERGENT", "schema_ok": schema_ok,
                    "evidence_total": len(all_ev_ids), "evidence_present": len(present_ev_ids),
                    "facets_total": n_facets, "facets_covered": covered,
                    "facet_fraction": round(facet_frac, 3),
                    "substrate_score": round(facet_frac, 3),
                    "substrate_complete": fc_complete,
                    "memorisable": False, "disposition": disposition,
                }
                question_reports.append(record)
                with question_report_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
                cp_q.mark_done(qid, disposition=disposition, facet_fraction=facet_frac)
                logger.info("Stage F EMERGENT %s: %d/%d facets covered (%.2f) → %s",
                            qid, covered, n_facets, facet_frac, disposition)
                continue

            # Filter evidence to slots that ACTUALLY exist on disk.
            # Stage C occasionally fails to write a slot (empty content,
            # HTTP retry that didn't recover). Stage E doesn't know; it
            # pulls slot_ids from the event's evidence_in_corpus list.
            # Be lenient: skip missing IDs, roll up substrate on what
            # remains. Only fail the question if NO evidence remains.
            all_ev_ids = q.get("evidence_artefact_ids", []) or []
            present_ev_ids = [sid for sid in all_ev_ids if sid in inputs["index_by_slot"]]
            missing_evidence_ids = [sid for sid in all_ev_ids if sid not in inputs["index_by_slot"]]
            evidence_was_filtered = bool(missing_evidence_ids) and bool(present_ev_ids)

            # Roll-up: average artefact substrate score across this Q's
            # PRESENT evidence.
            ev_scores = [
                artefact_reports.get(sid, {}).get("score", 0.0)
                for sid in present_ev_ids
                if sid in artefact_reports
            ]
            avg_substrate_score = sum(ev_scores) / max(1, len(ev_scores)) if ev_scores else 0.0
            substrate_complete = avg_substrate_score >= SUBSTRATE_COMPLETE_REQUIRED

            # Memorisation check
            mem_score, mem_candidate = await _check_memorisation(llm, q)
            memorisable = mem_score > MEMORISATION_THRESHOLD

            # Disposition
            if not schema_ok:
                disposition = "fail_schema"
            elif not present_ev_ids:
                # ALL evidence missing — genuinely broken question
                disposition = "fail_no_evidence_on_disk"
            elif not substrate_complete:
                disposition = "fail_substrate_incomplete"
            elif memorisable:
                disposition = "fail_memorisation"
            else:
                disposition = "pass"

            record = {
                "question_id": qid,
                "category": q["category"],
                "schema_ok": schema_ok,
                "evidence_total": len(all_ev_ids),
                "evidence_present": len(present_ev_ids),
                "missing_evidence_ids": missing_evidence_ids,
                "evidence_was_filtered": evidence_was_filtered,
                "substrate_score": round(avg_substrate_score, 3),
                "substrate_complete": substrate_complete,
                "memorisation_score": round(mem_score, 3),
                "memorisable": memorisable,
                "memorisation_candidate": mem_candidate[:400],
                "disposition": disposition,
            }
            question_reports.append(record)
            with question_report_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp_q.mark_done(qid, disposition=disposition, substrate=avg_substrate_score, mem=mem_score)
            logger.info(
                "Stage F Q %s [%s]: substrate=%.2f mem=%.2f → %s",
                qid, q["category"], avg_substrate_score, mem_score, disposition,
            )

        # ----- Final benchmark JSONL -----
        passing_ids = {r["question_id"] for r in question_reports if r["disposition"] == "pass"}
        with final_path.open("w", encoding="utf-8") as f:
            for q in inputs["questions"]:
                if q["id"] in passing_ids:
                    f.write(json.dumps(q, default=str) + "\n")

        disp_dist = Counter(r["disposition"] for r in question_reports)
        per_cat_pass: dict[str, int] = defaultdict(int)
        per_cat_total: dict[str, int] = defaultdict(int)
        for r in question_reports:
            per_cat_total[r["category"]] += 1
            if r["disposition"] == "pass":
                per_cat_pass[r["category"]] += 1
        logger.info("Stage F complete.")
        logger.info("  Artefacts checked: %d", len(artefact_reports))
        logger.info("  Questions: %d / %d pass. Disposition: %s",
                    len(passing_ids), len(question_reports), dict(disp_dist))
        for cat in sorted(per_cat_total):
            logger.info("    %s: %d / %d pass", cat, per_cat_pass[cat], per_cat_total[cat])
    finally:
        await llm.aclose()
