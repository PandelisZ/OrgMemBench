# Standing up the Zep Cloud backend

The Zep Cloud adapter uses the **managed Zep Cloud service** (`cloud.getzep.com`).
There is **no local service to stand up** — no Docker, no Neo4j, no embedder process.
All graph ingestion, entity extraction, summarization, embedding, and fact-rating
run inside Zep's infrastructure.

---

## What you need

| Dependency | Why |
|---|---|
| `ZEP_API_KEY` | Authenticates every SDK call to the hosted API |
| Python 3.9+ | `zep-cloud` SDK runtime |

No `ANTHROPIC_API_KEY`.  No `OPENAI_API_KEY`.  No local database.

---

## 1. Create a Zep Cloud account and get an API key

1. Sign up at [cloud.getzep.com](https://cloud.getzep.com).
2. In the dashboard, navigate to **Settings** > **API Keys**.
3. Create a new key and copy it — you will not be able to view it again.

---

## 2. Set the environment variable

```bash
export ZEP_API_KEY="z_..."   # your Zep Cloud API key
```

Add to a `.env` file (never commit it):

```bash
# .env
ZEP_API_KEY=z_...
```

Source with:

```bash
set -a && source .env && set +a
```

---

## 3. Install the Python SDK

```bash
pip install "zep-cloud==3.22.0"
```

Verify:

```bash
pip show zep-cloud | grep Version
# Version: 3.22.0
```

---

## 4. Verify the connection

```python
import os
from zep_cloud.client import Zep

client = Zep(api_key=os.environ["ZEP_API_KEY"])

# Quick ping: list groups (returns empty list if no data yet — that is fine)
print("Zep Cloud connection OK")
```

---

## 5. Run a live OrgMemBench benchmark

```bash
# Disable dry-run to allow real ingest and queries
export ORGMEMBENCH_DRY_RUN=0

python -m orgmembench.harness run \
  --adapter zep-cloud \
  --config config/zep-cloud.yaml \
  --tier small
```

---

## Notes and caveats

- **No local infrastructure.** Unlike the OSS `zep` adapter (graphiti-core +
  Neo4j), Zep Cloud runs entirely on Zep's servers.  Latency numbers will
  include network round-trips to the Zep Cloud API.

- **SDK version vs. service version.** The `version` pin in `config/zep-cloud.yaml`
  refers to the `zep-cloud` Python SDK.  The hosted service is independently
  versioned; the adapter records `{sdk_version}+cloud` in results to make this
  distinction clear.

- **group_id namespace.** Each OrgMemBench benchmark run should use a distinct
  `group_id` (e.g., `orgmembench-small-2026-05-25`) to prevent cross-run
  contamination.  Set it in `config/zep-cloud.yaml` or pass
  `{"group_id": "..."}` as the adapter config dict.

- **Temporal filtering scope.** Zep Cloud's `SearchFilters` (valid_at /
  invalid_at date filters) apply **only** to `scope="edges"` searches.  The
  adapter automatically switches to `scope="edges"` when `as_of` is set.

- **Provenance.** Returned edges include `episodes` (a list of episode UUIDs).
  Full slot_id back-mapping requires a secondary episode-lookup API call per
  edge, which the adapter currently defers (the episode UUIDs are recorded in
  `QueryResult.raw["episode_uuids"]` for manual reconstruction).

- **Teardown.** The `zep-cloud` SDK uses stateless HTTP; `adapter.teardown()`
  is a no-op that simply drops the client reference.  No connection pool needs
  draining.

- **Disk space.** None — data is stored in Zep Cloud.  Ensure your Zep Cloud
  plan supports the volume of data for the benchmark tier you intend to run.
