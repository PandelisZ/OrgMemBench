"""GBrain adapter for OrgMemBench.

GBrain (github.com/garrytan/gbrain) is a TypeScript/Bun CLI + MCP memory system
with hybrid search (BM25 + HNSW vector + knowledge graph) and LLM-synthesised
answers via ``gbrain think``.

Because gbrain has **no Python SDK**, this adapter shells out to the ``gbrain``
CLI binary via subprocess (stdlib only — no optional dependency to install).

VERSIONING NOTE — gbrain moves very fast (40+ releases in 2025 alone). The
``_resolve_version`` method captures both the CLI-reported version string
(``gbrain --version``) AND the installed commit SHA via ``gbrain version
--json``.  Pin both in ``config/gbrain.yaml``.  The harness will warn loudly if
the running version drifts from the pinned one.

Capabilities declared:
- RECALL      — always; ``gbrain think`` / ``gbrain search`` run hybrid
                BM25 + HNSW + knowledge-graph retrieval over every captured page.
- PROVENANCE  — yes; ``gbrain think --json`` returns a ``citations`` array of
                page slugs; we map slug→slot_id via the slug embedded at ingest
                time (``--slug orgmembench/<slot_id>``), so cited_artifact_ids is
                populated faithfully.

Capabilities NOT declared:
- TEMPORAL    — gbrain's ``--since``/``--until`` flags on ``think`` filter by
                document date but do **not** answer "what was the system's belief
                as of <date>" (no bi-temporal / valid-time query). Temporal
                window filtering is not the same as a true as-of audit.  C3/C4
                questions will be scored N/A for this adapter.
- SCOPE       — no role-relative knowledge isolation (no per-user namespacing
                analogous to mem0's user_id; sources are used but not per-role).
- NEGATIVE    — no calibrated abstention beyond the LLM's own behaviour.

Ingest mapping (Artifact → gbrain capture):
  ``gbrain capture --stdin --slug orgmembench/<slot_id> --type note --json``
  Stdin payload = frontmatter block + body text:

      ---
      title: <slot_id>
      source_type: <source_type>
      timestamp: <YYYY-MM-DD>
      author: <author>
      thread_id: <thread_id>
      orgmembench_slot_id: <slot_id>
      ---
      <artifact.text>

  gbrain merges YAML frontmatter into the page's metadata, making
  ``orgmembench_slot_id`` recoverable from citations at query time.

Query path:
  ``gbrain think --json [--model <model>] "<question.text>"``
  Parses the JSON response and extracts:
    - answer_text  ← ``answer``
    - cited_artifact_ids ← ``citations`` slugs, mapped back to slot_ids
    - raw          ← full JSON response

  ``gbrain think`` makes an LLM call (default provider depends on env keys; pass
  ``--model anthropic:claude-sonnet-4-6`` to steer to Claude Sonnet 4.6 when
  ANTHROPIC_API_KEY is set — see config/gbrain.yaml).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Any

from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter, cli_version

logger = logging.getLogger("orgmembench.adapter.gbrain")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Slug prefix used to namespace OrgMemBench pages inside gbrain so we can
# reliably reverse-map citation slugs → artifact slot_ids.
_SLUG_PREFIX = "orgmembench"

# Default model alias forwarded to ``gbrain think --model``; must match a model
# alias or full ID that gbrain accepts when ANTHROPIC_API_KEY is in env.
# Override via config key ``llm_model`` or env var GBRAIN_LLM_MODEL.
_DEFAULT_LLM_MODEL = "anthropic:claude-sonnet-4-6"

_DEFAULT_TOP_K = 10

# Subprocess timeout (seconds) for a single gbrain think/search call.
_THINK_TIMEOUT_S = 180
_CAPTURE_TIMEOUT_S = 180   # generous: big artifacts embed many chunks via ZeroEntropy


# ---------------------------------------------------------------------------
# Helper: build the slug for a given slot_id
# ---------------------------------------------------------------------------

def _slug_for(slot_id: str) -> str:
    """Deterministic gbrain slug for an OrgMemBench artifact."""
    # gbrain slugs are path-like lowercase strings; slot_ids already follow
    # a stable format (e.g. "helix-001-2024-07-15-slack") — keep them as-is
    # but ensure no whitespace.
    safe = slot_id.replace(" ", "-").lower()
    return f"{_SLUG_PREFIX}/{safe}"


def _slot_id_from_slug(slug: str) -> str | None:
    """Reverse the slug → slot_id mapping, or None if not an OrgMemBench slug."""
    prefix = f"{_SLUG_PREFIX}/"
    if slug.startswith(prefix):
        return slug[len(prefix):]
    return None


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class GBrainAdapter(MemoryAdapter):
    """OrgMemBench adapter that shells out to the ``gbrain`` CLI."""

    name = "gbrain"
    capabilities: set[Capability] = {Capability.RECALL, Capability.PROVENANCE}
    # gbrain ships its own prose answerer (`gbrain think`), so we use it — the
    # runner does NOT wrap gbrain with the basic answerer.
    self_answers = True

    # ------------------------------------------------------------------
    # Construction — MUST be free of side-effects and network calls.
    # The gbrain binary does NOT need to be present at import time.
    # ------------------------------------------------------------------
    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        super().__init__(config=config, dry_run=dry_run)
        # Binary path: config['binary'] > env GBRAIN_BIN > PATH default.
        self._bin: str = (
            self.config.get("binary")
            or os.environ.get("GBRAIN_BIN")
            or "gbrain"
        )
        # Docker container (set => all gbrain CLI calls go through `docker exec`).
        # Why: gbrain's PGLite lock (~/.gbrain/brain.pglite/.gbrain-lock) can
        # persist across process exits when run natively, causing back-to-back
        # invocations to hang waiting for the lock. Running in a container
        # gives clean lifecycle isolation per benchmark.
        self._docker_container: str = (
            self.config.get("docker_container")
            or os.environ.get("GBRAIN_DOCKER_CONTAINER")
            or ""
        )
        # LLM model forwarded to ``gbrain think --model``.
        self._llm_model: str = (
            self.config.get("llm_model")
            or os.environ.get("GBRAIN_LLM_MODEL")
            or _DEFAULT_LLM_MODEL
        )

    # ------------------------------------------------------------------
    # Version — capture both CLI version string and commit SHA.
    # gbrain updates very frequently; both must be recorded.
    # ------------------------------------------------------------------
    def _resolve_version(self) -> str:
        """Return 'gbrain <version> (commit <sha>)' if resolvable."""
        # 1. Human-readable version string (e.g. "gbrain 0.41.6.0").
        ver_raw = cli_version([self._bin, "--version"])

        # 2. Attempt to get the commit SHA from ``gbrain version --json``
        #    which (in recent releases) emits {"version": "...", "commit": "..."}.
        sha: str | None = None
        try:
            result = subprocess.run(
                [self._bin, "version", "--json"],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
            stdout = result.stdout.strip()
            if stdout:
                try:
                    data = json.loads(stdout)
                    if isinstance(data, dict):
                        sha = data.get("commit") or data.get("sha") or data.get("git_sha")
                except json.JSONDecodeError:
                    pass
        except (OSError, subprocess.SubprocessError):
            pass

        if sha:
            return f"{ver_raw} (commit {sha})"
        return ver_raw

    # ------------------------------------------------------------------
    # Internal: run a subprocess, returning (stdout, stderr, returncode).
    # Gracefully handles missing binary.
    # ------------------------------------------------------------------
    def _run(
        self,
        args: list[str],
        stdin: str | None = None,
        timeout: float = _CAPTURE_TIMEOUT_S,
    ) -> tuple[str, str, int]:
        """Run [self._bin, *args] returning (stdout, stderr, returncode).

        Raises RuntimeError if the binary is not found (gives install hint).
        """
        # gbrain refuses to run when MULTIPLE embedding providers are env-ready
        # (OPENAI + ZEROENTROPY both set) unless disambiguated. The brain is
        # configured for ZeroEntropy at init, so we strip OPENAI_API_KEY from the
        # subprocess env to keep gbrain unambiguously on ZeroEntropy + Anthropic.
        if self._docker_container:
            # Container has gbrain pre-installed at the pinned commit + a
            # clean HOME=/data, so locks can't leak between benchmark runs.
            # Inject env vars needed for ZE + Anthropic via -e flags.
            cmd: list[str] = ["docker", "exec"]
            if stdin is not None:
                cmd.append("-i")
            for k in ("ZEROENTROPY_API_KEY", "ANTHROPIC_API_KEY"):
                v = os.environ.get(k)
                if v:
                    cmd.extend(["-e", f"{k}={v}"])
            cmd.extend([self._docker_container, self._bin, *args])
            env = None  # docker exec ignores parent env unless passed via -e
        else:
            cmd = [self._bin, *args]
            env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        try:
            proc = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return proc.stdout, proc.stderr, proc.returncode
        except FileNotFoundError:
            raise RuntimeError(
                f"gbrain binary not found at {self._bin!r}. "
                "Install with: bun install -g "
                "github:garrytan/gbrain#3a2605e9a0b746a82ab42dd0177fc0f3a666a600\n"
                "Or set the GBRAIN_BIN env var / config['binary'] to the full path."
            )
        except subprocess.TimeoutExpired:
            logger.warning("gbrain command timed out after %.0fs: %s", timeout, " ".join(cmd))
            return "", "timeout", -1

    # ------------------------------------------------------------------
    # Build the capture payload (frontmatter + body) for an Artifact.
    # ------------------------------------------------------------------
    @staticmethod
    def _build_capture_payload(art: Artifact) -> str:
        """Return a YAML-frontmatter + body string for ``gbrain capture --stdin``."""
        lines: list[str] = ["---"]
        lines.append(f"title: {art.slot_id!r}")
        lines.append(f"orgmembench_slot_id: {art.slot_id!r}")
        if art.source_type:
            lines.append(f"source_type: {art.source_type!r}")
        if art.timestamp:
            # gbrain parses ISO date frontmatter for temporal-window filtering.
            lines.append(f"date: {art.timestamp}")
        if art.author:
            lines.append(f"author: {art.author!r}")
        if art.thread_id:
            lines.append(f"thread_id: {art.thread_id!r}")
        if art.role:
            lines.append(f"role: {art.role!r}")
        if art.company:
            lines.append(f"company: {art.company!r}")
        lines.append("---")
        lines.append("")
        lines.append(art.text)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        t0 = time.time()
        n_ok = 0
        n_fail = 0
        total_chars = 0

        # ── Phase 1: per-artifact captures, parallelized ─────────────
        # gbrain has no bulk-ingest path that fits our convention — its
        # `import <dir>` exists but uses filename-derived slugs that
        # don't match our `orgmembench/<slot_id>` convention. Instead we
        # parallelize the per-artifact `capture --stdin` loop. Postgres
        # backend (gbrain switched off PGLite to defeat single-writer-lock)
        # safely handles concurrent writes. Network round-trips to
        # ZeroEntropy for embeddings dominate per-call latency, so
        # threading gives ~Nx speedup.
        #
        # Knob: ``GBRAIN_INGEST_CONCURRENCY`` env (or config) sets the
        # worker count. Default 8 — measured on medium tier (443 artifacts):
        # sequential ran ~19s/artifact = ~140 min; at 8 workers expect
        # ~17-20 min.
        concurrency = int(
            self.config.get("ingest_concurrency")
            or os.environ.get("GBRAIN_INGEST_CONCURRENCY", 8)
        )
        logger.info(
            "gbrain: starting parallel capture (concurrency=%d, %d artifacts)",
            concurrency, len(artifacts),
        )

        def _capture_one(art: Artifact) -> tuple[Artifact, str, str, int, int]:
            slug = _slug_for(art.slot_id)
            payload = self._build_capture_payload(art)
            stdout, stderr, rc = self._run(
                ["capture", "--stdin", "--slug", slug, "--type", "note", "--json"],
                stdin=payload,
                timeout=_CAPTURE_TIMEOUT_S,
            )
            return art, stdout, stderr, rc, len(payload)

        completed = 0
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(_capture_one, art): art for art in artifacts}
            for fut in as_completed(futures):
                art, stdout, stderr, rc, payload_len = fut.result()
                total_chars += payload_len
                completed += 1
                if rc == 0:
                    n_ok += 1
                    logger.debug("captured %s", art.slot_id)
                else:
                    n_fail += 1
                    logger.warning(
                        "gbrain capture failed for %s (rc=%d): %s",
                        art.slot_id, rc, stderr.strip()[:200],
                    )
                # Periodic progress so long ingests aren't silent.
                if completed % 50 == 0 or completed == len(artifacts):
                    elapsed_so_far = time.time() - t0
                    rate = completed / elapsed_so_far if elapsed_so_far > 0 else 0
                    eta = (len(artifacts) - completed) / rate if rate > 0 else 0
                    logger.info(
                        "gbrain: captured %d/%d (%.1f art/s, eta %.0fs)",
                        completed, len(artifacts), rate, eta,
                    )

        if n_fail:
            logger.warning(
                "gbrain ingest: %d/%d artifacts failed to capture",
                n_fail, len(artifacts),
            )

        # ── Phase 2: extract all (links + timeline, idempotent) ─────
        # gbrain's `extract` builds the link graph and timeline index from
        # the captured pages — a predicate-classification / supersession-detection
        # refine sweep.
        logger.info("gbrain: extract all (links + timeline)")
        t_extract = time.time()
        extract_stdout, extract_stderr, extract_rc = self._run(
            ["extract", "all", "--json"], timeout=600.0,
        )
        if extract_rc != 0:
            logger.warning(
                "gbrain extract failed (rc=%d): %s",
                extract_rc, extract_stderr.strip()[:300],
            )
        extract_seconds = time.time() - t_extract

        # ── Phase 3: dream (overnight maintenance cycle) ────────────
        # gbrain's `dream` is the consolidation pass — recomputes salience,
        # detects anomalies, runs community/cluster refinement (an enrich +
        # post-enrich refine sweep).
        logger.info("gbrain: dream (overnight maintenance cycle)")
        t_dream = time.time()
        dream_stdout, dream_stderr, dream_rc = self._run(
            ["dream", "--json"], timeout=3600.0,
        )
        if dream_rc != 0:
            logger.warning(
                "gbrain dream failed (rc=%d): %s",
                dream_rc, dream_stderr.strip()[:300],
            )
        dream_seconds = time.time() - t_dream

        # Try to parse dream's JSON output for cost surfacing.
        dream_cost_usd = 0.0
        try:
            dj = json.loads(dream_stdout) if dream_stdout.strip() else {}
            dream_cost_usd = float(
                dj.get("total_cost_usd")
                or dj.get("cost_usd")
                or (dj.get("usage") or {}).get("cost_usd")
                or 0.0
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        elapsed = time.time() - t0

        return IngestStats(
            n_artifacts=n_ok,
            tokens_stored=total_chars // 4,  # gbrain doesn't expose stored token counts
            ingest_seconds=elapsed,
            raw={
                "n_ok": n_ok,
                "n_fail": n_fail,
                "extract_seconds": round(extract_seconds, 2),
                "extract_rc": extract_rc,
                "dream_seconds": round(dream_seconds, 2),
                "dream_rc": dream_rc,
                "dream_cost_usd": dream_cost_usd,
            },
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        """Run ``gbrain think --json [--model M] "<question>"`` and parse output."""
        t0 = time.time()

        args = ["think", "--json", "--model", self._llm_model]

        # gbrain think supports --since / --until for temporal window filtering.
        # This is NOT true bi-temporal as-of querying (we don't declare TEMPORAL),
        # but if an as_of date is supplied we pass it as --until as a best-effort
        # courtesy.  The harness marks C3/C4 N/A regardless.
        if as_of:
            args.extend(["--until", as_of])

        args.append(question.text)

        stdout, stderr, rc = self._run(args, timeout=_THINK_TIMEOUT_S)
        latency_ms = (time.time() - t0) * 1000.0

        if rc != 0 or not stdout.strip():
            logger.warning(
                "gbrain think failed (rc=%d) for question %s: %s",
                rc, question.id, stderr.strip()[:300],
            )
            return QueryResult(
                question_id=question.id,
                system=self.name,
                answer_text="[gbrain think returned no output]",
                answer_source="native:gbrain-think",
                latency_ms=latency_ms,
                raw={"rc": rc, "stderr": stderr[:500]},
            )

        # Parse JSON response.
        try:
            data: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("gbrain think JSON parse error: %s", exc)
            # Fall back to returning raw text as the answer.
            return QueryResult(
                question_id=question.id,
                system=self.name,
                answer_text=stdout.strip(),
                answer_source="native:gbrain-think",
                latency_ms=latency_ms,
                raw={"parse_error": str(exc), "raw_stdout": stdout[:2000]},
            )

        # Extract the answer text.
        answer_text: str = data.get("answer", "") or ""
        if not answer_text.strip():
            answer_text = "No answer produced."

        # Map citation slugs back to OrgMemBench slot_ids.
        cited_ids: list[str] = []
        citations = data.get("citations") or []
        if isinstance(citations, list):
            for cite in citations:
                # Citations may be plain slug strings or dicts with a "slug" key.
                if isinstance(cite, str):
                    slug = cite
                elif isinstance(cite, dict):
                    slug = cite.get("slug") or cite.get("page") or ""
                else:
                    slug = ""
                slot_id = _slot_id_from_slug(slug)
                if slot_id and slot_id not in cited_ids:
                    cited_ids.append(slot_id)

        return QueryResult(
            question_id=question.id,
            system=self.name,
            answer_text=answer_text,
            answer_source="native:gbrain-think",
            retrieved_context=f"(gbrain think synthesized its own answer from {data.get('pagesGathered', '?')} pages)",
            cited_artifact_ids=cited_ids,
            latency_ms=latency_ms,
            raw={
                "model_used": data.get("modelUsed"),
                "pages_gathered": data.get("pagesGathered"),
                "graph_hits": data.get("graphHits"),
                "gaps": data.get("gaps"),
                "warnings": data.get("warnings"),
                "n_citations": len(citations),
            },
        )
