"""Global configuration + the dry-run safety guard.

The harness is built to be developed and smoke-tested for **zero cost**. Every
path that could spend money or hit an external system is gated on
:func:`dry_run`, which defaults to **True**. A real run must opt in explicitly
by setting ``ORGMEMBENCH_DRY_RUN=0`` in the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of the orgmembench/ package dir.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_ROOT = REPO_ROOT / "datasets"
RESULTS_ROOT = REPO_ROOT / "results"
CONFIG_ROOT = REPO_ROOT / "config"

# All LLM roles (judge, any reader/answer-synthesis) use Claude Sonnet 4.6 with
# extended thinking EXPLICITLY enabled (we control the budget; we never rely on
# a vendor's auto-thinking).
JUDGE_MODEL = "claude-sonnet-4-6"
THINKING_BUDGET_TOKENS = 4000
MAX_OUTPUT_TOKENS = 8000  # must be > THINKING_BUDGET_TOKENS

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def dry_run() -> bool:
    """True unless ORGMEMBENCH_DRY_RUN is explicitly falsey.

    Default-True means: imports, loading, normalization, and the full pipeline
    plumbing run for free; nothing calls an LLM or an external memory system.
    """
    val = os.getenv("ORGMEMBENCH_DRY_RUN", "1").strip().lower()
    if val in _FALSE:
        return False
    return True  # default + any truthy value


def require_live(action: str) -> None:
    """Raise if a cost-incurring action is attempted while dry-run is on."""
    if dry_run():
        raise RuntimeError(
            f"Refusing to {action}: ORGMEMBENCH_DRY_RUN is on (default). "
            f"Set ORGMEMBENCH_DRY_RUN=0 to allow real runs (and provide the "
            f"relevant API keys / stand up the services first)."
        )
