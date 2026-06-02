# How we compute every number (scoring + cost)

This is the canonical reference for how a result is produced and how each figure
in the per-tier write-ups is calculated. Every system is run and scored
**identically**; to add a new system's numbers, pull the same fields (see
[Replication](#replication) at the bottom) — do not hand-compute.

## 1. The run pipeline (per system, per tier)

```
load corpus(tier)                      # normalized Artifact stream
ensure_clean_scope()                   # wipe (OSS/local) or verify-empty (hosted) the per-tier scope
ingest(corpus)                         # system-native ingestion
for each question:
    retrieved_context = system.retrieve(question[, as_of])   # memories/facts the system surfaces
    answer = answerer(question, retrieved_context)           # see §2
    verdict = judge(question, answer)                        # Sonnet 4.6 + thinking, rubric
metrics = compute_metrics(...)         # §3
usage   = build_usage(...)             # §4
```

Per-tier **isolation**: every system stores/queries under scope `"<company>-<tier>"`
(e.g. `helix-small`) — per-tier `user_id` (mem0, mem0-platform), `graph_id`
(zep-cloud), `group_id` (graphiti), Qdrant collection (mem0).
So small/medium/large never cross-contaminate.

## 2. Answering (what gets judged)

We score a **prose answer**, not raw retrieval. The rule: *use a system's own
prose answerer if it ships one; otherwise wrap its retrieved memories with the
neutral basic answerer.* All answerers use the same model (Sonnet 4.6 + extended
thinking); only the prompt differs.

| System | Answer produced by |
|---|---|
| gbrain | its own `gbrain think` (native, cited multi-hop) |
| mem0 · mem0-platform · zep-cloud · graphiti | the neutral **basic answerer** (`orgmembench/answerer.py`) over retrieved memories |

graphiti is treated as retrieval-only (graphiti-core ships no answerer).

## 3. Scoring

The judge (Claude Sonnet 4.6, extended thinking ON) returns, per question:
`subpoint_scores` (0–1 per rubric subpoint), `exact_match` (bool),
`semantic_score` (0–1), `faithful` (bool), `failure_mode`.

- **Per-question score** = rubric-weighted mean of subpoint fractions, weights =
  each subpoint's `max_score`. Computed in code (we never trust LLM arithmetic):
  `score = Σ(weight_i · frac_i) / Σ(weight_i)`.
- **`by_category`** = mean per-question score within each category (C1→supersession,
  C2→decision_provenance, C3→bitemporal, C4→audit_replay, C5→justification_chain,
  C6→contradiction, HARD→multi_hop_lineage, EMERGENT→emergent_pattern).
- **Capability-aware N/A**: if a system does not declare a category's required
  capability, that category is **N/A**, not 0. C3/C4 require `TEMPORAL`; C2/C5
  require `PROVENANCE`. A vector-only system is N/A on C3/C4 — it is **not**
  penalized for a question it structurally cannot answer. This is the core
  fairness rule.
- **`accuracy`** = exact-match rate (binary). This is *stricter* than the rubric
  score and is usually near 0 on hard org questions; the headline number is the
  rubric-weighted `by_category` / overall, not `accuracy`.
- **`by_difficulty`** = mean score per difficulty tier.
- **`failure_modes`** = counts of the judge's per-question label:
  `retrieval_miss` (evidence never surfaced), `wrong_synthesis` (had context,
  synthesized wrong), `hallucination` (confident + unsupported), `wrong_abstain`
  (abstained when answerable).

`failure_modes` is the most diagnostic field: `retrieval_miss` blames the memory
system; `wrong_synthesis` blames the answerer; this separation is why we hold the
answerer constant across systems.

## 4. Cost & usage metering

We report what we can **measure exactly**, and are explicit about what we can't.

- **Measured (proven)** = the LLM calls *we* make: the **answerer** (1/question,
  except gbrain whose `think` runs in a subprocess and isn't surfaced) + the
  **judge** (1/question). Token counts come from the Anthropic API `usage`;
  cost = `input·$3/M + output·$15/M` (Sonnet 4.6). `measured_anthropic_cost_usd`
  = answerer + judge.
- **Native units** = the vendor's own metering, so we can reconcile against each
  dashboard / free tier: mem0 → `add_requests` (= artifacts) + `retrieval_requests`
  (= questions); zep-cloud → `episodes` (= artifacts); etc.
- **NOT measured** (read the provider console for these): a self-hosted system's
  internal extractor (mem0, graphiti) runs inside its SDK; hosted systems
  (mem0-platform, zep-cloud) run ingest/retrieval server-side; gbrain's
  `think` + ZeroEntropy run in a subprocess. These tokens are real but not
  surfaced to the harness.
- **Estimate** = the pre-run `cost.py` per-cell figure, attached to every run so
  we can compare actual vs estimate. (Early finding: actual LLM cost runs well
  under estimate because the extended-thinking *budget* is a ceiling, not the
  actual spend.)

## Replication

For any completed run, every figure above comes from
`results/<system>/<company>-<tier>.json`:

- Scores: `metrics.accuracy`, `metrics.by_category`, `metrics.by_difficulty`,
  `metrics.failure_modes`.
- Usage: `metrics.usage.measured`, `metrics.usage.native_units`,
  `metrics.usage.ingest`, `metrics.usage.estimate`, `metrics.usage.not_measured`.

Or use the CLI: `orgmembench leaderboard` (scores) and `orgmembench usage`
(measured-vs-estimate across all runs). **Never hand-compute** — pull these
fields so every system is treated identically.
