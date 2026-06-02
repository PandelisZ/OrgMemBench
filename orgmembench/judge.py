"""Rubric-driven LLM judge (Claude Sonnet 4.6, extended thinking ON).

One uniform, rubric-driven mechanism scores both recorded questions (C1..C6,
HARD — structured ground truth + rubric subpoints) and emergent questions
(facet subpoints + a formal-vs-de-facto distractor subpoint). The judge returns
a per-subpoint fraction (0..1); we compute the weighted overall in code (more
reliable than trusting LLM arithmetic), plus a holistic semantic score, a
faithfulness verdict, and a failure-mode label.

Dry-run safe: :func:`judge_one` returns a stub (no LLM call) unless
ORGMEMBENCH_DRY_RUN=0.
"""

from __future__ import annotations

import json

from .config import dry_run
from .llm import AnthropicLLM
from .schemas import FailureMode, JudgeResult, Question, QueryResult, RunResult

_JUDGE_SYSTEM = (
    "You are a rigorous, impartial benchmark judge for an organizational-memory "
    "QA task. You score a candidate answer against a known ground truth and a "
    "rubric. Be strict: award a subpoint only to the extent its criterion is "
    "genuinely satisfied. Reward correct, supported answers; penalize confident "
    "claims that are unsupported or contradict the ground truth. Output STRICT "
    "JSON only."
)


def _weight(sp: dict) -> float:
    w = sp.get("max_score", sp.get("weight"))
    try:
        return float(w)
    except (TypeError, ValueError):
        return 0.0


def build_judge_prompt(question: Question, answer_text: str) -> str:
    gt = json.dumps(question.ground_truth_answer, ensure_ascii=False, indent=2)
    subpoints = [
        {
            "id": sp.get("id", f"sub{i+1}"),
            "criterion": sp.get("criterion", ""),
            "fail_criterion": sp.get("fail_criterion") or sp.get("fail_if", ""),
        }
        for i, sp in enumerate(question.rubric_subpoints)
    ]
    extra = ""
    if question.is_emergent:
        extra = (
            "\nThis is an EMERGENT question: the true answer is a de-facto pattern "
            "that was never written down, reconstructed from scattered behavior. "
            "Credit the candidate for capturing each facet of the pattern. If the "
            "candidate instead answers with a later FORMAL version (see the "
            "ground-truth 'formalization' field), that subpoint must fail.\n"
        )
    return f"""Question ({question.public_category}):
{question.text}
{extra}
GROUND TRUTH (authoritative):
{gt}

RUBRIC SUBPOINTS (score each from 0.0 to 1.0 = fraction of the criterion met):
{json.dumps(subpoints, ensure_ascii=False, indent=2)}

CANDIDATE ANSWER (from the system under test):
\"\"\"
{answer_text[:6000]}
\"\"\"

Return STRICT JSON with exactly these keys:
{{
  "subpoint_scores": {{"<subpoint id>": <0.0-1.0>, ...}},
  "exact_match": <true|false>,        // are the key ground-truth facts explicitly present?
  "semantic_score": <0.0-1.0>,        // holistic correctness vs ground truth
  "faithful": <true|false>,           // false if it confidently asserts unsupported/contradictory claims
  "failure_mode": "none|retrieval_miss|wrong_synthesis|hallucination|wrong_abstain",
  "rationale": "<one or two sentences>"
}}"""


def _to_failure_mode(s: str) -> FailureMode:
    try:
        return FailureMode(s)
    except ValueError:
        return FailureMode.NONE


def judge_one(question: Question, query: QueryResult, llm: AnthropicLLM | None = None) -> JudgeResult:
    if dry_run():
        return JudgeResult(
            question_id=question.id, system=query.system,
            score=0.0, failure_mode=FailureMode.DRY_RUN, judged_dry_run=True,
            rationale="dry-run: not judged",
        )
    llm = llm or AnthropicLLM()
    data, resp = llm.complete_json(build_judge_prompt(question, query.answer_text), system=_JUDGE_SYSTEM)

    # Weighted overall from per-subpoint fractions × rubric weights.
    sp_scores = data.get("subpoint_scores", {}) or {}
    total_w, got = 0.0, 0.0
    norm_scores: dict[str, float] = {}
    for sp in question.rubric_subpoints:
        sid = sp.get("id", "")
        w = _weight(sp) or 1.0
        frac = float(sp_scores.get(sid, 0.0) or 0.0)
        frac = min(1.0, max(0.0, frac))
        norm_scores[sid] = frac
        total_w += w
        got += w * frac
    overall = (got / total_w) if total_w else float(data.get("semantic_score", 0.0) or 0.0)

    return JudgeResult(
        question_id=question.id, system=query.system,
        score=round(overall, 4),
        exact_match=bool(data.get("exact_match", False)),
        semantic_score=min(1.0, max(0.0, float(data.get("semantic_score", overall) or 0.0))),
        faithful=bool(data.get("faithful", True)),
        subpoint_scores=norm_scores,
        failure_mode=_to_failure_mode(str(data.get("failure_mode", "none"))),
        rationale=str(data.get("rationale", ""))[:500],
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cost_usd=resp.cost_usd,
    )


def judge_run(run: RunResult, questions: list[Question], llm: AnthropicLLM | None = None) -> RunResult:
    qby = {q.id: q for q in questions}
    llm = llm or (None if dry_run() else AnthropicLLM())
    run.judgements = [
        judge_one(qby[qr.question_id], qr, llm)
        for qr in run.queries if qr.question_id in qby
    ]
    return run
