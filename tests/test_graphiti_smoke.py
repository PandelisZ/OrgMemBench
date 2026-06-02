"""Free smoke tests for the GraphitiAdapter — no install, no network, no tokens.

These tests validate the adapter contract in dry-run mode only:
  - The module imports cleanly without graphiti-core installed.
  - GraphitiAdapter can be constructed with dry_run=True.
  - name and capabilities match the declared contract.
  - A dry-run ingest returns an IngestStats stub.
  - A dry-run query returns a QueryResult stub (no LLM call, no Neo4j).
  - _resolve_version() returns "unknown" when graphiti-core is absent, or
    a semver string when it is installed.

Run:
    PYTHONPATH=/path/to/OrgMemBench pytest tests/test_zep_smoke.py -v
    # or without pytest:
    python tests/test_zep_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable whether running as a script or via pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orgmembench.adapters.graphiti_adapter import GraphitiAdapter      # noqa: E402
from orgmembench.schemas import (                            # noqa: E402
    Artifact, Capability, Question,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_adapter(**kwargs) -> GraphitiAdapter:
    """Construct a GraphitiAdapter in dry-run mode (default)."""
    return GraphitiAdapter(dry_run=True, **kwargs)


def _make_artifact(slot_id: str = "art-001", ts: str | None = "2024-03-15") -> Artifact:
    return Artifact(
        slot_id=slot_id,
        company="test-co",
        source_type="slack_thread",
        text="The team decided to postpone the launch to Q3.",
        timestamp=ts,
        author="Alice",
        thread_id="thread-42",
    )


def _make_question(qid: str = "q-001") -> Question:
    return Question(
        id=qid,
        company="test-co",
        tier="small",
        category="C1",
        text="When was the launch decision made?",
        ground_truth_answer={"answer": "Q3"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_import_without_graphiti():
    """The module must import even if graphiti-core is not installed."""
    # If we got here the import at the top of the file already succeeded.
    assert GraphitiAdapter is not None, "GraphitiAdapter could not be imported"


def test_name():
    adapter = _make_adapter()
    assert adapter.name == "graphiti", f"Expected name='graphiti', got {adapter.name!r}"


def test_capabilities():
    adapter = _make_adapter()
    expected = {Capability.RECALL, Capability.TEMPORAL, Capability.PROVENANCE}
    assert adapter.capabilities == expected, (
        f"Capabilities mismatch.\n  expected: {expected}\n  got:      {adapter.capabilities}"
    )


def test_supports_temporal():
    assert _make_adapter().supports(Capability.TEMPORAL)


def test_supports_provenance():
    assert _make_adapter().supports(Capability.PROVENANCE)


def test_supports_recall():
    assert _make_adapter().supports(Capability.RECALL)


def test_does_not_support_scope():
    assert not _make_adapter().supports(Capability.SCOPE)


def test_does_not_support_negative():
    assert not _make_adapter().supports(Capability.NEGATIVE)


def test_dry_run_flag():
    adapter = _make_adapter()
    assert adapter.dry_run is True


def test_version_returns_string():
    """version() must return a string (either semver or 'unknown')."""
    adapter = _make_adapter()
    v = adapter.version()
    assert isinstance(v, str) and len(v) > 0, f"Expected non-empty string, got {v!r}"
    # If graphiti-core is installed the version should look like a semver.
    # If not installed it must be "unknown" (not an exception).
    assert v == "unknown" or v[0].isdigit(), (
        f"version() should be 'unknown' or start with a digit, got {v!r}"
    )


def test_dry_run_ingest_returns_stats():
    adapter = _make_adapter()
    arts = [_make_artifact("a1"), _make_artifact("a2")]
    stats = adapter.ingest(arts)
    assert stats.n_artifacts == 2, f"Expected 2, got {stats.n_artifacts}"
    assert stats.raw.get("dry_run") is True


def test_dry_run_ingest_zero_artifacts():
    adapter = _make_adapter()
    stats = adapter.ingest([])
    assert stats.n_artifacts == 0


def test_dry_run_query_returns_stub():
    adapter = _make_adapter()
    q = _make_question()
    result = adapter.query(q)
    assert result.dry_run is True
    assert "DRY_RUN" in result.answer_text
    assert result.system == "graphiti"
    assert result.question_id == q.id


def test_dry_run_query_with_as_of():
    """as_of is accepted without error in dry-run; the stub is returned."""
    adapter = _make_adapter()
    q = _make_question()
    result = adapter.query(q, as_of="2024-01-01")
    assert result.dry_run is True


def test_config_group_id_default():
    adapter = _make_adapter()
    assert adapter._group_id == "orgmembench"


def test_config_group_id_override():
    adapter = GraphitiAdapter(config={"group_id": "my-run"}, dry_run=True)
    assert adapter._group_id == "my-run"


def test_no_network_on_construction():
    """Constructing the adapter must not attempt any network call.

    Verified implicitly by the test running in an environment with no
    Neo4j/Anthropic reachable — if the constructor touched the network this
    test would hang or raise a connection error.
    """
    for _ in range(3):
        a = GraphitiAdapter(dry_run=True)
        assert a._graphiti is None, "_graphiti should be None until first live call"


def test_teardown_is_safe_when_not_connected():
    """teardown() must not raise when the Graphiti client was never initialised."""
    adapter = _make_adapter()
    adapter.teardown()   # should be a no-op


# ---------------------------------------------------------------------------
# Entry-point for running as a script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.environ.setdefault("ORGMEMBENCH_DRY_RUN", "1")

    tests = [
        test_import_without_graphiti,
        test_name,
        test_capabilities,
        test_supports_temporal,
        test_supports_provenance,
        test_supports_recall,
        test_does_not_support_scope,
        test_does_not_support_negative,
        test_dry_run_flag,
        test_version_returns_string,
        test_dry_run_ingest_returns_stats,
        test_dry_run_ingest_zero_artifacts,
        test_dry_run_query_returns_stub,
        test_dry_run_query_with_as_of,
        test_config_group_id_default,
        test_config_group_id_override,
        test_no_network_on_construction,
        test_teardown_is_safe_when_not_connected,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            failed += 1

    print(f"\n{'ALL PASS' if not failed else 'SOME FAILURES'}  ({passed} passed, {failed} failed)")
    sys.exit(0 if not failed else 1)
