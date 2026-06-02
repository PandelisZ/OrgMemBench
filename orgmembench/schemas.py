"""Core data models for OrgMemBench.

Three families:
- **Corpus**: :class:`Artifact` — one normalized document/thread from one channel.
- **Questions**: :class:`Question` — a question + its ground-truth answer + rubric.
- **Run**: :class:`IngestStats`, :class:`QueryResult`, :class:`JudgeResult`,
  :class:`RunResult` — what a system produced and how it scored.

The question taxonomy uses the internal category codes the dataset ships with
(C1..C6, HARD, EMERGENT); :data:`CATEGORY_INFO` maps each to a public-facing
name and the *capabilities* a system must have to answer it. Capability flags
drive **capability-aware scoring**: a system that doesn't declare a required
capability is reported N/A for that category rather than silently scored zero.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Capability(str, Enum):
    RECALL = "recall"            # everyone; baseline retrieval
    TEMPORAL = "temporal"        # answer "as of <date>" / bi-temporal queries
    PROVENANCE = "provenance"    # cite the source(s) behind an answer
    SCOPE = "scope"              # role-relative knowledge (what X would know)
    NEGATIVE = "negative"        # calibrated "no evidence" / abstention


class FailureMode(str, Enum):
    NONE = "none"
    RETRIEVAL_MISS = "retrieval_miss"            # never surfaced the evidence
    WRONG_CONTEXT_SYNTHESIS = "wrong_synthesis"  # had context, synthesized wrong
    CONFIDENT_HALLUCINATION = "hallucination"    # confident + unsupported
    ABSTAIN_WHEN_ANSWERABLE = "wrong_abstain"
    DRY_RUN = "dry_run"                           # produced under dry-run (not real)


# Internal category code -> (public name, required capabilities).
# Required capabilities are conservative: only listed when a question genuinely
# cannot be answered without them (used to mark systems N/A, not to penalize).
CATEGORY_INFO: dict[str, tuple[str, tuple[Capability, ...]]] = {
    "C1":       ("supersession",           ()),
    "C2":       ("decision_provenance",    (Capability.PROVENANCE,)),
    "C3":       ("bitemporal",             (Capability.TEMPORAL,)),
    "C4":       ("audit_replay",           (Capability.TEMPORAL,)),
    "C5":       ("justification_chain",    (Capability.PROVENANCE,)),
    "C6":       ("contradiction",          ()),
    "HARD":     ("multi_hop_lineage",      ()),
    "EMERGENT": ("emergent_pattern",       ()),
}


def public_category(code: str) -> str:
    return CATEGORY_INFO.get(code, (code.lower(), ()))[0]


def required_capabilities(code: str) -> tuple[Capability, ...]:
    return CATEGORY_INFO.get(code, ("", ()))[1]


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
class Artifact(BaseModel):
    """One normalized corpus item. The *single fair shape* every adapter maps
    into its system's native ingest format (messages / episodes / chunks)."""

    slot_id: str
    company: str
    source_type: str                  # genre: slack_thread, email_thread, ...
    text: str                         # body with the metadata header stripped
    timestamp: str | None = None      # ISO date (YYYY-MM-DD) where known
    author: str | None = None         # human display name where known
    thread_id: str | None = None      # grouping key (event/pattern/customer)
    role: str | None = None           # primary | secondary | noise | emergent_evidence
    raw: dict[str, Any] = Field(default_factory=dict)  # original index row


# --------------------------------------------------------------------------- #
# Questions
# --------------------------------------------------------------------------- #
class Question(BaseModel):
    id: str
    company: str
    tier: str
    category: str                     # internal code (C1..EMERGENT)
    difficulty: str | None = None
    text: str
    paraphrases: list[str] = Field(default_factory=list)
    ground_truth_answer: dict[str, Any] = Field(default_factory=dict)
    rubric_subpoints: list[dict[str, Any]] = Field(default_factory=list)
    evidence_artifact_ids: list[str] = Field(default_factory=list)
    capabilities_required: list[Capability] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def public_category(self) -> str:
        return public_category(self.category)

    @property
    def is_emergent(self) -> bool:
        return self.category == "EMERGENT" or self.metadata.get("validation_mode") == "union"


# --------------------------------------------------------------------------- #
# Run records
# --------------------------------------------------------------------------- #
class IngestStats(BaseModel):
    n_artifacts: int = 0
    tokens_stored: int = 0            # system-reported tokens/units stored (0 if N/A)
    index_bytes: int = 0             # on-disk/in-memory index size (0 if N/A)
    ingest_seconds: float = 0.0
    # LLM tokens spent during ingest, WHERE the system reports them. 0 means
    # "not exposed by this system" (mem0/graphiti run their extractor inside the
    # SDK and don't surface usage).
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


class QueryResult(BaseModel):
    question_id: str
    system: str
    # The final, judged prose answer. Either the system's own (e.g. gbrain
    # `think`) or produced by the basic answerer over `retrieved_context`
    # (see runner). Empty until an answerer fills it.
    answer_text: str = ""
    # What the system actually RETRIEVED (memories/facts), as readable text.
    # This is the answerer's input for systems that don't self-answer.
    retrieved_context: str = ""
    # Provenance of answer_text: "native:<system>" | "basic-answerer" |
    # "dry-run".
    answer_source: str = ""
    cited_artifact_ids: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    # Measured answerer LLM usage (the prose-answer call we make for this query).
    # 0 for gbrain (its `think` runs in a subprocess and doesn't surface usage).
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    dry_run: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class JudgeResult(BaseModel):
    question_id: str
    system: str
    score: float = 0.0               # 0..1 overall (rubric-weighted)
    exact_match: bool = False
    semantic_score: float = 0.0      # 0..1
    faithful: bool = True            # False => hallucinated / unsupported
    subpoint_scores: dict[str, float] = Field(default_factory=dict)
    failure_mode: FailureMode = FailureMode.NONE
    rationale: str = ""
    # Measured judge LLM usage (Sonnet 4.6 + thinking, one call per question).
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    judged_dry_run: bool = False


class RunResult(BaseModel):
    """Everything from running one system on one tier."""

    system: str
    system_version: str = "unknown"   # resolved at run time (pkg/CLI/commit); pinned in config
    company: str
    tier: str
    capabilities: list[Capability] = Field(default_factory=list)
    ingest: IngestStats = Field(default_factory=IngestStats)
    queries: list[QueryResult] = Field(default_factory=list)
    judgements: list[JudgeResult] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
