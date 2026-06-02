"""Reference adapter — a dev/test fixture and the template for real adapters.

It is **not a contestant** and never appears on the public leaderboard. It uses
no LLM and no external service (naive keyword overlap), so the full pipeline can
be exercised end-to-end for free even with ORGMEMBENCH_DRY_RUN=0. Real adapters
(mem0/zep/gbrain/graphify-oss) follow this same shape but talk to their system.
"""

from __future__ import annotations

import re
import time

from .. import __version__
from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


class ReferenceAdapter(MemoryAdapter):
    name = "reference"
    capabilities = {Capability.RECALL}
    # Produces its own answer (naive keyword overlap, no LLM) so the pipeline
    # runs free even with dry-run off — the runner must not wrap it.
    self_answers = True

    def _resolve_version(self) -> str:
        return f"orgmembench-{__version__}"

    def scope_count(self) -> int:
        # In-memory, fresh per adapter instance: nothing stored until _ingest.
        return len(getattr(self, "_store", []))

    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        t0 = time.time()
        self._store = artifacts
        self._tok = [(_tokens(a.text), a) for a in artifacts]
        total_chars = sum(len(a.text) for a in artifacts)
        return IngestStats(
            n_artifacts=len(artifacts),
            tokens_stored=total_chars // 4,
            ingest_seconds=time.time() - t0,
        )

    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        q = _tokens(question.text)
        best, best_score = None, 0
        for toks, art in getattr(self, "_tok", []):
            score = len(q & toks)
            if score > best_score:
                best, best_score = art, score
        if best is None:
            return QueryResult(question_id=question.id, system=self.name,
                               answer_text="No relevant evidence found.",
                               retrieved_context="No relevant evidence found.",
                               answer_source="native:reference")
        return QueryResult(
            question_id=question.id, system=self.name,
            answer_text=best.text[:600],
            retrieved_context=best.text[:600],
            answer_source="native:reference",
            cited_artifact_ids=[best.slot_id],
        )
