"""Pydantic record schemas for the helix-corpus pipeline.

These are the *parsed-and-validated* representations of gpt-oss output.
The wire format gpt-oss emits is structured text (Markdown/YAML); the
parsers in :mod:`helix_corpus.parsers` extract dicts; these schemas turn
the dicts into typed records that downstream stages consume.

Schemas trace the benchmark design described in the paper, lightly simplified
for v0.x.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Stage A — Canon
# ---------------------------------------------------------------------------


class RoleInterval(BaseModel):
    """A persona's role during a date interval."""

    from_date: date = Field(..., alias="from")
    to_date: date | None = Field(default=None, alias="to")
    role: str
    manager: str | None = None

    model_config = {"populate_by_name": True}


VoiceMarker = dict  # Open-ended; gpt-oss decides voice fields per persona.


class Persona(BaseModel):
    """A named character in the Helix canon.

    Fields match v2 design §4.3 schema, lightly simplified. The
    ``voice_markers`` field is left as a free dict because gpt-oss will
    invent its own keys (hedging_frequency, emoji_use, etc.) per persona.
    """

    persona_id: str = Field(..., pattern=r"^P-\d{4}$")
    display_name: str
    pronouns: str | None = None
    joined_year: int
    left_year: int | None = None
    role_history: list[RoleInterval] = Field(default_factory=list)
    voice_markers: VoiceMarker = Field(default_factory=dict)
    signature_phrases: list[str] = Field(default_factory=list)
    doc_discipline_trait: Literal["low", "medium", "high", "very_high"] = "medium"
    communication_channel_mix: dict = Field(default_factory=dict)
    domain_expertise: list[str] = Field(default_factory=list)
    is_long_tail: bool = False

    @field_validator("signature_phrases")
    @classmethod
    def _phrases_count(cls, v: list[str]) -> list[str]:
        if len(v) < 3 or len(v) > 5:
            raise ValueError(
                f"signature_phrases must have 3-5 entries, got {len(v)}"
            )
        return v


class CustomerArc(BaseModel):
    """A named customer organisation with a multi-year arc."""

    customer_id: str = Field(..., pattern=r"^C-\d{4}$")
    name: str
    first_year: int
    last_year: int | None = None  # None if still active
    arc_summary: str
    narrative_roles: list[str] = Field(default_factory=list)
    renewal_timeline: list[dict] = Field(default_factory=list)


class DocDisciplineEra(BaseModel):
    """A documentation-discipline era spanning some year range.

    gpt-oss names + characterises these; helix_corpus enforces exactly 5
    eras + the low/medium/high mix.
    """

    era_id: str = Field(..., pattern=r"^E-\d{1,2}$")
    name: str
    start_year: int
    end_year: int
    discipline_level: Literal["low", "medium", "high"]
    characterisation: str


class ToolingChange(BaseModel):
    """A change in the company's tooling stack at a point in time."""

    tool_name: str
    category: str  # crm, eng_tickets, transcripts, etc.
    adopted_year: int
    adopted_quarter: int | None = None  # 1-4
    superseded_year: int | None = None
    superseded_by: str | None = None


class CanonSkeleton(BaseModel):
    """The Stage A1 skeleton output — the dimensional grid."""

    founding_date: date
    founder_count: int = Field(..., ge=1, le=5)
    year_arc_themes: dict[int, str]  # year -> 1-sentence theme
    product_line_count: int = Field(..., ge=1)
    customer_arc_count: int = Field(..., ge=8, le=10)
    era_count: int = Field(..., ge=5, le=5)


# ---------------------------------------------------------------------------
# Stage B — Source-of-truth graph
# ---------------------------------------------------------------------------


EventType = Literal[
    "strategic_decision",
    "hire",
    "departure",
    "launch",
    "incident",
    "customer_event",
    "supersession",
    "contradiction_episode",
    "policy_change",
]


CategoryTarget = Literal["C1", "C2", "C3", "C4", "C5", "C6"]


class Event(BaseModel):
    """One node in the source-of-truth graph.

    The bi-temporal pair (occurred_at vs recorded_at) lets us model
    retroactive corrections — see v2 design §4.6. ``evidence_in_corpus``
    is populated as placeholder slots by Stage B and filled with
    real artefact IDs by Stage C.
    """

    id: str = Field(..., pattern=r"^EV-\d{4}-\d{3}$")
    type: EventType
    occurred_at: date
    recorded_at: date | None = None  # defaults to occurred_at when null
    participants: list[str] = Field(default_factory=list)
    decision: str
    reason_canonical: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    category_target: CategoryTarget | None = None  # may be None for atmosphere events
    summary: str = ""
    evidence_in_corpus: list[dict] = Field(default_factory=list)
    doc_dispersal_pattern: Literal["informal_primary", "authoritative_primary", "mixed"] = "informal_primary"


class RelationType:
    """Closed enum for graph relationship types."""

    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    CAUSED_BY = "caused_by"
    RETROACTIVELY_CORRECTED_BY = "retroactively_corrected_by"
    REVERSES = "reverses"
    RE_ATTEMPTS = "re_attempts"
    RESOLVED_BY = "resolved_by"

    @classmethod
    def all(cls) -> set[str]:
        return {
            cls.SUPERSEDES, cls.CONTRADICTS, cls.CAUSED_BY,
            cls.RETROACTIVELY_CORRECTED_BY, cls.REVERSES, cls.RE_ATTEMPTS,
            cls.RESOLVED_BY,
        }


class Relation(BaseModel):
    """An edge between two events in the source-of-truth graph."""

    source: str = Field(..., pattern=r"^EV-\d{4}-\d{3}$")
    relation: str
    target: str = Field(..., pattern=r"^EV-\d{4}-\d{3}$")

    @field_validator("relation")
    @classmethod
    def _rel_in_enum(cls, v: str) -> str:
        if v not in RelationType.all():
            raise ValueError(f"unknown relation {v!r}; must be one of {sorted(RelationType.all())}")
        return v


# ---------------------------------------------------------------------------
# Stage E — Questions
# ---------------------------------------------------------------------------


class RubricSubpoint(BaseModel):
    """One sub-point of a question's scoring rubric."""

    id: str  # e.g. "C1.current_value"
    max_score: float = 1.0
    criterion: str  # natural-language description of what earns the point


class Question(BaseModel):
    """A benchmark question with structured answer and rubric.

    The answer is computed deterministically from the source-of-truth
    graph (see design doc §9). gpt-oss only writes the question text
    and the rubric criteria, not the answer fields.
    """

    id: str = Field(..., pattern=r"^Q-\d{4}$")
    category: CategoryTarget
    text: str
    ground_truth_answer: dict  # category-specific structured shape
    rubric_subpoints: list[RubricSubpoint]
    evidence_artefact_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage F — Validation report
# ---------------------------------------------------------------------------


ValidationDisposition = Literal[
    "pass",
    "fail_unanswerable",     # evidence missing from corpus
    "fail_memorisation",     # answerable without corpus
    "fail_distractor_missing",  # adversarial question's distractor absent
    "fail_rubric_incoherent",   # rubric doesn't score full marks on GT
]


class ValidationResult(BaseModel):
    question_id: str
    disposition: ValidationDisposition
    notes: str = ""
