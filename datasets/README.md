# Datasets

OrgMemBench evaluates memory systems over **synthetic fictional companies** with
years of multi-source history. The ground truth is fully known (projected
deterministically from a source-of-truth graph), so labels are unambiguous and
there is no training-data contamination.

> **This directory is the authority for the dataset.** The full Helix corpus +
> ground truth are vendored here (`helix/{small,medium,large}/`), licensed
> CC BY 4.0 ([`LICENSE`](LICENSE)). Heavy-tier hosting at public release (git vs
> HuggingFace) is still open; for now everything lives in-repo.

## Companies & tiers

- **Helix** — seed company (small-to-mid SaaS, ~85 people, multi-year history).
  Tiers present: **small** (14 questions), **medium** (73), **large** (113).
  **xl / xxl** planned; additional companies (different size/vertical/stage)
  planned for generalization claims.

## Per-tier layout (`helix/<tier>/`)

- `benchmark_v0.0.jsonl` — the validated question + ground-truth-answer set (use this).
- `questions_draft.jsonl`, `emergent_questions.jsonl` — source question sets.
- `corpus_index.jsonl` + `corpus/` — the artefacts (one file per slot_id).
- `source_of_truth/{events,relations}.jsonl` — the graph answers project from.
- `helix_canon/` — personas, customers, channel timeline, skeleton.

## Artifact schema (the corpus)

Each corpus artifact is one document/thread from one channel, with a normalized
header the harness can map to any system's ingest API:

```json
{
  "slot_id": "ART-EV-2023-007-001",
  "company": "helix",
  "source_type": "slack_thread | email_thread | meeting_transcript | notion_doc | ticket | crm_note | ...",
  "timestamp": "2023-07-15",
  "author": "P-0009",
  "thread_id": "EV-2023-007",
  "role": "primary | secondary | noise | emergent_evidence",
  "text": "<the artifact body>"
}
```

## Question schema (the ground truth)

```json
{
  "id": "Q-0001",
  "company": "helix",
  "category": "single_hop | multi_hop | temporal | supersession | aggregation | causal | scope_aware | negative_knowledge | provenance | emergent",
  "difficulty": "easy | medium | hard",
  "text": "<the question, surface-simple where appropriate>",
  "as_of": "2023-06-01 | null",
  "ground_truth_answer": { "...": "category-specific structured answer / facets" },
  "rubric_subpoints": [ { "id": "sub1", "weight": 0.2, "criterion": "...", "fail_if": "..." } ],
  "evidence_artifact_ids": ["ART-...", "ART-..."],
  "capabilities_required": ["temporal", "provenance"]
}
```

See `docs/PLAN.md` §3 for the full taxonomy and §9 for ground-truth quality /
inter-rater-agreement requirements.
