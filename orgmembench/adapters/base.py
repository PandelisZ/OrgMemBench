"""The adapter contract every memory system implements.

A subclass declares ``name`` + ``capabilities`` and implements ``_ingest`` /
``_query`` / ``_resolve_version``. The base class enforces three cross-cutting
concerns so every system behaves identically:

1. **Dry-run safety.** Public ``ingest`` / ``query`` short-circuit to stubs when
   dry-run is on (the default), so the whole pipeline runs for free and no
   adapter can accidentally spend tokens or hit a live service.
2. **Versioning.** ``version()`` resolves the system's *runtime* version
   (installed package / CLI / git commit); ``config['version']`` pins the
   expected version; ``check_version()`` warns on drift. Recorded into results
   for reproducibility (gbrain in particular moves fast).
3. **Timing.** Latency is measured around ``_query`` even if the adapter forgets.

Subclasses must NOT spend tokens or hit external services from ``__init__`` —
construction must be free so the harness can be smoke-tested in dry-run.
"""

from __future__ import annotations

import importlib.metadata
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..config import dry_run as _global_dry_run
from ..schemas import Artifact, Capability, IngestStats, QueryResult, Question

logger = logging.getLogger("orgmembench.adapter")


def pkg_version(dist_name: str) -> str:
    """Installed distribution version, or 'unknown'."""
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def cli_version(cmd: list[str], timeout: float = 10.0) -> str:
    """Run a CLI version command and return its trimmed stdout, or 'unknown'."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or out.stderr).strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


class MemoryAdapter(ABC):
    name: str = "base"
    capabilities: set[Capability] = {Capability.RECALL}

    # Does this system produce its OWN final prose answer (so the runner must
    # NOT apply the basic answerer)? True for systems that ship an answerer
    # (e.g. gbrain `think`). False for pure retrieval systems (mem0,
    # mem0-platform, zep-cloud, graphiti) — the runner wraps those with the
    # neutral basic answerer over ``retrieved_context``. See
    # orgmembench/answerer.py.
    self_answers: bool = False

    def __init__(self, config: dict | None = None, dry_run: bool | None = None) -> None:
        self.config = dict(config or {})
        self.dry_run = _global_dry_run() if dry_run is None else dry_run
        self.pinned_version: str | None = self.config.get("version")
        self._resolved_version: str | None = None
        # Per-run isolation key, e.g. "helix-small". The runner injects this
        # (company + tier) so EVERY system stores/queries each tier under a
        # DISTINCT user/namespace/group/store and tiers never cross-contaminate.
        # Falls back to namespace/group_id (tests) then a constant.
        self.scope: str = (
            self.config.get("scope")
            or self.config.get("namespace")
            or self.config.get("group_id")
            or "orgmembench"
        )

    # --- versioning ---
    def version(self) -> str:
        """Resolved runtime version (cached). 'unknown' if not determinable."""
        if self._resolved_version is None:
            try:
                self._resolved_version = self._resolve_version()
            except Exception as exc:  # never let version resolution break a run
                logger.warning("%s: version resolution failed: %s", self.name, exc)
                self._resolved_version = "unknown"
        return self._resolved_version

    def _resolve_version(self) -> str:
        return "unknown"

    def check_version(self) -> None:
        """Warn loudly if the running version differs from the pinned one.

        Skips when the runtime version is unresolved ("unknown…", e.g. the SDK
        isn't installed yet / dry-run) — that's not drift, just not-yet-known.
        """
        resolved = self.version()
        if not self.pinned_version or "unknown" in resolved.lower():
            return
        if resolved != self.pinned_version:
            logger.warning(
                "%s VERSION DRIFT: pinned=%s but running=%s — results may not be "
                "comparable to the pinned config.",
                self.name, self.pinned_version, resolved,
            )

    # --- capabilities ---
    def supports(self, cap: Capability) -> bool:
        return cap in self.capabilities

    # --- ingest (dry-run wrapped) ---
    def ingest(self, artifacts: Iterable[Artifact]) -> IngestStats:
        if self.dry_run:
            n = sum(1 for _ in artifacts)
            return IngestStats(n_artifacts=n, raw={"dry_run": True})
        return self._ingest(list(artifacts))

    # --- query (dry-run wrapped + timed) ---
    def query(self, question: Question, as_of: str | None = None) -> QueryResult:
        if self.dry_run:
            return QueryResult(
                question_id=question.id, system=self.name,
                answer_text="[DRY_RUN] no answer produced",
                retrieved_context="[DRY_RUN] no retrieval performed",
                answer_source="dry-run", dry_run=True,
            )
        t0 = time.time()
        qr = self._query(question, as_of)
        # backfill identity + latency the adapter may have left unset
        qr.question_id = qr.question_id or question.id
        qr.system = qr.system or self.name
        if not qr.latency_ms:
            qr.latency_ms = (time.time() - t0) * 1000.0
        return qr

    # --- pre-ingest scope hygiene -------------------------------------------
    # The runner calls ensure_clean_scope() before ingesting a tier, so we
    # NEVER ingest on top of stale data (which would contaminate the tier and
    # waste hosted free-tier quota). OSS/local stores get wiped; hosted stores
    # are checked (and cleared where the API allows).
    def scope_count(self) -> int:
        """Items currently stored under self.scope. -1 if not determinable."""
        return -1

    def reset_scope(self) -> None:
        """Best-effort wipe of self.scope's data (OSS local / hosted delete).
        Default no-op (e.g. fresh per-instance stores)."""
        return

    def ensure_clean_scope(self) -> None:
        """Reset (where possible) then verify the scope is empty before ingest.

        Raises if the scope is still non-empty (refuse to ingest on top of it).
        Logs a warning if emptiness cannot be verified (count unknown).
        """
        if self.dry_run:
            return
        self.reset_scope()
        n = self.scope_count()
        if n > 0:
            raise RuntimeError(
                f"{self.name}: scope {self.scope!r} still holds {n} item(s) after reset — "
                "refusing to ingest on top of existing data (tier contamination risk). "
                "Clear it manually and retry."
            )
        if n < 0:
            logger.warning("%s: could not verify scope %r is empty before ingest",
                           self.name, self.scope)
        else:
            logger.info("%s: scope %r verified empty (0 items) before ingest",
                        self.name, self.scope)

    # --- subclass surface ---
    @abstractmethod
    def _ingest(self, artifacts: list[Artifact]) -> IngestStats: ...

    @abstractmethod
    def _query(self, question: Question, as_of: str | None) -> QueryResult: ...

    # optional cleanup
    def teardown(self) -> None:
        pass
