# graphify-oss — thin image wrapping safishamsi/graphify v8
# Upstream commit: b07f0eb6a7d336142430a6c64ef23ae013255690
#
# Design decisions:
#   - We install from PyPI (pip install "graphifyy[pdf]") rather than copying
#     the vendored source so the image stays cache-friendly across re-runs.
#     We pin to exactly 0.8.20 (the version at vendored commit).
#   - No HTTP server; the adapter shells out to the `graphify` CLI directly
#     inside the container via `docker exec`.
#   - `anthropic` is added for the Claude backend (_call_claude uses it directly).
#   - Working directory /data is the per-run corpus scratch area; the adapter
#     mounts a host tmpdir there at run time.
#
# Env vars supplied at run time (never baked in):
#   ANTHROPIC_API_KEY  — Claude Sonnet 4.6 extraction backend (required)
#
# Embedding: none. graphify uses pure BFS/DFS graph traversal for queries;
#   no embedding provider is needed. The only LLM call is at extract time
#   (document-to-graph semantic extraction via Claude).
#
# Port: none exposed. Container is used headlessly via `docker exec`.

FROM python:3.12-slim

# System deps (tree-sitter needs a C compiler; graphify bundles pre-built grammars
# so we only need git for metadata and the compiler for any fallback wheel builds).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# Install graphify at the pinned version with pdf + anthropic extras.
# anthropic is NOT in graphifyy's optional extras but is required by _call_claude.
RUN pip install --no-cache-dir \
        "graphifyy==0.8.20" \
        "anthropic>=0.43.0"

# Working directory: the adapter bind-mounts a per-run tmpdir here.
WORKDIR /data

# Non-root user for safety.
RUN useradd -m -u 1000 graphify && chown graphify /data
USER graphify

# Default: keep the container alive so `docker exec` calls can reuse it.
CMD ["sleep", "infinity"]
