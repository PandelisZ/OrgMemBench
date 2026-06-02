"""Free smoke tests for ZepCloudAdapter — no install, no network, no tokens.

These tests validate the adapter contract in dry-run mode only:
  - The module imports cleanly without zep-cloud installed.
  - ZepCloudAdapter can be constructed with dry_run=True (no ZEP_API_KEY needed).
  - name and capabilities match the declared contract.
  - A dry-run ingest returns an IngestStats stub.
  - A dry-run query returns a QueryResult stub (no network, no tokens).
  - _resolve_version() returns a string ending in "+cloud" (or "unknown+cloud"
    if zep-cloud is absent), never raises.
  - teardown() is a no-op and never raises.

Run:
    PYTHONPATH=/path/to/OrgMemBench pytest tests/test_zep_cloud_smoke.py -v
    # or without pytest:
    python tests/test_zep_cloud_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable whether running as a script or via pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orgmembench.adapters.zep_cloud_adapter import ZepCloudAdapter   # noqa: E402
from orgmembench.schemas import (                                      # noqa: E402
    Artifact, Capability, Question,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_adapter(**kwargs) -> ZepCloudAdapter:
    """Construct a ZepCloudAdapter in dry-run mode (default)."""
    return ZepCloudAdapter(dry_run=True, **kwargs)


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

def test_import_without_zep_cloud():
    """The module must import even if zep-cloud is not installed."""
    assert ZepCloudAdapter is not None, "ZepCloudAdapter could not be imported"


def test_name():
    adapter = _make_adapter()
    assert adapter.name == "zep-cloud", (
        f"Expected name='zep-cloud', got {adapter.name!r}"
    )


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


def test_version_returns_cloud_string():
    """version() must return a string ending in '+cloud' or be 'unknown+cloud'."""
    adapter = _make_adapter()
    v = adapter.version()
    assert isinstance(v, str) and len(v) > 0, f"Expected non-empty string, got {v!r}"
    assert v.endswith("+cloud"), (
        f"version() should end with '+cloud' to distinguish from OSS adapter, got {v!r}"
    )
    # If zep-cloud is installed the leading part should look like a semver digit.
    # If not installed it must be 'unknown+cloud'.
    prefix = v.replace("+cloud", "")
    assert prefix == "unknown" or prefix[0].isdigit(), (
        f"version prefix should be 'unknown' or start with a digit, got {prefix!r}"
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
    assert result.system == "zep-cloud"
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
    adapter = ZepCloudAdapter(config={"group_id": "my-run"}, dry_run=True)
    assert adapter._group_id == "my-run"


def test_no_network_on_construction():
    """Constructing the adapter must not attempt any network call.

    Verified implicitly by the test running without ZEP_API_KEY and without
    network access — if the constructor touched the network this test would
    hang or raise.
    """
    for _ in range(3):
        a = ZepCloudAdapter(dry_run=True)
        assert a._client is None, "_client should be None until first live call"


def test_no_api_key_required_at_construct():
    """Construction must succeed even when ZEP_API_KEY is absent."""
    # Temporarily unset the env var to prove the constructor is free.
    original = os.environ.pop("ZEP_API_KEY", None)
    try:
        a = ZepCloudAdapter(dry_run=True)
        assert a._client is None
    finally:
        if original is not None:
            os.environ["ZEP_API_KEY"] = original


def test_teardown_is_safe_when_not_connected():
    """teardown() must not raise when the client was never initialised."""
    adapter = _make_adapter()
    adapter.teardown()   # should be a no-op
    assert adapter._client is None


def test_teardown_clears_client_reference():
    """teardown() clears _client even if it was set (simulated)."""
    adapter = _make_adapter()
    adapter._client = object()   # simulate an initialised client
    adapter.teardown()
    assert adapter._client is None


# ---------------------------------------------------------------------------
# Entry-point for running as a script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.environ.setdefault("ORGMEMBENCH_DRY_RUN", "1")

    tests = [
        test_import_without_zep_cloud,
        test_name,
        test_capabilities,
        test_supports_temporal,
        test_supports_provenance,
        test_supports_recall,
        test_does_not_support_scope,
        test_does_not_support_negative,
        test_dry_run_flag,
        test_version_returns_cloud_string,
        test_dry_run_ingest_returns_stats,
        test_dry_run_ingest_zero_artifacts,
        test_dry_run_query_returns_stub,
        test_dry_run_query_with_as_of,
        test_config_group_id_default,
        test_config_group_id_override,
        test_no_network_on_construction,
        test_no_api_key_required_at_construct,
        test_teardown_is_safe_when_not_connected,
        test_teardown_clears_client_reference,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'ALL PASS' if not failed else 'SOME FAILURES'}  ({passed} passed, {failed} failed)")
    sys.exit(0 if not failed else 1)
