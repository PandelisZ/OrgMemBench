# Mem0 local setup

This document covers everything needed to run the `mem0` adapter against a live
Qdrant vector store. The adapter itself (and the OrgMemBench harness) can be
imported and smoke-tested without any of this — only a real
`ORGMEMBENCH_DRY_RUN=0` run requires the services below.

---

## What needs to be running

| Service | Purpose | Default address |
|---------|---------|-----------------|
| **Qdrant** | Vector store for mem0 embeddings | `localhost:6333` |

Qdrant is the only external process required. mem0's LLM calls (Anthropic) and
embedder calls (OpenAI) go directly to their cloud APIs over HTTPS; no local
proxy is needed.

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | LLM for mem0 fact extraction (Claude Sonnet 4.6) |
| `OPENAI_API_KEY` | Yes | Embedder (text-embedding-3-small). mem0 has no Anthropic embedder provider; OpenAI is used for embeddings even when the LLM is Anthropic. |
| `ORGMEMBENCH_DRY_RUN` | No | Set to `0` to allow real runs. Default is `1` (dry-run, free). |

Export them before running:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export ORGMEMBENCH_DRY_RUN=0
```

---

## Docker Compose — Qdrant

Save as `docker/docker-compose.mem0.yml` (or run inline):

```yaml
version: "3.9"
services:
  qdrant:
    image: qdrant/qdrant:v1.13.4   # pin to a known-good release
    container_name: orgmembench-qdrant
    ports:
      - "6333:6333"   # HTTP REST + gRPC
      - "6334:6334"   # gRPC (optional, not used by mem0's default client)
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

volumes:
  qdrant_data:
```

Start it:

```bash
docker compose -f docker/docker-compose.mem0.yml up -d
# verify it's healthy
curl -s http://localhost:6333/healthz
# expected: {"title":"qdrant - vector search engine","version":"..."}
```

---

## Install mem0ai

```bash
# Pinned version (matches config/mem0.yaml)
pip install "mem0ai==2.0.2"

# Or via the OrgMemBench extras:
pip install "orgmembench[mem0]"
```

---

## Quick end-to-end check

```bash
# 1. Start Qdrant (see above)
# 2. Set env vars
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# 3. Verify the adapter imports cleanly (no mem0ai needed for this)
PYTHONPATH=. python -c "
from orgmembench.adapters.mem0_adapter import Mem0Adapter
a = Mem0Adapter(dry_run=True)
print('name:', a.name)
print('caps:', a.capabilities)
print('version (not installed = ok):', a.version())
"

# 4. Run a real small-tier benchmark
export ORGMEMBENCH_DRY_RUN=0
python -m orgmembench run mem0 --tier small --config config/mem0.yaml
```

---

## Alternative: on-disk Qdrant (no Docker)

If you prefer not to run Docker, mem0 can use Qdrant in embedded (on-disk)
mode. In `config/mem0.yaml`, comment out `vector_store_host`/`vector_store_port`
and uncomment:

```yaml
vector_store_path: "/tmp/orgmembench_qdrant"
```

This uses Qdrant's Python client in local mode (slower, not suitable for large
tiers, but zero infrastructure).

---

## Alternative: replace OpenAI embedder with HuggingFace

To avoid the `OPENAI_API_KEY` requirement entirely, switch to a local embedder
in `config/mem0.yaml`:

```yaml
embedder_provider: "huggingface"
embedder_model: "sentence-transformers/all-MiniLM-L6-v2"
```

Install the extra dep:

```bash
pip install sentence-transformers
```

The model is downloaded on first use (~90 MB) and cached locally. Embedding
quality is lower than `text-embedding-3-small`; benchmark scores will differ.

---

## Notes and limitations

- **No temporal support.** mem0 is vector-first; it records `created_at` /
  `updated_at` wall-clock timestamps but has no `as_of` / time-travel query
  API. C3 (bitemporal) and C4 (audit_replay) questions are scored N/A for this
  adapter — this is expected and correct.
- **Provenance is partial.** mem0 returns `memory_id` + the metadata we store at
  ingest time (including `slot_id`). The adapter maps these back to
  `cited_artifact_ids`. This satisfies the PROVENANCE capability, but mem0 does
  not store a full audit chain or supersession graph.
- **Ingest is LLM-heavy.** mem0 calls the LLM at ingest time to extract and
  consolidate facts from each message. For large tiers this is slow and costly
  compared to pure-vector systems. Budget accordingly.
- **Collection isolation.** All companies in a single benchmark run share one
  Qdrant collection (`orgmembench`) but are isolated by `user_id` (= company
  name). If you re-run a tier, mem0 will attempt to merge/update existing
  memories — for clean reproducibility, drop and recreate the collection between
  runs (or use `vector_store_collection: "orgmembench_<run_id>"`).
