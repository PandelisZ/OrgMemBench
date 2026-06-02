"""External submission format + judging.

Anyone can run their own system, dump predictions in this schema, and have them
judged on the same rubric as the built-in adapters (so the leaderboard accepts
external entries — the move that turns "we benchmarked them" into "they ran on
our benchmark").

Submission file: JSONL, one object per question:
    {"question_id": "Q-0001", "answer_text": "...", "cited_artifact_ids": ["ART-..."]}
"""

from __future__ import annotations

import json
from pathlib import Path

from .judge import judge_one
from .llm import AnthropicLLM
from .metrics import compute_metrics
from .questions import load_questions
from .config import dry_run
from .schemas import JudgeResult, QueryResult, RunResult


def load_submission(path: str | Path) -> dict[str, dict]:
    preds: dict[str, dict] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if "question_id" not in rec or "answer_text" not in rec:
            raise ValueError(f"submission record missing required keys: {rec}")
        preds[rec["question_id"]] = rec
    return preds


def validate_submission(preds: dict[str, dict], tier: str, company: str = "helix") -> dict:
    qs = load_questions(tier, company)
    ids = {q.id for q in qs}
    sub_ids = set(preds)
    return {
        "n_questions": len(ids),
        "n_predictions": len(sub_ids),
        "missing": sorted(ids - sub_ids),
        "unknown": sorted(sub_ids - ids),
        "complete": ids.issubset(sub_ids),
    }


def judge_submission(path: str | Path, system: str, tier: str, company: str = "helix") -> RunResult:
    preds = load_submission(path)
    qs = load_questions(tier, company)
    run = RunResult(system=system, company=company, tier=tier, dry_run=dry_run())
    llm = None if dry_run() else AnthropicLLM()
    for q in qs:
        p = preds.get(q.id, {})
        qr = QueryResult(
            question_id=q.id, system=system,
            answer_text=p.get("answer_text", ""),
            cited_artifact_ids=p.get("cited_artifact_ids", []) or [],
        )
        run.queries.append(qr)
        run.judgements.append(judge_one(q, qr, llm))
    run.metrics = compute_metrics(run, qs)
    return run
