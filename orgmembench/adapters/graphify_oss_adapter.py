"""graphify-oss adapter for OrgMemBench.

Wraps the public OSS upstream ``safishamsi/graphify`` (v8,
commit b07f0eb6a7d336142430a6c64ef23ae013255690).

## What graphify-oss is

graphify (``pip install graphifyy``) is a graph knowledge-base tool: it turns
any folder of documents (markdown, txt, rst, code, PDFs, etc.) into a
queryable knowledge graph stored in a ``graph.json`` file, then answers
questions via BFS/DFS graph traversal.

## Adapter design

**Ingest phase:**
  1. For each OrgMemBench Artifact, write a ``.md`` file to a per-scope
     working directory (``<workdir>/<scope>/corpus/``).  The file includes
     a YAML frontmatter block (slot_id, timestamp, author, source_type,
     thread_id) so that the extractor preserves attribution in the graph.
  2. After all artifact files are written, run one headless extraction pass:
     ``graphify extract <corpus_dir> --backend claude --out <workdir>/<scope>``
     This blocks until extraction completes (Claude LLM calls for semantic
     doc→graph extraction, then BFS/DFS clustering). SYNCHRONOUS -- no drain
     needed (see ``docs/writeups/ingest-settle.md``).

**Query phase:**
  ``graphify query "<question>" --graph <scope>/graphify-out/graph.json
    --budget <N>``
  Returns plain-text graph traversal output (BFS, depth 3, up to N tokens).
  Passed as ``retrieved_context`` to the neutral OrgMemBench answerer
  (this adapter sets ``self_answers = False``).

## LLM and embedding

- **LLM**: Anthropic Claude, defaulting to ``claude-sonnet-4-6`` (graphify's
  upstream default; no patch needed). Controlled by ``ANTHROPIC_API_KEY``.
- **Embeddings**: NONE. graphify uses pure graph traversal (BFS/DFS keyword
  scoring) for queries -- no vector DB, no embedding provider.

## Settle / async note

graphify's ``extract`` command is fully synchronous: it makes LLM calls to
build the graph and writes ``graph.json`` before returning. No background queue,
no settle drain needed.

## Docker

The adapter can run graphify either natively (if ``graphifyy`` is installed in
the host Python env) or inside a container via ``docker exec``:
  - ``config['docker_container']`` or env ``GRAPHIFY_OSS_DOCKER_CONTAINER``
    → use ``docker exec <container> graphify ...`` for process isolation.
  - Otherwise: run ``graphify`` from PATH.

Container: ``orgmembench-graphify-oss`` (see ``docker/graphify-oss/``).
The container has no HTTP API; it is kept alive with ``sleep infinity`` and
used via ``docker exec``.

## Capabilities

- RECALL: yes — graph traversal retrieves relevant nodes.
- PROVENANCE: no — graph traversal returns node/edge text, not slot citations.
- TEMPORAL: no — graphify has no bi-temporal model; ``as_of`` is ignored.
- SCOPE: no.
- NEGATIVE: no.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter

logger = logging.getLogger("orgmembench.adapter.graphify-oss")

# Default token budget for ``graphify query --budget``; covers enough graph
# context for the answerer without blowing the answerer's context window.
_DEFAULT_QUERY_BUDGET = 4000

# Subprocess timeout constants (seconds).
_EXTRACT_TIMEOUT_S = 7200.0   # 2h; extraction is LLM-heavy and scales with corpus
                              # size (121 small / 443 medium / large+). The small
                              # tier finishes in ~7 min; medium needs >30 min, so
                              # the old 1800s cap silently truncated medium runs.
# Parallel Claude extraction calls. Higher = faster extraction; capped to stay
# well under Anthropic rate limits. Overridable via GRAPHIFY_OSS_EXTRACT_CONCURRENCY.
_EXTRACT_CONCURRENCY = os.environ.get("GRAPHIFY_OSS_EXTRACT_CONCURRENCY", "8")
_QUERY_TIMEOUT_S = 120.0      # query is a local graph traversal — very fast

# Model env var that graphify reads for the claude backend (there is no
# GRAPHIFY_CLAUDE_MODEL; the claude backend has a hardcoded default of
# ``claude-sonnet-4-6``). We document this here for clarity.
_GRAPHIFY_CLAUDE_MODEL_NOTE = (
    "graphify's claude backend defaults to claude-sonnet-4-6; no override env var exists. "
    "If a future upstream version adds GRAPHIFY_CLAUDE_MODEL, set it in config['llm_model']."
)


class GraphifyOssAdapter(MemoryAdapter):
    """OrgMemBench adapter for safishamsi/graphify (public OSS, v8)."""

    name = "graphify-oss"
    capabilities: set[Capability] = {Capability.RECALL}
    self_answers = False   # use the neutral OrgMemBench answerer

    # ------------------------------------------------------------------
    # Construction — no network calls, no side-effects.
    # ------------------------------------------------------------------
    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        super().__init__(config=config, dry_run=dry_run)

        # Binary path (native) or empty (use default PATH).
        self._bin: str = (
            self.config.get("binary")
            or os.environ.get("GRAPHIFY_OSS_BIN")
            or "graphify"
        )

        # Optional Docker container name. When set, all CLI calls go through
        # ``docker exec <container> graphify ...``. This avoids polluting the
        # host Python env and matches how the other container-based adapters work.
        self._docker_container: str = (
            self.config.get("docker_container")
            or os.environ.get("GRAPHIFY_OSS_DOCKER_CONTAINER")
            or ""
        )

        # Per-scope working directory: stores corpus .md files + graphify-out/.
        # Defaults to a tmpdir managed by this adapter; override via config or env.
        self._workdir_override: str = (
            self.config.get("workdir")
            or os.environ.get("GRAPHIFY_OSS_WORKDIR")
            or ""
        )

        # Query budget (graph traversal token cap).
        self._query_budget: int = int(
            self.config.get("query_budget", os.environ.get("GRAPHIFY_OSS_QUERY_BUDGET", _DEFAULT_QUERY_BUDGET))
        )

        # Internal: the resolved per-scope workdir (set in _ingest).
        self._scope_workdir: Path | None = None
        # Managed tmpdir (set when we create our own; cleaned up in teardown).
        self._tmpdir: tempfile.TemporaryDirectory | None = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Version resolution
    # ------------------------------------------------------------------
    def _resolve_version(self) -> str:
        stdout, _, rc = self._run(["--version"], timeout=15.0)
        return stdout.strip() or "graphifyy (unknown)"

    # ------------------------------------------------------------------
    # Subprocess helper
    # ------------------------------------------------------------------
    def _run(
        self,
        args: list[str],
        *,
        stdin: str | None = None,
        timeout: float = _QUERY_TIMEOUT_S,
        cwd: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[str, str, int]:
        """Run [self._bin, *args] and return (stdout, stderr, returncode).

        When ``self._docker_container`` is set, routes through ``docker exec``
        with the Anthropic key injected via ``-e``. Working dir inside the
        container maps to ``/data`` (the bind-mount target).
        """
        if self._docker_container:
            cmd: list[str] = ["docker", "exec"]
            if stdin is not None:
                cmd.append("-i")
            for k in ("ANTHROPIC_API_KEY",):
                v = os.environ.get(k)
                if v:
                    cmd.extend(["-e", f"{k}={v}"])
            # Pass extra env vars (e.g. GRAPHIFY_OUT override).
            for k, v in (extra_env or {}).items():
                cmd.extend(["-e", f"{k}={v}"])
            # Working directory inside container.
            if cwd:
                cmd.extend(["-w", cwd])
            cmd.extend([self._docker_container, self._bin, *args])
            env = None
        else:
            cmd = [self._bin, *args]
            env = {**os.environ}
            if extra_env:
                env.update(extra_env)

        try:
            proc = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd if not self._docker_container else None,
                env=env,
            )
            return proc.stdout, proc.stderr, proc.returncode
        except FileNotFoundError:
            raise RuntimeError(
                f"graphify binary not found at {self._bin!r}. "
                "Install with: pip install 'graphifyy==0.8.20' anthropic\n"
                "Or set GRAPHIFY_OSS_BIN / config['binary'] to the full path.\n"
                "Or set GRAPHIFY_OSS_DOCKER_CONTAINER to use a pre-built container."
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "graphify command timed out after %.0fs: %s",
                timeout, " ".join(str(a) for a in cmd),
            )
            return "", "timeout", -1

    # ------------------------------------------------------------------
    # Working directory management
    # ------------------------------------------------------------------
    def _get_scope_workdir(self) -> Path:
        """Return (and create if needed) the per-scope working directory."""
        if self._scope_workdir is not None:
            return self._scope_workdir

        if self._workdir_override:
            base = Path(self._workdir_override)
        else:
            if self._tmpdir is None:
                self._tmpdir = tempfile.TemporaryDirectory(prefix="graphify-oss-")
            base = Path(self._tmpdir.name)

        # Namespace per scope so tiers don't contaminate each other.
        safe_scope = re.sub(r"[^\w\-]", "_", self.scope)
        wd = base / safe_scope
        wd.mkdir(parents=True, exist_ok=True)
        self._scope_workdir = wd
        return wd

    def _corpus_dir(self) -> Path:
        return self._get_scope_workdir() / "corpus"

    def _graph_path(self) -> Path:
        return self._get_scope_workdir() / "graphify-out" / "graph.json"

    # ------------------------------------------------------------------
    # Artifact → markdown file
    # ------------------------------------------------------------------
    @staticmethod
    def _artifact_to_md(art: Artifact) -> str:
        """Serialize an Artifact to YAML-frontmatter + body markdown.

        The frontmatter preserves attribution metadata so graphify's extractor
        can embed it as node attributes in the knowledge graph.
        """
        lines: list[str] = ["---"]
        lines.append(f"slot_id: {art.slot_id!r}")
        lines.append(f"source_type: {art.source_type!r}")
        if art.timestamp:
            lines.append(f"date: {art.timestamp!r}")
        if art.author:
            lines.append(f"author: {art.author!r}")
        if art.thread_id:
            lines.append(f"thread_id: {art.thread_id!r}")
        if art.role:
            lines.append(f"role: {art.role!r}")
        lines.append("---")
        lines.append("")
        lines.append(art.text)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # scope_count / reset_scope (for ensure_clean_scope)
    # ------------------------------------------------------------------
    def scope_count(self) -> int:
        """Count artifact files in the corpus dir. -1 if dir doesn't exist yet."""
        d = self._corpus_dir()
        if not d.exists():
            return 0
        return sum(1 for f in d.iterdir() if f.suffix == ".md")

    def reset_scope(self) -> None:
        """Wipe the per-scope workdir (corpus + graphify-out)."""
        wd = self._get_scope_workdir()
        import shutil
        if wd.exists():
            shutil.rmtree(str(wd))
        wd.mkdir(parents=True, exist_ok=True)
        logger.info("graphify-oss: reset scope %r (wiped %s)", self.scope, wd)

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        t0 = time.time()
        corpus_dir = self._corpus_dir()
        corpus_dir.mkdir(parents=True, exist_ok=True)

        # --- Phase 1: write artifact files ---
        n_written = 0
        total_chars = 0
        for art in artifacts:
            safe_name = re.sub(r"[^\w\-]", "_", art.slot_id)
            path = corpus_dir / f"{safe_name}.md"
            content = self._artifact_to_md(art)
            path.write_text(content, encoding="utf-8")
            n_written += 1
            total_chars += len(content)
            logger.debug("graphify-oss: wrote artifact %s -> %s", art.slot_id, path.name)

        logger.info(
            "graphify-oss: wrote %d artifact files to %s (%d chars total)",
            n_written, corpus_dir, total_chars,
        )

        # --- Phase 2: headless extraction ---
        # ``graphify extract <corpus_dir> --backend claude --out <scope_workdir>``
        # This is the LLM-heavy step: graphify reads each .md file, makes
        # Anthropic API calls to extract entities + relationships, builds the
        # graph, clusters it, and writes graphify-out/graph.json.
        # SYNCHRONOUS: blocks until graph.json is written.
        scope_workdir = self._get_scope_workdir()

        # Determine paths (native vs. docker container).
        if self._docker_container:
            # The docker-compose binds the host workdir (env GRAPHIFY_OSS_WORKDIR)
            # to /data inside the container. scope_workdir is one level deeper
            # (workdir / scope_name), so the in-container path needs the scope
            # subdir appended. Compute relpath against the bind-mount root so
            # the layout works no matter how the user set GRAPHIFY_OSS_WORKDIR.
            workdir_root = (
                Path(self._workdir_override).resolve()
                if self._workdir_override
                else Path(self._tmpdir.name).resolve()
            )
            try:
                rel = scope_workdir.resolve().relative_to(workdir_root)
            except ValueError:
                # scope_workdir is not under workdir_root — shouldn't happen, but
                # fall back to the bare scope name (matches _get_scope_workdir).
                rel = Path(re.sub(r"[^\w\-]", "_", self.scope))
            container_scope = f"/data/{rel.as_posix()}" if str(rel) != "." else "/data"
            container_corpus = f"{container_scope}/corpus"
            container_out = container_scope
            container_graph = f"{container_scope}/graphify-out/graph.json"
            extract_cwd = container_scope
        else:
            container_corpus = str(corpus_dir)
            container_out = str(scope_workdir)
            extract_cwd = str(scope_workdir)

        logger.info("graphify-oss: starting headless extraction (claude backend, may take several minutes)...")
        t_extract = time.time()

        stdout, stderr, rc = self._run(
            [
                "extract", container_corpus,
                "--backend", "claude",
                "--out", container_out,
                "--max-concurrency", _EXTRACT_CONCURRENCY,  # parallel LLM calls
            ],
            timeout=_EXTRACT_TIMEOUT_S,
            cwd=extract_cwd,
        )

        extract_seconds = time.time() - t_extract

        if rc != 0:
            logger.error(
                "graphify-oss: extract failed (rc=%d) after %.1fs.\nstdout: %s\nstderr: %s",
                rc, extract_seconds, stdout[-500:], stderr[-500:],
            )
        else:
            # Verify graph.json was written.
            graph_path = self._graph_path()
            if not graph_path.exists():
                logger.warning(
                    "graphify-oss: extract returned rc=0 but graph.json not found at %s",
                    graph_path,
                )
            else:
                graph_size = graph_path.stat().st_size
                logger.info(
                    "graphify-oss: extraction complete in %.1fs; graph.json = %d bytes",
                    extract_seconds, graph_size,
                )

        # Extract cost/usage from stdout if graphify prints it.
        extract_cost_usd = 0.0
        nodes_count = 0
        edges_count = 0
        try:
            # graphify extract prints summary lines like "N nodes, N edges"
            for line in (stdout + stderr).splitlines():
                if "nodes" in line and "edges" in line:
                    m = re.search(r"(\d+)\s+nodes", line)
                    if m:
                        nodes_count = int(m.group(1))
                    m = re.search(r"(\d+)\s+edges", line)
                    if m:
                        edges_count = int(m.group(1))
                if "cost" in line.lower() or "$" in line:
                    m = re.search(r"\$([0-9.]+)", line)
                    if m:
                        extract_cost_usd = float(m.group(1))
        except Exception:
            pass

        elapsed = time.time() - t0
        return IngestStats(
            n_artifacts=n_written,
            tokens_stored=total_chars // 4,  # approx; graphify doesn't expose stored token counts
            ingest_seconds=elapsed,
            raw={
                "extract_rc": rc,
                "extract_seconds": round(extract_seconds, 2),
                "extract_cost_usd": extract_cost_usd,
                "n_artifact_files": n_written,
                "total_chars": total_chars,
                "graph_nodes": nodes_count,
                "graph_edges": edges_count,
                "stdout_tail": stdout[-500:] if stdout else "",
                "stderr_tail": stderr[-500:] if stderr else "",
            },
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        """Run ``graphify query "<question>" --graph <path> --budget <N>``.

        as_of is silently ignored: graphify has no bi-temporal model. The
        adapter does NOT declare TEMPORAL capability, so the harness marks
        C3/C4 questions N/A rather than zero.
        """
        t0 = time.time()

        if as_of:
            logger.debug(
                "graphify-oss: as_of=%r ignored (no bi-temporal model)", as_of
            )

        # Determine graph path for native vs. docker.
        if self._docker_container:
            # Same scope-subdir nesting as extract — see _ingest for the rationale.
            workdir_root = (
                Path(self._workdir_override).resolve()
                if self._workdir_override
                else Path(self._tmpdir.name).resolve() if self._tmpdir else None
            )
            scope_workdir = self._get_scope_workdir()
            try:
                rel = scope_workdir.resolve().relative_to(workdir_root) if workdir_root else None
            except ValueError:
                rel = None
            if rel and str(rel) != ".":
                graph_path_str = f"/data/{rel.as_posix()}/graphify-out/graph.json"
            else:
                graph_path_str = "/data/graphify-out/graph.json"
        else:
            graph_path_str = str(self._graph_path())

        # Verify graph exists (native only; docker relies on the container).
        if not self._docker_container:
            gp = Path(graph_path_str)
            if not gp.exists():
                logger.error(
                    "graphify-oss: graph.json not found at %s — was ingest run?", gp
                )
                return QueryResult(
                    question_id=question.id,
                    system=self.name,
                    answer_text="[graphify-oss: graph.json not found — ingest may have failed]",
                    retrieved_context="",
                    answer_source="graphify-oss:error",
                    latency_ms=(time.time() - t0) * 1000.0,
                    raw={"error": "graph_not_found", "graph_path": graph_path_str},
                )

        stdout, stderr, rc = self._run(
            [
                "query", question.text,
                "--graph", graph_path_str,
                "--budget", str(self._query_budget),
            ],
            timeout=_QUERY_TIMEOUT_S,
        )

        latency_ms = (time.time() - t0) * 1000.0

        if rc != 0 or not stdout.strip():
            logger.warning(
                "graphify-oss: query failed (rc=%d) for %s: %s",
                rc, question.id, stderr.strip()[:300],
            )
            return QueryResult(
                question_id=question.id,
                system=self.name,
                answer_text="[graphify-oss: query returned no output]",
                retrieved_context="",
                answer_source="graphify-oss:error",
                latency_ms=latency_ms,
                raw={"rc": rc, "stderr": stderr[:500]},
            )

        retrieved_context = stdout.strip()
        logger.debug(
            "graphify-oss: query for %s returned %d chars of graph context",
            question.id, len(retrieved_context),
        )

        return QueryResult(
            question_id=question.id,
            system=self.name,
            answer_text="",            # filled by the neutral answerer
            retrieved_context=retrieved_context,
            answer_source="graphify-oss:graph-traversal",
            latency_ms=latency_ms,
            raw={
                "rc": rc,
                "context_chars": len(retrieved_context),
                "query_budget": self._query_budget,
            },
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    def teardown(self) -> None:
        """Clean up the managed tmpdir (if we created one)."""
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
                logger.info("graphify-oss: cleaned up tmpdir")
            except Exception as exc:
                logger.warning("graphify-oss: tmpdir cleanup failed: %s", exc)
            self._tmpdir = None
        self._scope_workdir = None
