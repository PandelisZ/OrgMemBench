# Standing up the Zep/Graphiti backend

The Zep adapter uses **Graphiti** (`graphiti-core`), an open-source
bi-temporal knowledge-graph engine that runs entirely on your infrastructure.
There is no Zep Cloud account required.

## What you need

| Dependency | Why |
|---|---|
| Neo4j 5.x | graph store + full-text search |
| ANTHROPIC_API_KEY | LLM extraction, resolution, answer synthesis (Claude Sonnet 4.6) |
| OPENAI_API_KEY | default Graphiti embedder (text-embedding-3-small) |
| Python 3.10+ | graphiti-core runtime |

---

## 1. Start Neo4j with Docker Compose

Save the following as `docker/neo4j-compose.yml` (or inline into your existing
compose file).

```yaml
version: "3.9"

services:
  neo4j:
    image: neo4j:5.26-community
    container_name: orgmembench-neo4j
    ports:
      - "7474:7474"   # Neo4j Browser (optional)
      - "7687:7687"   # Bolt protocol (Graphiti uses this)
    environment:
      NEO4J_AUTH: "neo4j/your-password-here"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
      NEO4J_dbms_memory_heap_initial__size: "512m"
      NEO4J_dbms_memory_heap_max__size: "2G"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
```

Start it:

```bash
docker compose -f docker/neo4j-compose.yml up -d
# Verify it's up:
docker compose -f docker/neo4j-compose.yml logs -f neo4j
# Should print: "Remote interface available at http://localhost:7474/"
```

Change `your-password-here` to something real and update `NEO4J_PASSWORD`
below.

---

## 2. Environment variables

Export these before running any OrgMemBench commands:

```bash
# Neo4j (must match the compose file above)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password-here"

# LLM + Embedder
export ANTHROPIC_API_KEY="sk-ant-..."   # Claude Sonnet 4.6 — extraction + synthesis
export OPENAI_API_KEY="sk-..."          # OpenAI embedder (default graphiti-core)
```

Add these to a `.env` file (never commit it) and source with:

```bash
set -a && source .env && set +a
```

---

## 3. Install the Python package

```bash
# graphiti-core with Anthropic support pinned to the OrgMemBench-tested version
pip install "graphiti-core[anthropic]==0.29.1"
```

The `[anthropic]` extra installs `anthropic` SDK support alongside the
`graphiti-core` base (which defaults to OpenAI).  Both `anthropic` and
`openai` packages end up installed because the default embedder is OpenAI.

---

## 4. Verify the connection

```python
import asyncio
from graphiti_core import Graphiti

async def ping():
    g = Graphiti("bolt://localhost:7687", "neo4j", "your-password-here")
    await g.build_indices_and_constraints()
    print("Neo4j + Graphiti OK")
    await g.close()

asyncio.run(ping())
```

---

## 5. Run a live OrgMemBench benchmark

```bash
# Disable dry-run to allow real ingest and queries
export ORGMEMBENCH_DRY_RUN=0

python -m orgmembench.harness run \
  --adapter zep \
  --config config/zep.yaml \
  --tier small
```

---

## Notes and caveats

- **APOC plugin** is required by Graphiti for full-text index management.
  The `NEO4J_PLUGINS: '["apoc"]'` line in the compose file handles this
  automatically for Community Edition.

- **Disk space**: Neo4j + a medium-tier benchmark corpus uses ~1-3 GB on
  disk.  The `neo4j_data` volume persists across restarts, so Graphiti will
  reuse the graph between runs without re-ingesting.

- **Temperature**: always set `temperature: 1.0` (not null) when using
  `AnthropicClient`.  A null temperature causes a 400 error from the
  Anthropic API.  See `config/zep.yaml` and
  https://github.com/getzep/graphiti/issues/1103.

- **group_id namespace**: each OrgMemBench benchmark run should use a
  distinct `group_id` (e.g., `orgmembench-small-2026-05-25`) to prevent
  cross-contamination between tiers or re-runs.  Set it in `config/zep.yaml`
  or pass `{"group_id": "..."}` as the adapter config dict.

- **Teardown**: call `adapter.teardown()` or `Graphiti.close()` after a run
  to cleanly close the Neo4j driver connection pool.
