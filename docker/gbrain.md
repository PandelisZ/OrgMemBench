# gbrain — Installation and Setup Guide

## Pinned version

| Field   | Value |
|---------|-------|
| Version | `0.41.6.0` |
| Commit  | `3a2605e9a0b746a82ab42dd0177fc0f3a666a600` |
| Date    | 2026-05-25 |
| Tag     | `v0.41.6.0` (CI speedup release) |

gbrain updates extremely frequently. Always install the pinned commit. Never run `bun upgrade` during or between benchmark runs — version drift invalidates comparisons.

---

## Prerequisites

- **Bun** >= 1.1 — [https://bun.sh](https://bun.sh)
  ```bash
  curl -fsSL https://bun.sh/install | bash
  ```
- **API keys** (at least one embedding provider + the LLM provider):

  | Key | Purpose | Required? |
  |-----|---------|-----------|
  | `ANTHROPIC_API_KEY` | `gbrain think` LLM synthesis (claude-sonnet-4-6) | Yes |
  | `ZEROENTROPY_API_KEY` | Default embeddings + zerank-2 reranker | Recommended |
  | `OPENAI_API_KEY` | Alternative embedding provider | Either/or with ZeroEntropy |

---

## Install the pinned version

```bash
# Install the exact commit (never "latest")
bun install -g github:garrytan/gbrain#3a2605e9a0b746a82ab42dd0177fc0f3a666a600

# Verify
gbrain --version
# Expected output: gbrain 0.41.6.0

gbrain version --json
# Expected: {"version": "0.41.6.0", "commit": "3a2605e9a0b..."}
```

---

## Stand up the database

gbrain supports two storage backends.

### Option A — PGLite (recommended for benchmarking, no Docker needed)

Postgres 17 runs in-process via WASM. Up to ~50K pages.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export ZEROENTROPY_API_KEY=ze-...

gbrain init --pglite
gbrain doctor          # verify all systems green
```

### Option B — Postgres (Supabase or self-hosted, for larger runs)

```bash
export DATABASE_URL="postgres://user:pass@host:5432/gbrain"
gbrain init --postgres --connection-string "$DATABASE_URL"
gbrain doctor
```

---

## Dockerfile snippet (Bun base image)

Use this to containerise the benchmark runner with a pinned gbrain install:

```dockerfile
FROM oven/bun:1.1-slim AS gbrain-install

# Install system deps (needed for PGLite WASM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Install the EXACT pinned commit — do NOT use "latest" or a semver range.
RUN bun install -g \
    github:garrytan/gbrain#3a2605e9a0b746a82ab42dd0177fc0f3a666a600

# Verify the installed version matches the pin.
RUN gbrain --version | grep -q "0.41.6.0" \
    || (echo "ERROR: gbrain version mismatch — update the pinned commit in docker/gbrain.md and config/gbrain.yaml" && exit 1)

# -------------------------------------------------------
# Python benchmark runner layer
FROM oven/bun:1.1-slim AS runner

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy gbrain binary from the install stage
COPY --from=gbrain-install /root/.bun/bin/gbrain /usr/local/bin/gbrain

WORKDIR /bench

# Install Python deps
COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]"

COPY . .

# Initialise PGLite DB at container build time (zero-server, no Postgres needed)
RUN gbrain init --pglite

ENTRYPOINT ["python", "-m", "orgmembench.cli"]
```

Build and run:

```bash
docker build -t orgmembench-gbrain .
docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e ZEROENTROPY_API_KEY="$ZEROENTROPY_API_KEY" \
  -e ORGMEMBENCH_DRY_RUN=0 \
  orgmembench-gbrain run gbrain --tier small
```

---

## Updating the pinned version

When you need to update gbrain:

1. Find the new commit SHA:
   ```bash
   curl -s https://api.github.com/repos/garrytan/gbrain/commits?per_page=1 \
     | python3 -c "import sys,json; c=json.load(sys.stdin)[0]; print(c['sha'], c['commit']['message'][:80])"
   ```
2. Update `config/gbrain.yaml` — both `version:` and `commit:` fields.
3. Update the commit SHA in this file (all three occurrences above).
4. Re-run the full benchmark from scratch (do not mix result files across versions).
5. Commit the config change alongside the new results entry.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `gbrain: command not found` | Check `bun` is on PATH; re-run `bun install -g ...` |
| `gbrain doctor` reports DB error | Re-run `gbrain init --pglite` |
| `gbrain think` hangs | Default timeout is 180s; check `ANTHROPIC_API_KEY` is set |
| Version drift warning in benchmark | Install the pinned commit exactly; don't `bun upgrade` |
| ZeroEntropy embedding errors | Set `ZEROENTROPY_API_KEY` or pass `--embedding-model openai:text-embedding-3-large` to `gbrain init` |
