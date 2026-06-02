"""Mem0 adapter for OrgMemBench.

Uses the open-source ``mem0ai`` SDK (self-hosted, NOT the Mem0 Platform cloud
service). The Memory class is lazy-imported so this module loads cleanly even
when mem0ai isn't installed — construction and dry-run stubs work with zero deps.

Capabilities declared:
- RECALL     — always; mem0 retrieves semantically similar memories via
                BM25 + vector hybrid search.
- PROVENANCE — partial; each search result returns a ``memory_id`` (the ``id``
                field) that can be mapped back to the slot_id stored in metadata
                at ingest time, so we can cite which artifact(s) a result came
                from. This satisfies the "cites source IDs" contract even though
                mem0 doesn't store a full audit chain.

Capabilities NOT declared:
- TEMPORAL   — mem0 is vector-first with no ``as_of`` / time-travel API; it
                records ``created_at`` / ``updated_at`` wall-clock timestamps but
                cannot answer "what was true on <date>". C3/C4 questions are
                scored N/A for this adapter.
- SCOPE      — no role-relative knowledge isolation.
- NEGATIVE   — no calibrated abstention beyond normal LLM behaviour.

Ingest mapping (Artifact → Mem0):
  • messages  = [{"role": "user", "content": artifact.text}]
  • user_id   = artifact.company          (namespace isolation per company)
  • metadata  = {slot_id, source_type, timestamp, author, thread_id, role}
    so we can recover slot_id from search results and populate cited_artifact_ids.

Query: search top-k results for the question text, then synthesise a plain-
English answer by concatenating the retrieved memory snippets (no extra LLM call
from the adapter itself — mem0's internal extraction + Anthropic LLM handles the
factual compression at ingest time; the adapter stitches retrieval output into a
readable answer string).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question
from .base import MemoryAdapter, pkg_version

if TYPE_CHECKING:
    pass  # kept for optional future type stubs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_TOP_K = 10
_NAMESPACE_KEY = "user_id"  # mem0 uses user_id for namespace isolation


class Mem0Adapter(MemoryAdapter):
    """OrgMemBench adapter wrapping the open-source mem0ai Memory class."""

    name = "mem0"
    capabilities: set[Capability] = {Capability.RECALL, Capability.PROVENANCE}

    # ------------------------------------------------------------------
    # Construction — MUST be free of side-effects and NOT import mem0
    # ------------------------------------------------------------------
    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        super().__init__(config=config, dry_run=dry_run)
        # _mem is populated lazily on first _ingest / _query call.
        self._mem: Any = None

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------
    def _resolve_version(self) -> str:
        return pkg_version("mem0ai")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_memory(self) -> Any:
        """Lazily construct and cache the mem0 Memory instance."""
        if self._mem is not None:
            return self._mem

        try:
            from mem0 import Memory  # lazy import — mem0ai need not be installed
        except ImportError as exc:
            raise RuntimeError(
                "mem0ai is not installed. Install it with: pip install mem0ai>=2.0.2\n"
                "Or: pip install 'orgmembench[mem0]'"
            ) from exc

        mem0_config = self._build_mem0_config()
        self._mem = Memory.from_config(mem0_config)
        return self._mem

    def _build_mem0_config(self) -> dict:
        """Build the mem0 config dict from our adapter config.

        Priority: values in self.config > reasonable defaults.
        The config/mem0.yaml file is the canonical reference for production
        configuration; self.config is populated from that file by the harness.
        """
        cfg = self.config

        # LLM — prefer Anthropic claude-sonnet-4-6 per project rules.
        llm_provider = cfg.get("llm_provider", "anthropic")
        llm_model = cfg.get("llm_model", "claude-sonnet-4-6")
        llm_max_tokens = cfg.get("llm_max_tokens", 2000)
        llm_temperature = cfg.get("llm_temperature", 0.1)

        # Embedder — no Anthropic embedder; use OpenAI text-embedding-3-small.
        # (mem0 requires an embedder; OpenAI is the most widely supported choice
        # that works alongside an Anthropic LLM.  OPENAI_API_KEY must be set.)
        embedder_provider = cfg.get("embedder_provider", "openai")
        embedder_model = cfg.get("embedder_model", "text-embedding-3-small")

        # Vector store — Qdrant (local mode by default, remote optional).
        vs_provider = cfg.get("vector_store_provider", "qdrant")
        vs_host = cfg.get("vector_store_host", "localhost")
        vs_port = cfg.get("vector_store_port", 6333)
        # Per-tier collection so tiers are physically isolated in Qdrant.
        base_collection = cfg.get("vector_store_collection", "orgmembench")
        safe_scope = "".join(c if c.isalnum() else "_" for c in self.scope)
        vs_collection = f"{base_collection}_{safe_scope}"
        vs_path = cfg.get("vector_store_path", None)  # if set, use local on-disk Qdrant

        vector_store_config: dict = {
            "collection_name": vs_collection,
        }
        if vs_path:
            # Pure local on-disk Qdrant (no Docker needed, but slower).
            vector_store_config["path"] = vs_path
        else:
            vector_store_config["host"] = vs_host
            vector_store_config["port"] = vs_port

        return {
            "llm": {
                "provider": llm_provider,
                "config": {
                    "model": llm_model,
                    "temperature": llm_temperature,
                    "max_tokens": llm_max_tokens,
                },
            },
            "embedder": {
                "provider": embedder_provider,
                "config": {
                    "model": embedder_model,
                },
            },
            "vector_store": {
                "provider": vs_provider,
                "config": vector_store_config,
            },
        }

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------
    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        t0 = time.time()
        mem = self._get_memory()

        n_stored = 0
        total_text_chars = 0

        for art in artifacts:
            # Build the message list mem0 expects.
            messages = [{"role": "user", "content": art.text}]

            # Pack all OrgMemBench metadata so we can recover slot_id in search.
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

            mem.add(
                messages,
                user_id=self.scope,    # per-tier isolation (company-tier)
                metadata=metadata,
            )
            n_stored += 1
            total_text_chars += len(art.text)

        return IngestStats(
            n_artifacts=n_stored,
            # mem0 doesn't expose token counts; approximate from chars.
            tokens_stored=total_text_chars // 4,
            ingest_seconds=time.time() - t0,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        # as_of is intentionally ignored — mem0 has no time-travel API.
        # The harness will mark C3/C4 questions N/A for this adapter.
        t0 = time.time()
        mem = self._get_memory()

        top_k: int = self.config.get("retrieval_top_k", _DEFAULT_TOP_K)

        # mem0ai 2.x rejects a top-level user_id in search() — must use filters.
        results = mem.search(
            question.text,
            filters={"user_id": self.scope},   # per-tier isolation (company-tier)
            top_k=top_k,
        )

        # results shape: {"results": [{"id": ..., "memory": ..., "metadata": {...}, ...}]}
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

        # mem0 is retrieval-only (self_answers=False): we return the retrieved
        # memories as context; the runner's basic answerer turns them into the
        # prose answer that gets judged.
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
    def reset_scope(self) -> None:
        """Drop this tier's Qdrant collections for a clean slate (local store)."""
        try:
            from qdrant_client import QdrantClient
            cfg = self.config
            base = cfg.get("vector_store_collection", "orgmembench")
            safe = "".join(c if c.isalnum() else "_" for c in self.scope)
            prefix = f"{base}_{safe}"
            qc = QdrantClient(host=cfg.get("vector_store_host", "localhost"),
                              port=cfg.get("vector_store_port", 6333))
            for col in qc.get_collections().collections:
                if col.name == prefix or col.name.startswith(prefix + "_"):
                    qc.delete_collection(col.name)
            self._mem = None  # rebuild so empty collections are recreated on ingest
        except Exception:
            pass  # best-effort; scope_count() is the hard emptiness check

    def scope_count(self) -> int:
        try:
            res = self._get_memory().get_all(filters={"user_id": self.scope})
            items = res.get("results", res) if isinstance(res, dict) else res
            return len(items or [])
        except Exception:
            return -1

    def teardown(self) -> None:
        """Release the mem0 Memory instance (no persistent cleanup needed)."""
        self._mem = None
