"""Run one system on one tier: ingest → query → judge → metrics.

Checkpointed: per-question (query, judgement) pairs are appended to a partial
file as they complete, so a long real run resumes instead of restarting.
Dry-run by default — the whole loop runs for free and produces a structurally
valid (but meaningless) result set, which is exactly what the smoke tests check.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import yaml

from .config import CONFIG_ROOT, RESULTS_ROOT, dry_run
from .corpus import load_corpus
from .judge import judge_one
from .llm import AnthropicLLM
from .metrics import compute_metrics
from .questions import load_questions
from .adapters.registry import get_adapter
from .schemas import IngestStats, JudgeResult, QueryResult, RunResult

logger = logging.getLogger("orgmembench.runner")


def load_system_config(system: str) -> dict:
    """Load config/<system>.yaml (vendor-recommended settings + version pin)."""
    f = CONFIG_ROOT / f"{system}.yaml"
    if not f.exists():
        return {}
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _result_paths(system: str, tier: str, company: str) -> tuple[Path, Path]:
    d = RESULTS_ROOT / system
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{company}-{tier}.partial.jsonl", d / f"{company}-{tier}.json"


def _derive_as_of(question) -> str | None:
    """Pass an explicit as-of date only when the question carries one."""
    md = question.metadata or {}
    for k in ("as_of", "as_of_date"):
        if md.get(k):
            return str(md[k])
    gt = question.ground_truth_answer or {}
    for k in ("as_of_date", "as_of"):
        if gt.get(k):
            return str(gt[k])
    return None


def _load_checkpoint(partial: Path) -> tuple[dict[str, QueryResult], dict[str, JudgeResult]]:
    qrs: dict[str, QueryResult] = {}
    jrs: dict[str, JudgeResult] = {}
    if not partial.exists():
        return qrs, jrs
    for line in partial.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        qid = rec["query"]["question_id"]
        qrs[qid] = QueryResult(**rec["query"])
        jrs[qid] = JudgeResult(**rec["judge"])
    return qrs, jrs


def run_system(
    system: str,
    tier: str,
    company: str = "helix",
    config: dict | None = None,
    limit: int | None = None,
    resume: bool = True,
) -> RunResult:
    dry = dry_run()
    partial, final = _result_paths(system, tier, company)

    corpus = load_corpus(tier, company)
    questions = load_questions(tier, company)
    if limit:
        questions = questions[:limit]

    merged_cfg = load_system_config(system)
    if config:
        merged_cfg.update(config)
    # Per-tier isolation: every adapter scopes its store/namespace/user to this
    # so small/medium/large never cross-contaminate. Explicit config wins.
    merged_cfg.setdefault("scope", f"{company}-{tier}")
    adapter = get_adapter(system, config=merged_cfg, dry_run=dry)
    adapter.check_version()
    logger.info("Run %s v=%s on %s/%s (%d artifacts, %d questions, dry_run=%s)",
                system, adapter.version(), company, tier, len(corpus), len(questions), dry)

    # Refuse to ingest on top of stale data: wipe (OSS/local) or verify-empty
    # (hosted) the per-tier scope first. No-op in dry-run.
    #
    # ``ORGMEMBENCH_REUSE_INGEST=1`` opts out of the wipe-and-reingest cycle and
    # reuses whatever's already in the adapter's scope. Use when you want to
    # iterate on the *query* phase (e.g. raised timeout, swapped answerer) on
    # an expensive ingest you don't want to repeat. Skips ensure_clean_scope()
    # AND adapter.ingest(); synthesises an empty IngestResult so the rest of
    # the runner sees a coherent ``run.ingest`` object.
    reuse_ingest = os.environ.get("ORGMEMBENCH_REUSE_INGEST", "").strip().lower() in ("1", "true", "yes")
    if reuse_ingest and not dry:
        logger.warning(
            "Run %s/%s: ORGMEMBENCH_REUSE_INGEST=1 — skipping ensure_clean_scope() + ingest(). "
            "Querying against pre-existing data in the adapter's scope.",
            system, tier,
        )
        ingest = IngestStats(n_artifacts=len(corpus), tokens_stored=0, ingest_seconds=0.0)
    else:
        adapter.ensure_clean_scope()
        t0 = time.time()
        ingest = adapter.ingest(corpus)
        ingest.ingest_seconds = ingest.ingest_seconds or (time.time() - t0)

    run = RunResult(
        system=system, system_version=adapter.version(), company=company, tier=tier,
        capabilities=sorted(adapter.capabilities, key=lambda c: c.value),
        ingest=ingest, dry_run=dry,
    )

    done_q, done_j = _load_checkpoint(partial) if (resume and not dry) else ({}, {})
    llm = None if dry else AnthropicLLM()

    # Only touch the checkpoint file for real runs (dry-run leaves no scratch).
    cp = partial.open("a", encoding="utf-8") if not dry else None
    try:
        for q in questions:
            if q.id in done_q and q.id in done_j:
                run.queries.append(done_q[q.id]); run.judgements.append(done_j[q.id])
                continue
            qr = adapter.query(q, as_of=_derive_as_of(q))
            # Answerer stage. Systems that ship their own prose answer
            # (e.g. gbrain `think`) set self_answers and already filled
            # answer_text. Everyone else (retrieval-only) gets the neutral
            # basic answerer over what they retrieved.
            if not dry and not adapter.self_answers:
                from .answerer import basic_answer
                resp = basic_answer(q.text, qr.retrieved_context, llm)
                qr.answer_text = resp.text.strip() or "No answer produced."
                qr.answer_source = "basic-answerer"
                qr.input_tokens = resp.input_tokens
                qr.output_tokens = resp.output_tokens
                qr.cost_usd += resp.cost_usd
            jr = judge_one(q, qr, llm)
            run.queries.append(qr); run.judgements.append(jr)
            if cp is not None:  # checkpoint real work only
                cp.write(json.dumps({"query": qr.model_dump(), "judge": jr.model_dump()},
                                    default=str) + "\n")
                cp.flush()
    finally:
        if cp is not None:
            cp.close()

    run.metrics = compute_metrics(run, questions)
    # Actuals metering (tokens / native units / vs-estimate), for post-run review.
    from .usage import build_usage
    run.metrics["usage"] = build_usage(run)
    if not dry:
        u = run.metrics["usage"]
        m, e = u["measured"], u["estimate"]
        logger.info(
            "USAGE %s/%s: measured Anthropic $%.2f (answerer %d tok-out, judge %d tok-out) "
            "vs estimate all-in $%s | native=%s",
            system, tier, m["measured_anthropic_cost_usd"],
            m["answerer"]["output_tokens"], m["judge"]["output_tokens"],
            e.get("all_in_usd"), u["native_units"],
        )
    adapter.teardown()

    if not dry:
        final.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Wrote %s", final)
    return run
