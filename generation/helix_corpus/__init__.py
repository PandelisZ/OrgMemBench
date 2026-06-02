"""helix-corpus — fully-synthetic context-graph benchmark generation.

Stages A-F: company canon, source-of-truth graph, corpus, cross-refs,
questions, validation. All LLM calls route through one open-weight model
(``gpt-oss:20b``) served behind an OpenAI-compatible API, configured via the
``GRAPHIFY_LLM_*`` environment variables.

The benchmark *runner* (Stages G-I) lives in the separate ``orgmembench``
harness package — generation and evaluation are deliberately kept apart.
"""

__version__ = "0.0.1"
