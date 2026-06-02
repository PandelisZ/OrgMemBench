# OrgMemBench — System Configuration & Replication Guide

Authoritative operational record for **how every reported number was produced**: exact
versions, models, embeddings, retrieval settings, ingest/readiness procedure, the run
command, and the recovery steps for each failure mode we have hit. This is the operational
companion to the paper's Appendix C (Baseline Hyperparameters); the paper summarizes, this
file lets you re-run.

Last updated: 2026-06-01 (after the helix-medium run + readiness-gate hardening).

---

## 0. Shared setup (every system)

| Component | Value | Source |
|---|---|---|
| Judge | Claude **Sonnet 4.6**, extended thinking **4000** tokens, temp **1.0**, max-output **8000** | `orgmembench/config.py` (`JUDGE_MODEL`, `THINKING_BUDGET_TOKENS`, `MAX_OUTPUT_TOKENS`) |
| Shared neutral answerer | Claude Sonnet 4.6, ~**3500** thinking tokens | `orgmembench/answerer.py` — used by zep-cloud, mem0-platform, graphify-oss |
| Native answerer | the system's own synthesizer | gbrain `think` — used per "native answerer if a system has one" |
| Retrieval depth | `top_k = 10` wherever configurable | per-adapter `_DEFAULT_TOP_K` |
| Tiers | small = 11 q / 121 artifacts · medium = 73 q / 443 artifacts · large = (in progress) | `datasets/helix/<tier>/benchmark_v0.0.jsonl` |

**Keys** (in `.env`, never committed): `ANTHROPIC_API_KEY` (judge + answerer + every Anthropic-billed
system LLM), `OPENAI_API_KEY` (mem0-OSS embeddings only), `MEM0_API_KEY`, `ZEP_API_KEY`.

**Run command** (the canonical invocation; always source `.env` with allexport):
```bash
cd /path/to/OrgMemBench
set -o allexport; source ./.env; set +o allexport
python3 -m orgmembench.cli run --system <system> --tier <small|medium|large> --execute
# dry-run (no spend) is the default; --execute actually runs.
```

**Re-query an already-ingested store** (skip ingest + drain, query the existing store):
```bash
ORGMEMBENCH_REUSE_INGEST=1 python3 -m orgmembench.cli run --system <system> --tier <tier> --execute
```

---

## 1. THE READINESS-GATE RULE (the most important section)

A system must be **(a) fully written AND (b) searchable** before any question is asked.
**Synchronous** systems satisfy this when the ingest call returns. **Asynchronous** (hosted)
systems do **not** — extraction continues server-side after the client call returns, and a
naive "ingest returned" / "count plateaued" signal will query a partially-built store and
**silently understate the system**.

### Sync vs async

| System | Ingest | Drain needed? |
|---|---|---|
| gbrain | SYNC (capture blocks through write) | no |
| graphify-oss | SYNC (`extract` blocks until `graph.json` written) | no — but **timeout must scale with corpus** (see §5) |
| **zep-cloud** | **ASYNC** (graph builds for minutes after `graph.add`) | **YES** |
| **mem0-platform** | **ASYNC** (extraction continues after `add()`) | **YES** |

### Why a stability-window drain is NOT enough (the 2026-06-01 medium bug)

Server-side extraction proceeds in **bursts with multi-minute pauses**. A "count stable for N
polls" drain mistakes a pause for completion:
- **zep-cloud medium** plateaued at **368 edges for ~75s** → old drain SETTLED there and queried a
  graph that later finished at **1000+ edges** (only **37% built**). Reported 0.094; the real
  value on the complete graph is **0.209**.
- **mem0-platform medium** climbed 43→88, paused ~40s → SETTLED at 88 while extraction continued
  to 100 memories (**88% built**). Reported 0.236; real value **0.273**.

**Fix (now in both adapters):** after the count looks stable, do a **CONFIRMATION HOLD** —
sleep a long window (default 120s) and re-check; if it grew, the "stability" was a pause, so
resume draining. Only settle when the count survives the hold unchanged. Plus larger windows
and (mem0) a bigger probe `top_k`.

