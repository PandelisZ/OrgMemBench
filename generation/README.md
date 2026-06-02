# helix-corpus

Helix benchmark — **corpus generation pipeline**. Stages A through F: company
canon → source-of-truth graph → corpus → cross-references → questions →
validation. All LLM calls go through one open-weight model, `gpt-oss:20b`,
served behind an OpenAI-compatible API (e.g. a local Ollama or vLLM server).

This package is intentionally **scoped to generation only**. The benchmark
*runner* (ingesting the corpus into systems-under-test, asking questions,
scoring) lives in the separate `orgmembench` harness package. See the
[paper](../paper/) for the full design rationale: the category taxonomy,
persona schema, genre taxonomy, and the gap analysis vs LoCoMo / LongMemEval / BEAM.

## Quickstart

```bash
# 1. Point the pipeline at an OpenAI-compatible endpoint serving gpt-oss:20b
#    (e.g. a local Ollama or vLLM server).
export GRAPHIFY_LLM_BACKEND=openai_compat
export GRAPHIFY_LLM_BASE_URL=https://your-endpoint.example/v1
export GRAPHIFY_LLM_API_KEY=...           # if your endpoint requires one
export GRAPHIFY_AGENT_MODEL=gpt-oss:20b
# Optional extra request headers (JSON), if your endpoint sits behind a proxy:
# export GRAPHIFY_LLM_EXTRA_HEADERS='{"Header-Name":"value"}'

# 2. Install
pip install -e .

# 3. Run a stage
helix-corpus run --stage A --size small
```

## Pipeline stages

| Stage | What it does | Wire format gpt-oss emits | Output |
|---|---|---|---|
| A | Company canon (founders, year arcs, personas, customer arcs, doc-discipline eras, tooling timeline) | Markdown + YAML | `data/helix_canon/` |
| B | Source-of-truth graph (events, relationships, coverage by benchmark category) | Markdown + YAML + triples | `data/source_of_truth/` |
| C | Corpus (Slack, ADRs, meeting transcripts, retrospectives, etc.) | Genre-shaped Markdown/JSONL | `data/corpus/` |
| D | Cross-references + noise injection | small prose calls | augments corpus + `data/noise_manifest.jsonl` |
| E | Questions (deterministic answers from graph + gpt-oss phrasing) | structured Markdown + computed JSON | `data/questions.jsonl` |
| F | Self-consistency validation (answerability, memorisation, distractor, rubric coherence) | gpt-oss self-checks | `data/validation_report.jsonl`, `data/benchmark_v0.0.jsonl` |

Each stage produces an inspectable artefact reviewed before the next stage runs.

## Sizes

| Size | Scope | Artefacts | Questions |
|---|---|---|---|
| Small | 1 quarter × 1 team | 121 | 11 |
| Medium | 1 year × all teams | 443 | 73 |

Larger tiers (multi-year, full-canon) are supported by the pipeline but not shipped
in this release.

## Methodological honesty

Single-model end-to-end generation is **methodologically circular by construction**:
the same model writes the questions, the answers, and grades the validation.
Structural defences (closed-enum event types, deterministic graph projections for
answers, multi-pass critique, automated sentinels for n-gram diversity / persona
consistency / anachronism) compensate but don't eliminate circularity.

Defensibility against the "GPT-easy questions" failure mode is addressed by a
planned cross-model validation pass, in which a frontier model replaces gpt-oss in
the validator and judge roles. See the [paper](../paper/) for details.
