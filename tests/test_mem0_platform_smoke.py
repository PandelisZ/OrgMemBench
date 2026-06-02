"""Free smoke tests for the Mem0 Platform adapter.

Validates:
- The module imports cleanly without mem0ai installed.
- Mem0PlatformAdapter(dry_run=True) constructs with zero side-effects.
- name and capabilities are declared correctly.
- dry_run=True query returns the standard stub (no LLM, no network).
- version() returns something (either "<ver> (platform)" or "unknown (platform)").
- MEM0_API_KEY is NOT read at construction (only at first live call).

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

from orgmembench.adapters.mem0_platform_adapter import Mem0PlatformAdapter  # noqa: E402
from orgmembench.schemas import Capability, Question                          # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter(**kwargs) -> Mem0PlatformAdapter:
    return Mem0PlatformAdapter(dry_run=True, **kwargs)


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
    import orgmembench.adapters.mem0_platform_adapter  # noqa: F401
    assert True


def test_adapter_name():
    a = _make_adapter()
    assert a.name == "mem0-platform"


def test_adapter_capabilities_include_recall():
    a = _make_adapter()
    assert Capability.RECALL in a.capabilities


def test_adapter_capabilities_include_provenance():
    a = _make_adapter()
    assert Capability.PROVENANCE in a.capabilities


def test_adapter_no_temporal_capability():
    """Platform reference_date is NL reasoning, NOT bi-temporal as_of; TEMPORAL not declared."""
    a = _make_adapter()
    assert Capability.TEMPORAL not in a.capabilities


def test_adapter_no_scope_capability():
    a = _make_adapter()
    assert Capability.SCOPE not in a.capabilities


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
    assert result.system == "mem0-platform"


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
    """version() must not raise; returns '<ver> (platform)' or 'unknown (platform)'."""
    a = _make_adapter()
    v = a.version()
    assert isinstance(v, str)
    assert len(v) > 0
    # Must always contain the "(platform)" marker so results are unambiguous.
    assert "(platform)" in v, f"Expected '(platform)' in version string, got: {v!r}"
    print(f"  mem0-platform version: {v!r}")


def test_version_contains_platform_marker():
    """The '(platform)' suffix distinguishes this from the OSS adapter version."""
    a = _make_adapter()
    v = a.version()
    assert v.endswith("(platform)"), f"Version should end with '(platform)', got: {v!r}"


def test_client_not_instantiated_in_init():
    """__init__ must NOT instantiate the MemoryClient object (lazy init).
    In particular: MEM0_API_KEY is NOT read at construction time."""
    # Temporarily unset the key to prove construction still works without it.
    orig = os.environ.pop("MEM0_API_KEY", None)
    try:
        a = _make_adapter()
        assert a._client is None
    finally:
        if orig is not None:
            os.environ["MEM0_API_KEY"] = orig


def test_config_passthrough():
    """Custom config dict is stored and accessible."""
    cfg = {"retrieval_top_k": 5}
    a = Mem0PlatformAdapter(config=cfg, dry_run=True)
    assert a.config["retrieval_top_k"] == 5


def test_name_differs_from_oss_adapter():
    """mem0-platform must be a distinct contestant from mem0 (OSS)."""
    from orgmembench.adapters.mem0_adapter import Mem0Adapter
    oss = Mem0Adapter(dry_run=True)
    platform = _make_adapter()
    assert oss.name != platform.name
    assert platform.name == "mem0-platform"
    assert oss.name == "mem0"


if __name__ == "__main__":
    tests = [
        test_import_without_mem0ai,
        test_adapter_name,
        test_adapter_capabilities_include_recall,
        test_adapter_capabilities_include_provenance,
        test_adapter_no_temporal_capability,
        test_adapter_no_scope_capability,
        test_adapter_is_dry_run,
        test_dry_run_query_returns_stub,
        test_dry_run_ingest_returns_stub,
        test_version_resolves_without_error,
        test_version_contains_platform_marker,
        test_client_not_instantiated_in_init,
        test_config_passthrough,
        test_name_differs_from_oss_adapter,
    ]
    for fn in tests:
        print(f"  {fn.__name__} ...", end=" ")
        fn()
        print("PASS")
    print(f"\nAll {len(tests)} smoke tests PASS")