Drain knobs (env-overridable):
- zep: `ZEP_DRAIN_MAX_WAIT=3600`, `ZEP_DRAIN_MIN_WAIT=120`, `ZEP_DRAIN_INTERVAL=15`, `ZEP_DRAIN_STABLE=6`, `ZEP_DRAIN_CONFIRM_HOLD=120`. Count via uncapped `graph.edge.get_by_graph_id` (NOT `graph.search`, which caps ~50).
- mem0: `MEM0_DRAIN_MAX_WAIT=2400`, `MEM0_DRAIN_MIN_WAIT=120`, `MEM0_DRAIN_INTERVAL=10`, `MEM0_DRAIN_STABLE=8`, `MEM0_DRAIN_CONFIRM_HOLD=120`, `MEM0_DRAIN_PROBE_TOPK=2000`. Count via a probe `search()` (NOT `get_all`, which plateaus on transient values).

### MANDATORY post-run validity check (do this every time for async systems)

After a hosted run, query the **live** store size and compare to the count at query time. If it
grew, the drain settled early → the run is INVALID → re-query the now-settled store with
`ORGMEMBENCH_REUSE_INGEST=1` (+ `MEM0_PIN_USER_ID=<user>` for mem0).
```python
# zep:   z.graph.edge.get_by_graph_id(graph_id="helix-<tier>", limit=10000)  -> len
# mem0:  m.get_all(version="v2", filters={"user_id":"<pinned user>"}, page_size=2000) -> len
# Poll twice ~45s apart; equal == settled == safe to trust the run.
```

---

## 2. gbrain (Garry Tan's open gbrain)

| Setting | Value |
|---|---|
| Version | `gbrain 0.41.6.0` |
| Container | `orgmembench-gbrain` + `orgmembench-gbrain-pg-1` (Postgres backend) |
| LLM | `anthropic:claude-sonnet-4-6` (via `gbrain think --model`); env `GBRAIN_LLM_MODEL` |
| Embeddings | ZeroEntropy `zembed-1` (native default) |
| Retrieval | hybrid BM25 + dense-vector + graph traversal; `top_k=10` |
| Answerer | native `gbrain think --json` |
| Ingest | SYNC; per-artifact `capture --stdin --slug orgmembench/<slot_id>`, **parallelized** (`GBRAIN_INGEST_CONCURRENCY=8`, default 8) |
| Drain | none (sync) |

Run: `... run --system gbrain --tier <tier> --execute` (set `GBRAIN_INGEST_CONCURRENCY=8`).
Gotcha: earlier PGLite single-writer lock → switched to Postgres backend (`-pg-1` sidecar).

## 3. zep-cloud (Zep / Graphiti, hosted)

| Setting | Value |
|---|---|
| SDK | `zep-cloud 3.22.0` (service unversioned; recorded as `3.22.0+cloud`) |
| Endpoint / plan | `api.getzep.com/api/v2`, **FREE** (1000 episodes/month) |
| Ingest | `graph.add(graph_id=<scope>, type="text", data=...)`; ASYNC |
| Retrieval | `scope="edges"` (NOT `"auto"`), `limit=min(k,50)`, reranker `rrf` |
| Embeddings / extractor | hosted, undisclosed |
| Drain | confirmation-hold (see §1); uncapped `graph.edge.get_by_graph_id` |
| Reset race fix | poll `graph.get` after `graph.create` (defeats delete→create→add 404) |
| Rate limits | honor `Retry-After` (free plan ~5 req/6s); adapter retries with backoff |

Run: `... run --system zep-cloud --tier <tier> --execute`.
Gotchas: **episode quota** — a full medium run (443 episodes) plus repeats exhausts the free
1000/month; rotate `ZEP_API_KEY` if you hit 403 "over the episode usage limit". The hosted
extractor is **sparse at scale** (medium graph ~1000 edges vs small ~654 — sub-linear due to
entity consolidation), which is a real system property, not a bug.

## 4. mem0-platform (Mem0 hosted)

| Setting | Value |
|---|---|
| SDK | `mem0ai 2.0.2` (platform) |
| Endpoint / plan | `api.mem0.ai/v3`, **FREE** tier |
| Namespace | **fresh `user_id` per attempt** (`<scope>-<uuid8>`); pin via `MEM0_PIN_USER_ID` to re-query |
| Retrieval | `search(version="v2", filters={"user_id":...}, top_k=10)` |
| Embeddings / extractor | hosted, undisclosed (NOT user-configurable) |
| Drain | probe-`search` confirmation-hold (see §1); probe `top_k=2000` |

