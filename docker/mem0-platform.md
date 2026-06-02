# Mem0 Platform setup

The `mem0-platform` adapter uses the **hosted Mem0 Platform cloud service** at
`https://api.mem0.ai`. There is no local service to run and no Docker container
needed. All infrastructure (vector store, graph DB, LLM extraction, embedder)
is managed by Mem0.

---

## What needs to be running

| Service | Purpose | Address |
|---------|---------|---------|
| (none) | All compute is managed by Mem0 Platform | `https://api.mem0.ai` |

No local processes. No Docker. No Qdrant. No Postgres. Just a key.

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MEM0_API_KEY` | Yes | Platform API key from https://app.mem0.ai |
| `ORGMEMBENCH_DRY_RUN` | No | Set to `0` to allow real runs. Default is `1` (dry-run, free). |

`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are **not required** — LLM extraction
and embeddings are handled server-side by the platform.

Export before running:

```bash
export MEM0_API_KEY="m0-..."
export ORGMEMBENCH_DRY_RUN=0
```

---

## Install the SDK

```bash
# Pinned version (matches config/mem0-platform.yaml)
pip install "mem0ai==2.0.2"

# Or via the OrgMemBench extras:
pip install "orgmembench[mem0]"
```

The `mem0-platform` adapter uses the same `mem0ai` package as the OSS adapter
but instantiates `MemoryClient` (the hosted client) instead of `Memory` (the
OSS self-hosted client).

---

## Get a Mem0 Platform API key

1. Sign up at https://app.mem0.ai
2. Go to Settings > API Keys > Create new key
3. Export as `MEM0_API_KEY`

Free tier: 10,000 memories — sufficient for the small benchmark tier.
For medium/large tiers, the Starter plan ($19/mo) is recommended.

---

## Quick end-to-end check

```bash
# 1. Set env vars
export MEM0_API_KEY="m0-..."

# 2. Verify the adapter imports cleanly (no mem0ai needed for this)
PYTHONPATH=. python -c "
from orgmembench.adapters.mem0_platform_adapter import Mem0PlatformAdapter
a = Mem0PlatformAdapter(dry_run=True)
print('name:', a.name)
print('caps:', a.capabilities)
print('version (not installed = ok):', a.version())
"

# 3. Run a real small-tier benchmark
export ORGMEMBENCH_DRY_RUN=0
python -m orgmembench run mem0-platform --tier small --config config/mem0-platform.yaml
```

---

## Notes and limitations

- **No temporal support.** The Mem0 Platform v3 REST API exposes a
  `reference_date` parameter on search, described as "temporal reasoning
  internally while preserving the normal search response shape." This is
  probabilistic NL-based reasoning, NOT bi-temporal indexing. It cannot answer
  "what was the state of knowledge on date X vs now" and does not implement
  valid_at / ingested_at semantics. C3 (bitemporal) and C4 (audit_replay)
  questions are scored N/A for this adapter — this is expected and correct.

- **Provenance is partial.** The platform stores the `metadata` dict supplied at
  ingest time and returns it in search results. The adapter packs `slot_id` into
  metadata so it can recover `cited_artifact_ids`. There is no full audit chain
  or supersession graph.

- **Managed service is unversioned.** The `mem0ai` SDK is pinned at 2.0.2, but
  the cloud service itself updates continuously without a client-pinnable
  version. Benchmark results are only reproducible when the run date is recorded
  alongside the SDK version.

- **Ingest is async and LLM-heavy server-side.** The platform runs fact
  extraction on each ingested message using its own LLM. The Python client
  returns after queuing the job (event_id + PENDING). For large tiers, allow
  extra time for background processing to complete before querying.

- **Rate limits apply.** Free tier (10K memories) and Starter tier may throttle
  concurrent ingest requests. If you see 429 errors, add a small sleep between
  `add()` calls or upgrade your plan.

- **Collection isolation.** Memories are namespaced by `user_id` (= company
  name). If you re-run a tier without clearing data, the platform may merge or
  update existing memories rather than creating fresh ones. For clean
  reproducibility, use a unique `user_id` suffix per run or clear memories via
  the platform dashboard before re-running.
