"""Load the validated question + ground-truth set for a company tier."""

from __future__ import annotations

import json
from pathlib import Path

from .corpus import tier_dir
from .schemas import Question, required_capabilities


def load_questions(tier: str, company: str = "helix") -> list[Question]:
    """Read ``benchmark_v0.0.jsonl`` (the validated Q + ground-truth set)."""
    path = tier_dir(tier, company) / "benchmark_v0.0.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No benchmark file at {path}")
    out: list[Question] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cat = r.get("category", "")
        out.append(
            Question(
                id=r["id"],
                company=company,
                tier=tier,
                category=cat,
                difficulty=r.get("difficulty"),
                text=r["text"],
                paraphrases=r.get("paraphrases", []) or [],
                ground_truth_answer=r.get("ground_truth_answer", {}) or {},
                rubric_subpoints=r.get("rubric_subpoints", []) or [],
                evidence_artifact_ids=r.get("evidence_artefact_ids", r.get("evidence_artifact_ids", [])) or [],
                capabilities_required=list(required_capabilities(cat)),
                metadata=r.get("metadata", {}) or {},
            )
        )
    return out


def questions_stats(tier: str, company: str = "helix") -> dict:
    from collections import Counter
    qs = load_questions(tier, company)
    return {
        "company": company,
        "tier": tier,
        "n_questions": len(qs),
        "by_category": dict(Counter(q.category for q in qs)),
        "by_public_category": dict(Counter(q.public_category for q in qs)),
        "by_difficulty": dict(Counter(q.difficulty for q in qs)),
        "n_emergent": sum(1 for q in qs if q.is_emergent),
        "n_temporal_required": sum(1 for q in qs if any(c.value == "temporal" for c in q.capabilities_required)),
    }