Run: `... run --system mem0-platform --tier <tier> --execute`.
Gotchas: fresh-user_id-per-attempt avoids stale async deletes racing a new ingest (this
vaporized an early run). Extraction is **sparse** (~100 memories for 443 medium artifacts).
The C4 (audit-replay / negative-knowledge) category can be **inflated** for sparse-retrieval
systems that default to "nothing changed" — note this in analysis.

## 5. graphify-oss (safishamsi/graphify v8)

| Setting | Value |
|---|---|
| Source | `safishamsi/graphify` v8, commit `b07f0eb`; PyPI `graphifyy 0.8.20` |
| Container | `orgmembench-graphify-oss` (docker-compose; host `GRAPHIFY_OSS_WORKDIR` → `/data` bind mount) |
| Invocation | `docker exec` (env `GRAPHIFY_OSS_DOCKER_CONTAINER=orgmembench-graphify-oss`) |
| Extract | `graphify extract <corpus> --backend claude --out <scope> --max-concurrency 8` (`GRAPHIFY_OSS_EXTRACT_CONCURRENCY`, default 8) |
| Extract model | `claude-sonnet-4-6` (upstream hardcoded default) |
| **Extract timeout** | **`_EXTRACT_TIMEOUT_S = 7200`** (2h). The old 1800s was sized for the 121-doc small tier and **silently truncated the 443-doc medium extraction** (no graph.json → all "graph file not found" → artificial zeros). Timeout MUST scale with corpus. |
| Query | `graphify query "<q>" --graph <path> --budget N` (BFS depth 2) |
| Embeddings | **none** (pure BFS/DFS over `graph.json`) |
| Ingest | SYNC (`extract` blocks until `graph.json` written, then queries) |
| Bi-temporal | none (`as_of` ignored) |

Run (Docker must be up + container started):
```bash
docker compose -f docker/graphify-oss/docker-compose.yml up -d   # GRAPHIFY_OSS_WORKDIR set
GRAPHIFY_OSS_DOCKER_CONTAINER=orgmembench-graphify-oss GRAPHIFY_OSS_EXTRACT_CONCURRENCY=8 \
  ... run --system graphify-oss --tier <tier> --execute
```
Gotchas: (1) extraction writes `graph.json` **only at the end** (q=0 / empty out-dir mid-run is
normal — confirm progress via live Anthropic connections, not disk). (2) Anthropic
rate-limit **contention**: running graphify extraction alongside other Anthropic-heavy runs
(judge+answerer) on the same key throttles it badly (medium extraction went from ~12 min
uncontended to ~40 min contended). Prefer to run graphify extraction alone, or expect it slow.
(3) `graph.json` writes at end → 1 node/artifact at org-scale (coarse) is the root cause of its
high retrieval-miss rate.

---

## 6. Recovery procedures (failure modes hit this session)

| Symptom | Cause | Fix |
|---|---|---|
| Query "graph file not found" (graphify) | extract timed out before writing graph.json | raise `_EXTRACT_TIMEOUT_S` / scale with corpus; re-run |
| Two `graphify extract` procs racing | host `pkill` killed the harness but the `docker exec` extract orphaned in-container | **`docker restart <container>`** (slim images lack `pkill`); then relaunch once |
| `Timed out waiting for PGLite lock` (gbrain) | prior run left a DB lock | `docker restart <container>` to clear, then `ORGMEMBENCH_REUSE_INGEST=1` resume |
| `Connection reset` / DNS fail mid-run | internet/Wi-Fi switch | kill + relaunch with `ORGMEMBENCH_REUSE_INGEST=1` (checkpoint resumes from partial) |
| zep `403 over the episode usage limit` | free plan 1000 episodes/month exhausted | rotate `ZEP_API_KEY` |
| zep every `graph.add` 404s | `graph.delete` from reset still propagating when `graph.create`/`add` fire | the adapter's `graph.get` post-create poll handles it |
| Hosted result suspiciously low / sparse | drain settled on a mid-build pause | post-run live-count check (§1); re-query settled store via REUSE_INGEST |

## 7. Results provenance

- Final per-tier results: `results/<system>/helix-<tier>.json`.
- Superseded/invalid runs (premature drain, host-vs-docker, timeouts) are archived under
  `results/_prior_runs/` with descriptive suffixes, e.g.
  `zep-cloud-helix-medium-premature-drain-368edges.json`,
  `mem0-platform-helix-medium-premature-drain-88mem.json`.
- Every dataset change is logged in `datasets/helix/<tier>/CHANGELOG.md` with pre-patch backups.
