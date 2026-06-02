"""Free smoke tests for the Mem0 adapter.

Validates:
- The module imports cleanly without mem0ai installed.
- Mem0Adapter(dry_run=True) constructs with zero side-effects.
- name and capabilities are declared correctly.
- dry_run=True query returns the standard stub (no LLM, no network).
- version() returns something (either the installed version or "unknown").

MUST NOT: install mem0ai, hit any network, spend tokens, or touch
ORGMEMBENCH_DRY_RUN=0 paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ.setdefault("ORGMEMBENCH_DRY_RUN", "1")

from orgmembench.adapters.mem0_adapter import Mem0Adapter   # noqa: E402
from orgmembench.schemas import Capability, Question         # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter(**kwargs) -> Mem0Adapter:
    return Mem0Adapter(dry_run=True, **kwargs)


def _make_question() -> Question:
    return Question(
        id="q-smoke-001",
        company="acme",
        tier="small",
        category="C1",
        text="What was decided about the API versioning strategy?",
        ground_truth_answer={"answer": "use semver"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_import_without_mem0ai():
    """Module must be importable even when mem0ai is NOT installed."""
    # If we got here without ImportError, the test passes.
    import orgmembench.adapters.mem0_adapter  # noqa: F401
    assert True


def test_adapter_name():
    a = _make_adapter()
    assert a.name == "mem0"


def test_adapter_capabilities_include_recall():
    a = _make_adapter()
    assert Capability.RECALL in a.capabilities


def test_adapter_capabilities_include_provenance():
    a = _make_adapter()
    assert Capability.PROVENANCE in a.capabilities


def test_adapter_no_temporal_capability():
    """mem0 is vector-first; temporal/time-travel is NOT supported."""
    a = _make_adapter()
    assert Capability.TEMPORAL not in a.capabilities


def test_adapter_is_dry_run():
    a = _make_adapter()
    assert a.dry_run is True


def test_dry_run_query_returns_stub():
    a = _make_adapter()
    q = _make_question()
    result = a.query(q)
    # Base class dry-run stub
    assert result.dry_run is True
    assert "DRY_RUN" in result.answer_text
    assert result.question_id == q.id
    assert result.system == "mem0"


def test_dry_run_ingest_returns_stub():
    from orgmembench.schemas import Artifact
    a = _make_adapter()
    arts = [
        Artifact(
            slot_id="art-001",
            company="acme",
            source_type="slack_thread",
            text="We decided to use semver for our API.",
            timestamp="2024-03-15",
            author="Alice",
        )
    ]
    stats = a.ingest(arts)
    assert stats.n_artifacts == 1
    assert stats.raw.get("dry_run") is True


def test_version_resolves_without_error():
    """version() must not raise; returns installed version or 'unknown'."""
    a = _make_adapter()
    v = a.version()
    assert isinstance(v, str)
    assert len(v) > 0
    # Either the real version (e.g. "2.0.2") or "unknown" if not installed.
    print(f"  mem0 version: {v!r}")


def test_config_passthrough():
    """Custom config dict is stored and accessible."""
    cfg = {"llm_model": "claude-sonnet-4-6", "retrieval_top_k": 5}
    a = Mem0Adapter(config=cfg, dry_run=True)
    assert a.config["llm_model"] == "claude-sonnet-4-6"
    assert a.config["retrieval_top_k"] == 5


def test_no_mem0_instantiation_in_init():
    """__init__ must NOT instantiate the mem0 Memory object (lazy init)."""
    a = _make_adapter()
    # _mem should be None until _get_memory() is called.
    assert a._mem is None


def test_registered_in_registry():
    """Mem0Adapter must be discoverable via the registry when importable."""
    from orgmembench.adapters.registry import available
    adapters = available()
    # "mem0" appears in registry because mem0_adapter module imports cleanly.
    assert "mem0" in adapters, f"mem0 not in registry; got: {adapters}"


if __name__ == "__main__":
    tests = [
        test_import_without_mem0ai,
        test_adapter_name,
        test_adapter_capabilities_include_recall,
        test_adapter_capabilities_include_provenance,
        test_adapter_no_temporal_capability,
        test_adapter_is_dry_run,
        test_dry_run_query_returns_stub,
        test_dry_run_ingest_returns_stub,
        test_version_resolves_without_error,
        test_config_passthrough,
        test_no_mem0_instantiation_in_init,
        test_registered_in_registry,
    ]
    for fn in tests:
        print(f"  {fn.__name__} ...", end=" ")
        fn()
        print("PASS")
    print(f"\nAll {len(tests)} smoke tests PASS")
