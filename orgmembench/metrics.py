"""The 5D metrics matrix + failure-mode breakdown + capability-aware rollup.

5D (community-standard for memory systems): accuracy, faithfulness, latency,
cost, footprint (tokens stored / index size), ingest time. Plus a failure-mode
decomposition and a per-category breakdown that marks a category **N/A** when
the system lacks a capability that category requires (rather than scoring zero).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from .schemas import Capability, FailureMode, JudgeResult, Question, QueryResult, RunResult


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def compute_metrics(run: RunResult, questions: list[Question]) -> dict:
    qby = {q.id: q for q in questions}
    judged = run.judgements
    queries = {qr.question_id: qr for qr in run.queries}
    sys_caps = set(run.capabilities)

    scores = [j.score for j in judged]
    sem = [j.semantic_score for j in judged]
    em = [1.0 if j.exact_match else 0.0 for j in judged]
    faithful = [1.0 if j.faithful else 0.0 for j in judged]
    latencies = [qr.latency_ms for qr in run.queries if qr.latency_ms]
    costs = [qr.cost_usd for qr in run.queries]

    # --- per-category ---
    # Per user request 2026-05-26: ALL systems are scored on ALL categories,
    # even ones they don't claim capability for. Rationale: capability-aware
    # N/A let systems opt out of hard questions, which inflated their headline
    # means relative to systems that DID attempt them (e.g. a system skipping
    # C3 and C4 while another attempted them). For a fair head-to-head every
    # system gets scored on every question; non-capable systems will score near
    # zero on those questions, which is the truth.
    #
    # The per-category required-caps mapping is still computed below into
    # ``cat_caps`` (used by the diagnostic ``cat_caps_required`` field) so
    # consumers can still see which categories DEMAND temporal/etc support —
    # they just don't gate scoring anymore.
    by_cat: dict[str, list[float]] = defaultdict(list)
    for j in judged:
        q = qby.get(j.question_id)
        if q:
            by_cat[q.public_category].append(j.score)
    cat_caps: dict[str, set[Capability]] = defaultdict(set)
    for q in questions:
        cat_caps[q.public_category].update(q.capabilities_required)
    category_scores: dict[str, object] = {
        cat: round(mean(sc), 4) if sc else 0.0
        for cat, sc in by_cat.items()
    }

    # --- by difficulty ---
    by_diff: dict[str, list[float]] = defaultdict(list)
    for j in judged:
        q = qby.get(j.question_id)
        by_diff[(q.difficulty if q and q.difficulty else "unspecified")].append(j.score)
    difficulty_scores = {d: round(mean(sc), 4) for d, sc in by_diff.items() if sc}

    return {
        "system": run.system,
        "system_version": run.system_version,
        "company": run.company,
        "tier": run.tier,
        "dry_run": run.dry_run,
        "n_questions": len(judged),
        # accuracy
        "accuracy_mean": round(mean(scores), 4) if scores else 0.0,
        "exact_match_rate": round(mean(em), 4) if em else 0.0,
        "semantic_mean": round(mean(sem), 4) if sem else 0.0,
        # faithfulness
        "faithfulness_rate": round(mean(faithful), 4) if faithful else 0.0,
        "hallucination_rate": round(1 - mean(faithful), 4) if faithful else 0.0,
        # latency / cost / footprint / ingest
        "latency_ms_p50": round(_pct(latencies, 0.50), 2),
        "latency_ms_p95": round(_pct(latencies, 0.95), 2),
        "cost_per_query_usd": round(mean(costs), 6) if costs else 0.0,
        "tokens_stored": run.ingest.tokens_stored,
        "index_bytes": run.ingest.index_bytes,
        "ingest_seconds": round(run.ingest.ingest_seconds, 2),
        # breakdowns
        "by_category": category_scores,
        "by_difficulty": difficulty_scores,
        "failure_modes": dict(Counter(j.failure_mode.value for j in judged)),
    }
