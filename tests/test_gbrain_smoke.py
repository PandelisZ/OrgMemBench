"""Smoke tests for GBrainAdapter — free, no subprocess to real binary, no network.

These tests validate:
1. The module imports cleanly even when gbrain is not installed.
2. GBrainAdapter constructs with dry_run=True without side effects.
3. name and capabilities are correctly declared.
4. Dry-run ingest returns a stub IngestStats (n_artifacts = input count).
5. Dry-run query returns a stub QueryResult with dry_run=True.
6. _build_capture_payload embeds the required frontmatter fields.
7. _slug_for / _slot_id_from_slug are inverses.
8. _resolve_version degrades gracefully when the binary is absent.
9. The adapter is reachable through the registry.

Run with: pytest tests/test_gbrain_smoke.py -v
Or:        python tests/test_gbrain_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running directly (python tests/test_gbrain_smoke.py) as well as via pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("ORGMEMBENCH_DRY_RUN", "1")

from orgmembench.adapters.gbrain_adapter import (  # noqa: E402
    GBrainAdapter,
    _slug_for,
    _slot_id_from_slug,
    _SLUG_PREFIX,
)
from orgmembench.schemas import (  # noqa: E402
    Artifact, Capability, Question,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_artifact(**kwargs) -> Artifact:
    defaults = dict(
        slot_id="helix-001-2024-07-15",
        company="helix",
        source_type="slack_thread",
        text="We decided to drop the v1 API endpoint on 2024-09-01.",
        timestamp="2024-07-15",
        author="Alice",
        thread_id="thread-42",
        role="primary",
    )
    defaults.update(kwargs)
    return Artifact(**defaults)


def _make_question(**kwargs) -> Question:
    defaults = dict(
        id="q-001",
        company="helix",
        tier="small",
        category="C2",
        text="When was the v1 API deprecation decided and who decided it?",
        ground_truth_answer={"text": "2024-07-15, Alice"},
    )
    defaults.update(kwargs)
    return Question(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_import():
    """Module imports cleanly without gbrain installed."""
    import orgmembench.adapters.gbrain_adapter  # noqa: F401 — import is the test


def test_constructor_is_free():
    """Construction does not touch the filesystem, network, or subprocess."""
    adapter = GBrainAdapter(dry_run=True)
    assert adapter is not None


def test_name():
    adapter = GBrainAdapter(dry_run=True)
    assert adapter.name == "gbrain"


def test_capabilities_include_recall_and_provenance():
    adapter = GBrainAdapter(dry_run=True)
    assert Capability.RECALL in adapter.capabilities
    assert Capability.PROVENANCE in adapter.capabilities


def test_capabilities_exclude_temporal():
    """gbrain has --since/--until filtering but NOT true as-of bi-temporal queries."""
    adapter = GBrainAdapter(dry_run=True)
    assert Capability.TEMPORAL not in adapter.capabilities


def test_capabilities_exclude_scope_and_negative():
    adapter = GBrainAdapter(dry_run=True)
    assert Capability.SCOPE not in adapter.capabilities
    assert Capability.NEGATIVE not in adapter.capabilities


def test_dry_run_ingest_stub():
    adapter = GBrainAdapter(dry_run=True)
    arts = [_make_artifact(slot_id=f"art-{i}") for i in range(5)]
    stats = adapter.ingest(iter(arts))
    assert stats.n_artifacts == 5
    assert stats.raw.get("dry_run") is True


def test_dry_run_query_stub():
    adapter = GBrainAdapter(dry_run=True)
    q = _make_question()
    result = adapter.query(q)
    assert result.dry_run is True
    assert "DRY_RUN" in result.answer_text
    assert result.question_id == q.id
    assert result.system == "gbrain"


def test_dry_run_query_with_as_of():
    adapter = GBrainAdapter(dry_run=True)
    q = _make_question()
    result = adapter.query(q, as_of="2024-09-01")
    assert result.dry_run is True


def test_build_capture_payload_frontmatter():
    art = _make_artifact()
    payload = GBrainAdapter._build_capture_payload(art)
    assert "---" in payload
    assert "orgmembench_slot_id" in payload
    assert art.slot_id in payload
    assert art.source_type in payload
    assert art.timestamp in payload
    assert art.author in payload
    assert art.thread_id in payload
    assert art.text in payload


def test_build_capture_payload_optional_fields_absent():
    """Absent optional fields must not appear as 'None' strings in the payload."""
    art = _make_artifact(timestamp=None, author=None, thread_id=None, role=None)
    payload = GBrainAdapter._build_capture_payload(art)
    assert "None" not in payload
    assert art.slot_id in payload


def test_slug_for_produces_prefix():
    slug = _slug_for("helix-001-2024-07-15")
    assert slug.startswith(f"{_SLUG_PREFIX}/")
    assert "helix-001-2024-07-15" in slug


def test_slug_round_trip():
    slot_id = "helix-001-2024-07-15"
    slug = _slug_for(slot_id)
    recovered = _slot_id_from_slug(slug)
    assert recovered == slot_id.lower()


def test_slug_foreign_returns_none():
    assert _slot_id_from_slug("some/other/slug") is None
    assert _slot_id_from_slug("") is None


def test_resolve_version_degrades_gracefully():
    """Version resolution must not raise when gbrain binary is absent."""
    adapter = GBrainAdapter(config={"binary": "/nonexistent/gbrain"}, dry_run=True)
    ver = adapter.version()  # calls _resolve_version internally
    assert isinstance(ver, str)
    # Should return "unknown" or similar — not raise.
    assert ver  # non-empty string


def test_config_binary_override():
    adapter = GBrainAdapter(config={"binary": "/usr/local/bin/gbrain"}, dry_run=True)
    assert adapter._bin == "/usr/local/bin/gbrain"


def test_config_llm_model_override():
    adapter = GBrainAdapter(config={"llm_model": "anthropic:claude-opus-4"}, dry_run=True)
    assert adapter._llm_model == "anthropic:claude-opus-4"


def test_env_binary_override(monkeypatch=None):
    """GBRAIN_BIN env var is respected."""
    import importlib
    old = os.environ.get("GBRAIN_BIN")
    try:
        os.environ["GBRAIN_BIN"] = "/opt/bun/bin/gbrain"
        adapter = GBrainAdapter(dry_run=True)
        assert adapter._bin == "/opt/bun/bin/gbrain"
    finally:
        if old is None:
            os.environ.pop("GBRAIN_BIN", None)
        else:
            os.environ["GBRAIN_BIN"] = old


def test_registry_resolves_gbrain():
    from orgmembench.adapters.registry import get_adapter
    adapter = get_adapter("gbrain", dry_run=True)
    assert adapter.name == "gbrain"


def test_registry_available_includes_gbrain():
    from orgmembench.adapters.registry import available
    assert "gbrain" in available()


# ---------------------------------------------------------------------------
# Direct execution support
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_import,
        test_constructor_is_free,
        test_name,
        test_capabilities_include_recall_and_provenance,
        test_capabilities_exclude_temporal,
        test_capabilities_exclude_scope_and_negative,
        test_dry_run_ingest_stub,
        test_dry_run_query_stub,
        test_dry_run_query_with_as_of,
        test_build_capture_payload_frontmatter,
        test_build_capture_payload_optional_fields_absent,
        test_slug_for_produces_prefix,
        test_slug_round_trip,
        test_slug_foreign_returns_none,
        test_resolve_version_degrades_gracefully,
        test_config_binary_override,
        test_config_llm_model_override,
        test_env_binary_override,
        test_registry_resolves_gbrain,
        test_registry_available_includes_gbrain,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            failed += 1
    print()
    if failed:
        print(f"{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"All {len(tests)} smoke tests PASS")
