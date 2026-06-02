# Adapters

One adapter per system, all implementing the same contract (`base.py`) so the
harness runs any of them identically. See `docs/CONTRIBUTING-AN-ADAPTER.md`.

Memory systems only — **no retrieval baselines** (dropped on purpose; a separate
article covers baseline critique). OSS/self-hosted and hosted variants are
separate, precisely-labeled contestants (run with vendor-recommended configs in
`config/<name>.yaml`):

| Adapter | What it is | Hosted? | Temporal |
|---|---|---|---|
| `mem0` | `mem0ai` OSS, self-hosted (Qdrant) | no | no |
| `mem0-platform` | Mem0 Platform managed API | yes | no |
| `graphiti` | `graphiti-core` — Zep's OSS engine (Neo4j) | no | yes |
| `zep-cloud` | Zep Cloud managed product | yes | yes |
| `gbrain` | gbrain OSS (TS CLI, PGLite) | no | no |
| `graphify-oss` | graphify OSS (CLI, temporal graph) | no | yes |

`reference` is a dev fixture (no LLM, free) — the contract template, excluded
from the leaderboard.

## Answering (retrieval vs. prose)

These are QA systems, not retrieval systems: every contestant is judged on a
**prose answer**. The rule: *if a system ships its own prose answerer, use it;
otherwise wrap its retrieved memories with the neutral basic answerer*
(`orgmembench/answerer.py`).

- Adapters return what they RETRIEVED in `QueryResult.retrieved_context`.
- Adapters that produce their own answer set `self_answers = True` and fill
  `answer_text`: **gbrain** (`gbrain think`) and `reference`.
- Everyone else (`mem0`, `mem0-platform`, `zep-cloud`, `graphiti`,
  `graphify-oss`) is retrieval-only; the runner applies the basic answerer over
  `retrieved_context`.

The basic answerer takes the question **and** the retrieved context, and uses
the same model (Sonnet 4.6 + extended thinking) as every other LLM role — only
the prompt differs.

Each adapter resolves its system's **runtime version** (`config/<name>.yaml`
pins the expected version; the base class warns on drift) — recorded into every
result for reproducibility.
