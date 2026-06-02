"""OrgMemBench — a benchmark for long-horizon organizational memory.

Public surface is intentionally small; import submodules directly:

    from orgmembench.corpus import load_corpus
    from orgmembench.questions import load_questions
    from orgmembench.runner import run_system

Nothing in this package spends tokens or calls an external system unless
``ORGMEMBENCH_DRY_RUN`` is explicitly disabled (default: dry-run ON). See
``orgmembench.config``.
"""

__version__ = "0.1.0"
