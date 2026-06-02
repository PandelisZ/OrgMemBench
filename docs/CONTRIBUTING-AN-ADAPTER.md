# Contributing an adapter

Adding a memory system to OrgMemBench = writing one adapter against a small
contract. The harness handles loading, normalization, judging, metrics, and the
leaderboard; your adapter just maps the corpus into your system and answers
questions out of it.

## The contract

Subclass `orgmembench.adapters.base.MemoryAdapter` and implement four things:

```python
from orgmembench.adapters.base import MemoryAdapter, pkg_version
from orgmembench.schemas import Artifact, Capability, IngestStats, QueryResult, Question

class MySystemAdapter(MemoryAdapter):
    name = "mysystem"
    capabilities = {Capability.RECALL}          # add TEMPORAL/PROVENANCE/SCOPE/NEGATIVE if true

    def _resolve_version(self) -> str:
        return pkg_version("mysystem-sdk")        # or CLI --version / git commit

    def _ingest(self, artifacts: list[Artifact]) -> IngestStats:
        # map each Artifact (text, timestamp, author, source_type, thread_id)
        # into your system's native ingest; return counts/timing.
        ...

    def _query(self, question: Question, as_of: str | None) -> QueryResult:
        # retrieve + synthesize an answer; honor as_of if you declared TEMPORAL.
        return QueryResult(question_id=question.id, system=self.name,
                           answer_text=..., cited_artifact_ids=[...])
```

Then register it in `orgmembench/adapters/registry.py`.

## Rules that keep the comparison fair + safe

1. **Declare capabilities honestly.** A category that requires a capability you
   don't declare is reported **N/A** for you — not scored zero. Don't claim
   `TEMPORAL` unless you genuinely answer "as of date" queries.
2. **Pin + report your version.** `_resolve_version()` must return the real
   runtime version; pin the expected version in `config/<name>.yaml`. The base
   class warns on drift. (Fast-moving systems: pin the commit too.)
3. **Vendor-recommended config.** Run on your recommended settings and commit
   them in `config/<name>.yaml`. An unfair config invalidates the result.
4. **Construction is free.** `__init__` must not call the system, spend tokens,
   or require network. Lazy-import your SDK inside the methods so the module
   imports even when the SDK isn't installed.
5. **Dry-run is automatic.** The base class short-circuits `ingest`/`query` to
   stubs when `ORGMEMBENCH_DRY_RUN` is on (the default) — you only implement the
   real `_ingest`/`_query`.

## Files to add

- `orgmembench/adapters/<name>_adapter.py` — the adapter.
- `config/<name>.yaml` — pinned version + vendor-recommended settings.
- `docker/<name>.md` — how to stand the system up + which keys/services it needs.
- `tests/test_<name>_smoke.py` — a free smoke test (import + dry-run construct).

## Verify (free)

```bash
PYTHONPATH=. python -c "from orgmembench.adapters.<name>_adapter import MySystemAdapter; \
  a=MySystemAdapter(dry_run=True); print(a.name, a.capabilities, a.version())"
PYTHONPATH=. python tests/test_<name>_smoke.py
```
