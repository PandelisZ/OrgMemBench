"""Mem0 Platform adapter for OrgMemBench.

Uses the **hosted** Mem0 Platform cloud service via the ``MemoryClient`` class
(distinct from the self-hosted ``Memory`` class used by ``Mem0Adapter``). The
client is lazy-imported so this module loads cleanly even when mem0ai isn't
installed.

The Mem0 Platform is a managed cloud service at https://api.mem0.ai. There is
no local process to run; a ``MEM0_API_KEY`` from https://app.mem0.ai is the
only requirement for live runs.

Capabilities declared:
- RECALL     — always; the platform performs hybrid retrieval (semantic vector
                embedding + BM25 keyword + entity matching) on every search call.
- PROVENANCE — partial; each search result returns a ``metadata`` dict containing
                the ``slot_id`` we stored at ingest time, which maps back to the
                originating Artifact. This satisfies the "cites source IDs"
                contract. The platform does not store a full audit chain or
                supersession graph.

Capabilities NOT declared:
- TEMPORAL   — the Mem0 Platform v3 REST API does expose a ``reference_date``
                parameter on search (documented as a "temporal anchor for
                time-aware queries"). However, the implementation is described
                as "temporal reasoning internally while preserving the normal
                search response shape" — it does NOT implement bi-temporal
                as_of semantics (valid_at vs ingested_at) and cannot answer
                "what was the state of knowledge on date X vs now". C3/C4
                questions are scored N/A for this adapter.
- SCOPE      — no role-relative knowledge isolation.
- NEGATIVE   — no calibrated abstention beyond normal platform behaviour.

Ingest mapping (Artifact → Mem0 Platform):
  • messages  = [{"role": "user", "content": artifact.text}]
  • user_id   = artifact.company          (namespace isolation per company)
  • metadata  = {slot_id, source_type, timestamp, author, thread_id, role}
    The platform returns this metadata dict in search results, so we can
    recover slot_id and populate cited_artifact_ids.
  • infer     = True (default; platform LLM extracts facts at ingest time)

Query: search top-k results for the question text scoped by company (user_id),
then stitch retrieved memory snippets into a plain-English answer. No additional
LLM call is made by the adapter.

Key differences from the OSS Mem0Adapter (mem0_adapter.py):
  - Uses ``MemoryClient`` (platform) instead of ``Memory`` (OSS).
  - No local Qdrant, no LLM config, no embedder config — all managed by Mem0.
  - Requires ``MEM0_API_KEY`` (from env); does NOT require ANTHROPIC_API_KEY or
    OPENAI_API_KEY (those are consumed server-side by the platform).
  - Namespace scoping: ``user_id`` passed directly to add()/search() (not inside
    a filters dict) for the Python client; the REST layer maps this correctly.
  - Add is async on the platform: returns an event_id + PENDING status. The
    Python client handles polling internally; the adapter treats the call as
    fire-and-return for throughput (same semantics as the OSS client's synchrony
    from the caller's perspective).
  - Search filters: the Python SDK accepts ``user_id`` as a top-level keyword
    argument to search(); the REST API requires it inside ``filters`` — the SDK
    handles the mapping transparently.

Limitations (critical for benchmark interpretation):
  - The Mem0 **platform service** is a moving target; there is no client-pinnable
    version for the server-side behaviour. ``_resolve_version()`` records the
    installed SDK version + a "(platform)" marker to make this visible in results.
    Benchmark reproducibility requires noting both the SDK version AND the run
    date, since the managed service may change without a version bump.
  - Ingest is LLM-heavy server-side. For large tiers this can be slow and the
    platform may rate-limit concurrent requests.
  - Provenance is partial: ``slot_id`` is recoverable from metadata but there is
    no supersession graph or full audit trail.
  - The ``reference_date`` temporal feature is probabilistic NL reasoning, not
    bi-temporal indexing; C3/C4 results are not meaningful for this adapter.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import TYPE_CHECKING, Any

from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter, pkg_version

logger = logging.getLogger("orgmembench.mem0_platform")

if TYPE_CHECKING:
    pass  # kept for optional future type stubs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_TOP_K = 10
_ENV_API_KEY = "MEM0_API_KEY"


class Mem0PlatformAdapter(MemoryAdapter):
    """OrgMemBench adapter wrapping the hosted Mem0 Platform MemoryClient."""

    name = "mem0-platform"
    capabilities: set[Capability] = {Capability.RECALL, Capability.PROVENANCE}

    # ------------------------------------------------------------------
    # Construction — MUST be free of side-effects and NOT import mem0
    # ------------------------------------------------------------------
    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        super().__init__(config=config, dry_run=dry_run)
        # _client is populated lazily on first _ingest / _query call.
        # Importantly, the API key is NOT read at construction — only at first
        # live use — so the adapter can be constructed and smoke-tested for free.
        self._client: Any = None
        # FRESH user_id PER ATTEMPT. The platform deletes asynchronously, so a
        # prior attempt's in-flight deletes can clobber a re-ingest on the same
        # user_id (this vaporized the first run's store). A run-unique namespace
        # means stale async deletes can never touch this run's data.
        # FRESH user_id per attempt by default. Override with MEM0_PIN_USER_ID to
        # re-query an EXISTING store (used with ORGMEMBENCH_REUSE_INGEST=1 to score
        # against a store whose async extraction has fully settled, bypassing a
        # fresh ingest+drain cycle).
        self._ns: str = (
            os.environ.get("MEM0_PIN_USER_ID", "").strip()
            or f"{self.scope}-{uuid.uuid4().hex[:8]}"
        )

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------
    def _resolve_version(self) -> str:
        """SDK version + a marker that the server-side service is unversioned."""
        sdk_ver = pkg_version("mem0ai")
        return f"{sdk_ver} (platform)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_client(self) -> Any:
        """Lazily construct and cache the Mem0 MemoryClient instance.

        The API key is read from the environment at this point (NOT in __init__),
        so construction remains free and side-effect-free.
        """
        if self._client is not None:
            return self._client

        try:
            from mem0 import MemoryClient  # lazy import — mem0ai need not be installed
        except ImportError as exc:
            raise RuntimeError(
                "mem0ai is not installed. Install it with: pip install mem0ai>=2.0.2\n"
                "Or: pip install 'orgmembench[mem0]'"
            ) from exc

        api_key = os.environ.get(_ENV_API_KEY, "").strip()
        if not api_key:
            raise RuntimeError(
                f"MEM0_API_KEY environment variable is not set. "
                f"Get a key from https://app.mem0.ai and export it as "
                f"MEM0_API_KEY before running a live benchmark."
            )

        self._client = MemoryClient(api_key=api_key)
        return self._client

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        t0 = time.time()
        client = self._get_client()

        n_stored = 0
        total_text_chars = 0

        for art in artifacts:
            # Build the message list MemoryClient expects.
            messages = [{"role": "user", "content": art.text}]

            # Pack all OrgMemBench metadata so we can recover slot_id in search.
            # The platform stores this dict verbatim and returns it in search
            # results under the "metadata" key.
            metadata: dict[str, Any] = {"slot_id": art.slot_id}
            if art.source_type:
                metadata["source_type"] = art.source_type
            if art.timestamp:
                metadata["timestamp"] = art.timestamp
            if art.author:
                metadata["author"] = art.author
            if art.thread_id:
                metadata["thread_id"] = art.thread_id
            if art.role:
                metadata["role"] = art.role

            # Platform add() is async server-side (returns event_id + PENDING).
            # The Python client surfaces this as a synchronous return; we treat
            # it as fire-and-return to match OSS client semantics.
            client.add(
                messages,
                user_id=self._ns,      # per-tier isolation + per-attempt unique
                metadata=metadata,
            )
            n_stored += 1
            total_text_chars += len(art.text)

        # Platform extraction is async — wait until it settles so the query
        # phase doesn't race a half-built memory set.
        settled = self._wait_until_settled()

        return IngestStats(
            n_artifacts=n_stored,                 # = add requests (mem0 metering)
            # Platform doesn't expose token counts; approximate from chars.
            tokens_stored=total_text_chars // 4,
            ingest_seconds=time.time() - t0,
            raw={"settled_memories": settled},
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        # as_of is intentionally ignored — the platform's reference_date is NL
        # temporal reasoning, not bi-temporal as_of indexing. The harness marks
        # C3/C4 questions N/A for this adapter.
        t0 = time.time()
        client = self._get_client()

        top_k: int = self.config.get("retrieval_top_k", _DEFAULT_TOP_K)

        # The Python SDK accepts user_id as a direct keyword arg; it maps to
        # filters={"user_id": ...} in the REST API v3 internally.
        # Mem0 Platform v3 search() requires the namespace inside `filters`
        # (a top-level user_id is rejected). Scope = per-tier isolation key.
        results = client.search(
            question.text,
            version="v2",
            filters={"user_id": self._ns},
            top_k=top_k,
        )

        # results shape: {"results": [{id, memory, score, metadata, categories,
        #                              created_at, updated_at, user_id}, ...]}
        hits = results.get("results", []) if isinstance(results, dict) else []

        # Recover cited artifact slot_ids from metadata we stored at ingest.
        cited_ids: list[str] = []
        snippets: list[str] = []
        for hit in hits:
            meta = hit.get("metadata") or {}
            slot_id = meta.get("slot_id")
            if slot_id and slot_id not in cited_ids:
                cited_ids.append(slot_id)
            memory_text = hit.get("memory", "")
            if memory_text:
                ts = meta.get("timestamp")
                snippets.append(f"[{ts}] {memory_text}" if ts else memory_text)

        # Platform is retrieval-only (self_answers=False): return retrieved
        # memories as context; the runner's basic answerer produces the answer.
        retrieved_context = "\n\n".join(snippets) if snippets else "No relevant evidence found."

        latency_ms = (time.time() - t0) * 1000.0

        return QueryResult(
            question_id=question.id,
            system=self.name,
            retrieved_context=retrieved_context,
            cited_artifact_ids=cited_ids,
            latency_ms=latency_ms,
            raw={"n_hits": len(hits), "hits": hits[:3]},  # top-3 for debugging
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    def _settled_count(self) -> int:
        try:
            r = self._get_client().get_all(version="v2", filters={"user_id": self._ns})
            items = r.get("results", r) if isinstance(r, dict) else r
            return len(items or [])
        except Exception:
            return -1

    def _probe_search_count(self, probe_query: str = "decision") -> int:
        """Run a real search and count results. The count is the signal the
        prior 2026-05-25 writeup identified as reliable: get_all() count
        plateaus on transient values (0 during async-extract warmup, 78 mid-
        delete-storm) but a search() that returns N results means N memories
        are actually searchable RIGHT NOW. A generic query word is used so
        the probe is corpus-agnostic."""
        # top_k must exceed the largest expected store, else the count CAPS at
        # top_k and the drain can't see growth past it (medium plateaued at the
        # old top_k=100 even as the store kept extracting). Env-overridable.
        import os
        probe_k = int(os.environ.get("MEM0_DRAIN_PROBE_TOPK", "2000"))
        try:
            r = self._get_client().search(
                query=probe_query,
                version="v2",
                filters={"user_id": self._ns},
                top_k=probe_k,
            )
            items = r.get("results", r) if isinstance(r, dict) else r
            return len(items or [])
        except Exception:
            return -1

    def _wait_until_settled(
        self,
        max_wait: int | None = None,
        interval: int | None = None,
        min_wait: int | None = None,
        require_nonzero_stable_checks: int | None = None,
    ) -> int:
        """Platform ingest is ASYNC (add() returns before server-side extraction
        finishes). Two failure modes the prior 2026-05-25 invalid run exposed:

          1. ``get_all`` count plateaus on transient values (0 during async-
             extract warmup, 78 mid-delete-storm). → use a probe SEARCH instead;
             only memories that are actually searchable count.
          2. The naive stability check returns on the first plateau, including
             a 0→0→0 plateau when extraction simply hasn't started yet. → require
             a NON-ZERO stable window AND a minimum total wait.

        Probe-search-based drain: poll every ``interval``s, look for ``stable``
        consecutive identical non-zero counts. Require at least ``min_wait`` s
        total. Returns the final settled count.

        2026-06-01 hardening (helix-MEDIUM premature-settle bug): like zep, mem0's
        server-side extraction proceeds in bursts. On medium the probe count
        climbed 43→88, paused ~40s (4 polls), and the drain SETTLED at 88 while
        extraction continued to 100+. A stability window alone is unsafe against
        pause-then-resume, so after apparent stability we do a CONFIRMATION HOLD
        and re-check; if it grew, the "stability" was a pause and we resume. Plus
        a bigger probe top_k (see _probe_search_count), higher min_wait, and a
        larger stable window. All knobs env-overridable (MEM0_DRAIN_*).

        A fully-settled store can also be re-queried via ORGMEMBENCH_REUSE_INGEST=1
        + MEM0_PIN_USER_ID; ALWAYS verify post-run that the live memory count
        matches the count at query time."""
        import os
        max_wait = max_wait if max_wait is not None else int(os.environ.get("MEM0_DRAIN_MAX_WAIT", "2400"))
        interval = interval if interval is not None else int(os.environ.get("MEM0_DRAIN_INTERVAL", "10"))
        min_wait = min_wait if min_wait is not None else int(os.environ.get("MEM0_DRAIN_MIN_WAIT", "120"))
        if require_nonzero_stable_checks is None:
            require_nonzero_stable_checks = int(os.environ.get("MEM0_DRAIN_STABLE", "8"))   # ~80s window
        confirm_hold = int(os.environ.get("MEM0_DRAIN_CONFIRM_HOLD", "120"))
        logger.info(
            "mem0-platform: drain begin (max_wait=%ss, interval=%ss, min_wait=%ss, "
            "stable=%s, confirm_hold=%ss)",
            max_wait, interval, min_wait, require_nonzero_stable_checks, confirm_hold,
        )
        prev, stable, waited = -1, 0, 0
        while waited < max_wait:
            n = self._probe_search_count()
            logger.info("mem0-platform: drain poll t=%ss probe_count=%s stable=%s",
                        waited, n, stable)
            if n > 0 and n == prev:
                stable += 1
                if stable >= require_nonzero_stable_checks and waited >= min_wait:
                    logger.info("mem0-platform: apparent settle at n=%s — confirmation hold %ss",
                                n, confirm_hold)
                    time.sleep(confirm_hold); waited += confirm_hold
                    n2 = self._probe_search_count()
                    if n2 == n:
                        logger.info("mem0-platform: drain SETTLED at n=%s (waited=%ss, confirmed)", n, waited)
                        return n
                    logger.info("mem0-platform: count grew %s->%s during hold — was a pause; resuming", n, n2)
                    prev, stable = n2, 0
                    continue
            else:
                stable = 0
            prev = n
            time.sleep(interval)
            waited += interval
        logger.warning("mem0-platform: drain TIMEOUT after %ss, last_count=%s", waited, prev)
        return max(prev, 0)

    def reset_scope(self) -> None:
        """Wipe this tier's memories. delete_users()/delete_all(user_id=) are
        silent no-ops on this SDK, so we enumerate and delete each id, looping to
        catch async-extraction stragglers, until empty and stable."""
        client = self._get_client()
        empties = 0
        for _ in range(30):
            try:
                r = client.get_all(version="v2", filters={"user_id": self._ns})
                items = r.get("results", r) if isinstance(r, dict) else r
                mids = [m["id"] for m in (items or []) if m.get("id")]
            except Exception:
                return  # scope_count() is the hard check
            if not mids:
                empties += 1
                if empties >= 3:
                    return
                time.sleep(4)
                continue
            empties = 0
            for mid in mids:
                try:
                    client.delete(mid)
                except Exception:
                    pass
            time.sleep(4)

    def scope_count(self) -> int:
        try:
            res = self._get_client().get_all(version="v2", filters={"user_id": self._ns})
            items = res.get("results", res) if isinstance(res, dict) else res
            return len(items or [])
        except Exception:
            return -1

    def teardown(self) -> None:
        """Release the MemoryClient instance (stateless HTTP client; no cleanup)."""
        self._client = None
