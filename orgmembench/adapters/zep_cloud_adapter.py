"""Zep Cloud adapter — powered by the managed Zep Cloud API (getzep.com).

This is the HOSTED product, distinct from the self-hosted graphiti-core
adapter (``zep_adapter.py``).  Zep Cloud runs managed ingestion, entity
extraction, summarization, and fact-rating on top of Graphiti; the client
just sends data and queries through a REST API authenticated with ZEP_API_KEY.

Architecture
------------
Zep Cloud exposes two complementary ingest paths:

    memory.add(session_id, messages)  — chat-turn ingestion; Zep builds
        session summaries and distils facts automatically.

    graph.add(user_id, type, data)    — direct graph ingestion; accepts
        "text", "json", or "message" payloads without needing a chat session.

For OrgMemBench we use **graph.add** on the group graph (group_id scope) so
all artifacts land in a shared namespace rather than per-user silos.  The
group_id acts as our benchmark-run namespace, analogous to graphiti-core's
group_id parameter.

Point-in-time (as-of) retrieval
---------------------------------
graph.search accepts a ``search_filters`` argument (``SearchFilters`` object)
with 2-D date filter arrays.  Each DateFilter is:

    DateFilter(comparison_operator=">=", date="<ISO-8601-UTC>")

Outer lists are OR-ed; inner lists are AND-ed.  For an as-of valid-time slice
("what was true on date T"):

    valid_at   <= T          (fact had begun by T)
    invalid_at  > T  OR  IS NULL   (fact had not ended by T)

This is exactly the same bi-temporal contract as the graphiti-core adapter,
but expressed through the zep-cloud SDK types instead of graphiti_core types.
Note: temporal filters apply only to ``scope="edges"`` searches (Zep Cloud
docs state this explicitly).

LLM / embedding
----------------
All LLM extraction, embedding, and answer synthesis run inside Zep Cloud's
infrastructure.  The adapter itself does NOT need ANTHROPIC_API_KEY or
OPENAI_API_KEY.  Only ZEP_API_KEY is required at run time.

OrgMemBench capabilities declared
----------------------------------
    RECALL      — baseline retrieval (always true)
    TEMPORAL    — bi-temporal as-of queries via SearchFilters (valid_at / invalid_at)
    PROVENANCE  — returned edges carry episode_uuid fields that trace back to
                  the source episode; slot_id is embedded in the episode name
                  ("{source_type}::{slot_id}") so provenance can be recovered.

Versioning note
---------------
``pkg_version("zep-cloud")`` reports the installed client SDK version.  The
hosted Zep Cloud service is independently versioned and has no client-pinnable
counterpart; the config pin ("3.22.0") refers to the SDK, not the service.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter, pkg_version

if TYPE_CHECKING:
    pass  # kept for optional future type stubs

logger = logging.getLogger("orgmembench.zep_cloud")

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
_CAPABILITIES: set[Capability] = {
    Capability.RECALL,
    Capability.TEMPORAL,
    Capability.PROVENANCE,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso_date(ts: str | None) -> datetime | None:
    """Parse an ISO date string (YYYY-MM-DD or ISO-8601 datetime) to UTC datetime."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        pass
    try:
        dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _dt_to_iso(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC string (Zep Cloud requires timezone suffix)."""
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_as_of_filter(as_of_dt: datetime):
    """Return a zep-cloud SearchFilters for a point-in-time (as-of-valid-time) slice.

    Selects edges where:
        valid_at   <= as_of_dt    (fact had started by the query date)
        invalid_at  > as_of_dt  OR  invalid_at IS NULL
                                  (fact had not ended by the query date)

    Outer lists are OR-ed; inner lists are AND-ed (DNF).

    ``valid_at  <= T``   →  [[DateFilter("<=", T)]]
    ``invalid_at > T OR IS NULL``  →  [[DateFilter("IS NULL")],
                                       [DateFilter(">", T)]]

    Temporal filters apply only to ``scope="edges"`` searches (Zep Cloud docs).
    """
    # lazy import — zep-cloud not required at module load
    from zep_cloud.types import SearchFilters, DateFilter

    iso = _dt_to_iso(as_of_dt)

    valid_at_filter = [[DateFilter(comparison_operator="<=", date=iso)]]

    invalid_at_filter = [
        [DateFilter(comparison_operator="IS NULL")],
        [DateFilter(comparison_operator=">", date=iso)],
    ]

    return SearchFilters(
        valid_at=valid_at_filter,
        invalid_at=invalid_at_filter,
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class ZepCloudAdapter(MemoryAdapter):
    """OrgMemBench adapter backed by Zep Cloud (managed, hosted service).

    Construction is always free/side-effect-free.  All I/O is deferred to
    _ingest() / _query() which are guarded by the base-class dry-run gate.

    Required at run time (NOT at construct):
        ZEP_API_KEY  — Zep Cloud API key (from cloud.getzep.com dashboard).

    Config keys (passed as config dict or read from environment):
        zep_api_key    — overrides ZEP_API_KEY env var
        group_id       — namespace for this benchmark run (default "orgmembench")
        num_results    — edges to retrieve per query (default 20)
        reranker       — Zep Cloud reranker (default "rrf"; options: rrf, mmr,
                         node_distance, episode_mentions, cross_encoder)
    """

    name = "zep-cloud"
    capabilities = _CAPABILITIES

    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        super().__init__(config=config, dry_run=dry_run)
        # Lazy reference; populated on first real call
        self._client: Any = None
        # group_id namespaces the graph per tier so tiers never bleed together
        self._group_id: str = self.scope

    # --- versioning ---

    def _resolve_version(self) -> str:
        """Return the installed zep-cloud client SDK version + a 'cloud' marker.

        The hosted Zep Cloud service is versioned independently of the SDK and
        has no client-pinnable service version.  We record the SDK version for
        reproducibility; the marker 'cloud' distinguishes this from the OSS
        graphiti-core adapter which also uses the "zep" brand name.
        """
        sdk_ver = pkg_version("zep-cloud")
        # Append 'cloud' marker so the recorded version string is unambiguous:
        # e.g. "3.22.0+cloud" vs graphiti-core's "0.29.1".
        if sdk_ver != "unknown":
            return f"{sdk_ver}+cloud"
        return "unknown+cloud"

    # --- API key resolution ---

    def _api_key(self) -> str:
        key = self.config.get("zep_api_key") or os.environ.get("ZEP_API_KEY", "")
        if not key:
            raise RuntimeError(
                "ZEP_API_KEY is not set.  Export it in the environment or "
                "pass zep_api_key in the adapter config dict."
            )
        return key

    # --- Zep Cloud client initialisation ---

    def _get_client(self):
        """Lazily construct the Zep Cloud client (first real call only)."""
        if self._client is not None:
            return self._client

        from zep_cloud.client import Zep  # lazy import

        self._client = Zep(api_key=self._api_key())
        return self._client

    # --- ingest ---

    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        """Map each Artifact to a Zep Cloud graph episode and persist.

        Mapping:
            data         ← artifact.text  (free text, type="text")
            group_id     ← self._group_id (namespace isolation per run)
            episode_name ← "{source_type}::{slot_id}"
                           Stored in episode metadata so provenance can be
                           recovered at query time via the episode_uuid on edges.

        We use graph.add with group_id (not user_id) so all artifacts for one
        benchmark run land in a single shared graph namespace regardless of
        company or author.  This mirrors the graphiti-core adapter's group_id
        approach.

        reference_time: Zep Cloud's graph.add does not expose a direct
        reference_time parameter (unlike graphiti-core's add_episode).  We
        embed the timestamp in the text payload so Zep's LLM extractor can
        pick it up when it parses the episode.
        """
        client = self._get_client()

        # zep-cloud 3.22 uses graph_id (not group_id) and the graph must exist
        # before graph.add. Create it (idempotent: ignore "already exists").
        # NB: reset_scope's graph.delete returns before propagation completes;
        # if create races a still-arriving delete the graph ends up gone and
        # every subsequent add 404s (see 2026-05-26 helix-small rerun). Poll
        # graph.get until it confirms the graph is live before ingesting.
        try:
            client.graph.create(graph_id=self._group_id, name=self._group_id)
        except Exception as exc:
            logger.debug("zep-cloud graph.create(%s): %s", self._group_id, exc)

        for attempt in range(10):
            try:
                client.graph.get(graph_id=self._group_id)
                break
            except Exception as exc:
                if attempt == 9:
                    logger.warning(
                        "zep-cloud graph.get(%s) still failing after 10 retries: %s",
                        self._group_id, exc,
                    )
                # Re-issue create — a racing delete may have eaten the first one.
                try:
                    client.graph.create(graph_id=self._group_id, name=self._group_id)
                except Exception:
                    pass
                time.sleep(1.0)

        t0 = time.time()
        n_ok = 0

        for art in artifacts:
            # Build the episode text, optionally prepending the timestamp so
            # Zep's extractor can anchor facts to the correct valid_at date.
            ts_prefix = f"[Date: {art.timestamp}] " if art.timestamp else ""
            meta_header = (
                f"Source: {art.source_type}"
                + (f" | Author: {art.author}" if art.author else "")
                + (f" | Thread: {art.thread_id}" if art.thread_id else "")
                + (f" | Company: {art.company}" if art.company else "")
            )
            episode_text = f"{ts_prefix}{meta_header}\n\n{art.text}"

            # Zep Cloud's FREE plan rate-limits ingest aggressively (~5 req per
            # 6s window with Retry-After: 6 on 429s). Honor the Retry-After header
            # via bounded retry — silently swallowing 429s produces a partial
            # ingest, which the prior 2026-05-26 helix-small run hit hard.
            for attempt in range(8):
                try:
                    client.graph.add(
                        graph_id=self._group_id,
                        type="text",
                        data=episode_text,
                    )
                    n_ok += 1
                    break
                except Exception as exc:
                    # Detect rate-limit 429: zep-cloud SDK wraps the HTTP error
                    # but its string repr usually includes 'status_code: 429'
                    # and a 'retry-after' header value we can pull out.
                    s = str(exc)
                    if "status_code: 429" in s or "429 Too Many Requests" in s:
                        # Pull retry-after from the error string if present;
                        # default to 6s which matches FREE plan refill window.
                        m = re.search(r"'retry-after': '(\d+)'", s)
                        wait = int(m.group(1)) if m else 6
                        # Exponential backoff multiplier capped at 4x
                        wait = min(wait * (2 ** min(attempt, 2)), 60)
                        logger.info(
                            "zep-cloud rate-limited on %s (attempt %d/8), sleeping %ss",
                            art.slot_id, attempt + 1, wait,
                        )
                        time.sleep(wait)
                        continue
                    logger.warning("zep-cloud ingest error for %s: %s", art.slot_id, exc)
                    break
            else:
                logger.warning("zep-cloud gave up on %s after 8 rate-limit retries", art.slot_id)

        # Zep builds the graph asynchronously — wait until it settles so the
        # query phase sees the full graph, not a half-built one.
        settled = self._wait_until_settled()

        return IngestStats(
            n_artifacts=n_ok,                       # = episodes (zep metering)
            ingest_seconds=time.time() - t0,
            raw={"graph_id": self._group_id, "failed": len(artifacts) - n_ok,
                 "settled_edge_count": settled},
        )

    # --- query ---

    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        """Search the Zep Cloud graph for edges relevant to *question*.

        When *as_of* is provided, constructs a SearchFilters object restricting
        results to edges valid on that date:
            valid_at   <= T  AND  (invalid_at > T  OR  invalid_at IS NULL)

        Temporal filters apply only to scope="edges" (Zep Cloud constraint).

        Answer synthesis: the top-k edge facts are concatenated as context;
        graph.search returns a ``context`` string (pre-synthesized) that we
        use directly when available, falling back to manual fact concatenation.

        Provenance: returned edges carry ``uuid_`` (edge UUID) and ``episodes``
        (list of episode UUIDs that produced the edge).  We record episode UUIDs
        in ``raw`` for downstream provenance reconstruction.  Direct slot_id
        back-mapping is not possible without a separate episode lookup, so
        ``cited_artifact_ids`` is left empty (the episode metadata lookup would
        require an extra API call per edge and is deferred to a future enhancement).
        """
        t0 = time.time()
        client = self._get_client()

        as_of_dt = _parse_iso_date(as_of) if as_of else None
        search_filter = _build_as_of_filter(as_of_dt) if as_of_dt else None

        num_results: int = self.config.get("num_results", 20)
        reranker: str = self.config.get("reranker", "rrf")

        try:
            # ALWAYS scope="edges" — it returns the raw relevant facts. (The old
            # scope="auto" returned a synthesized context block that, on small,
            # missed the facts entirely while scope="edges" surfaces them — see
            # docs/writeups/zep-cloud.md. scope="edges" also carries the temporal
            # filter for as_of questions.)
            scope = "edges"
            results = client.graph.search(
                graph_id=self._group_id,
                query=question.text,
                scope=scope,
                limit=min(num_results, 50),  # Zep Cloud caps at 50
                reranker=reranker,
                **({"search_filters": search_filter} if search_filter else {}),
            )
        except Exception as exc:
            logger.warning("zep-cloud search error: %s", exc)
            results = None

        latency_ms = (time.time() - t0) * 1000.0

        if results is None or (
            not getattr(results, "edges", None)
            and not getattr(results, "context", None)
        ):
            return QueryResult(
                question_id=question.id,
                system=self.name,
                retrieved_context="No relevant evidence found in the knowledge graph.",
                latency_ms=latency_ms,
            )

        # Use Zep's pre-synthesized context string if available
        context_str: str | None = getattr(results, "context", None)

        # Collect facts and episode UUIDs from returned edges for provenance
        facts: list[str] = []
        episode_uuids: list[str] = []

        edges = getattr(results, "edges", None) or []
        for edge in edges:
            if hasattr(edge, "fact") and edge.fact:
                facts.append(edge.fact)
            # episode provenance
            if hasattr(edge, "episodes") and edge.episodes:
                episode_uuids.extend(edge.episodes)
            # some SDK versions surface episode_uuid directly on the edge
            elif hasattr(edge, "episode_uuid") and edge.episode_uuid:
                episode_uuids.append(edge.episode_uuid)

        # zep-cloud is retrieval-only here (self_answers=False): return Zep's
        # context block / facts as retrieved context; the runner's basic
        # answerer turns it into the judged prose answer.
        if context_str and context_str.strip():
            retrieved_context = context_str.strip()
        elif facts:
            fact_block = "\n".join(f"- {f}" for f in facts[:num_results])
            preamble = f"Relevant facts from the knowledge graph"
            if as_of:
                preamble += f" (as of {as_of})"
            retrieved_context = f"{preamble}:\n{fact_block}"
        else:
            retrieved_context = "No relevant evidence found in the knowledge graph."

        return QueryResult(
            question_id=question.id,
            system=self.name,
            retrieved_context=retrieved_context,
            cited_artifact_ids=[],    # episode lookup deferred; see docstring
            latency_ms=latency_ms,
            raw={
                "n_edges": len(edges),
                "episode_uuids": list(dict.fromkeys(episode_uuids)),
                "as_of": as_of,
                "group_id": self._group_id,
                "scope": scope,
                "reranker": reranker,
            },
        )

    # --- cleanup ---

    def _edge_count(self) -> int:
        """Real edge count via graph.edge.get_by_graph_id (NOT graph.search,
        which caps at ~50 and gave a false 'settled' signal). Used by the drain
        to detect when async graph-building has actually finished."""
        try:
            eg = self._get_client().graph.edge.get_by_graph_id(
                graph_id=self._group_id, limit=1000)
            return len(eg if isinstance(eg, list) else (getattr(eg, "edges", eg) or []))
        except Exception:
            return -1

    def _wait_until_settled(self, max_wait: int | None = None, interval: int | None = None,
                            min_wait: int | None = None) -> int:
        """Zep graph-building is ASYNC — graph.add returns before episodes are
        processed into edges, and building continues for minutes.

        2026-06-01 hardening (after the helix-MEDIUM premature-settle bug): the
        edge count does NOT grow monotonically — server-side extraction proceeds
        in BURSTS with multi-minute PAUSES. On medium the count plateaued at 368
        for ~75s (4 polls) so the old "stable for N polls" drain SETTLED there
        and queried a 37%-built graph; the graph later finished at 1000+ edges.
        A stability window alone is fundamentally unsafe against pause-then-resume.

        Fix: after the count looks stable, do a CONFIRMATION HOLD — sleep a long
        window and re-check. If it grew during the hold, that "stability" was a
        mid-build pause: reset and keep draining. Only settle when the count
        survives the hold unchanged. Combined with a higher min_wait and a larger
        stability window. All knobs are env-overridable (ZEP_DRAIN_*).

        NOTE: a fully-settled store can also be re-queried directly via
        ORGMEMBENCH_REUSE_INGEST=1 (skips ingest+drain) — preferred when a prior
        run already built the graph. ALWAYS verify post-run that the live edge
        count matches the count at query time."""
        import os
        max_wait = max_wait if max_wait is not None else int(os.environ.get("ZEP_DRAIN_MAX_WAIT", "3600"))
        interval = interval if interval is not None else int(os.environ.get("ZEP_DRAIN_INTERVAL", "15"))
        min_wait = min_wait if min_wait is not None else int(os.environ.get("ZEP_DRAIN_MIN_WAIT", "120"))
        stable_needed = int(os.environ.get("ZEP_DRAIN_STABLE", "6"))         # ~90s window
        confirm_hold = int(os.environ.get("ZEP_DRAIN_CONFIRM_HOLD", "120"))  # re-check after this
        logger.info("zep-cloud: drain begin (max_wait=%ss, interval=%ss, min_wait=%ss, "
                    "stable=%s, confirm_hold=%ss)",
                    max_wait, interval, min_wait, stable_needed, confirm_hold)
        prev, stable, waited = -1, 0, 0
        while waited < max_wait:
            n = self._edge_count()
            logger.info("zep-cloud: drain poll t=%ss edge_count=%s stable=%s",
                        waited, n, stable)
            if waited >= min_wait and n >= 0 and n == prev:
                stable += 1
                if stable >= stable_needed:
                    # Confirmation hold: re-check after a long pause to defeat
                    # the burst-pause-burst pattern.
                    logger.info("zep-cloud: apparent settle at n=%s — confirmation hold %ss",
                                n, confirm_hold)
                    time.sleep(confirm_hold); waited += confirm_hold
                    n2 = self._edge_count()
                    if n2 == n:
                        logger.info("zep-cloud: drain SETTLED at n=%s (waited=%ss, confirmed)", n, waited)
                        return n
                    logger.info("zep-cloud: count grew %s->%s during hold — was a pause; resuming drain", n, n2)
                    prev, stable = n2, 0
                    continue
            else:
                stable = 0
            prev = n
            time.sleep(interval)
            waited += interval
        logger.warning("zep-cloud: drain TIMEOUT after %ss, last_count=%s", waited, prev)
        return prev

    def scope_count(self) -> int:
        """Count edges in this tier's graph. After reset_scope() the graph is
        deleted, so search raises -> -1 (treated as 'cannot verify', which is
        fine since we just wiped it)."""
        return self._edge_count()

    def reset_scope(self) -> None:
        """Delete this tier's entire graph (zep-cloud 3.22 graph.delete). Ingest
        re-creates it via graph.create."""
        try:
            self._get_client().graph.delete(graph_id=self._group_id)
        except Exception as exc:
            logger.debug("zep-cloud graph.delete(%s): %s", self._group_id, exc)

    def teardown(self) -> None:
        """Release the Zep Cloud HTTP client (no persistent connections to close)."""
        self._client = None
