"""LLM wrapper for the helix-corpus pipeline.

Single backend by design: ``gpt-oss:20b`` via an OpenAI-compatible endpoint,
talking the OpenAI Chat Completions API. We extend the proven
``OpenAICompatClient`` from ``graphify_service.llm_engine`` with two
helix-specific things:

1. ``reasoning_effort`` pass-through — the underlying Ollama endpoint
   accepts ``reasoning_effort: low|medium|high`` at the top of the body
   and respects it. ``OpenAICompatClient`` did not know about this
   parameter; we add it here without touching the upstream shim.

2. ``call_text(...)`` — a single-turn convenience that asks for plain
   text and returns the assistant's ``content`` field. No tool-use,
   no JSON-schema-enforcement, no Anthropic-shaped translation — just
   the simplest possible "prompt in, text out" surface that the
   generation stages need.

For tool-use / Anthropic-shaped calls (which we do NOT use in helix-corpus
stages A-F), continue to use ``OpenAICompatClient.messages.create()``
from the upstream module directly.

This wrapper is configured entirely via environment variables (canonical
contract: ``GRAPHIFY_LLM_BACKEND``, ``GRAPHIFY_LLM_BASE_URL``,
``GRAPHIFY_LLM_API_KEY``, ``GRAPHIFY_LLM_EXTRA_HEADERS``,
``GRAPHIFY_AGENT_MODEL``). Point ``GRAPHIFY_LLM_BASE_URL`` at any
OpenAI-compatible server (e.g. a local Ollama or vLLM instance).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

# These imports rely on graphify-service being installed (path dep in
# pyproject.toml). The OpenAICompatClient handles auth, optional extra
# request headers, the sequential semaphore, and the empty-content /
# format-nudge retry. We only add reasoning_effort + a text-only helper on top.
from graphify_service.llm_engine import (
    OpenAICompatClient,
    _parse_extra_headers,
)

logger = logging.getLogger("helix_corpus.llm")


# Per-stage default reasoning_effort.
# Overridden by HELIX_REASONING_EFFORT env var if set; further overridable
# by an explicit call-site argument.
STAGE_REASONING_EFFORT: dict[str, str] = {
    "A": "medium",  # canon — persona coherence matters
    "B": "high",    # graph — highest-stakes generation
    "C": "low",     # corpus bulk — sentinels calibrate quality
    "D": "low",     # noise injection — phrase-level
    "E": "medium",  # question phrasing
    "F": "medium",  # validation is itself a reasoning task
}


# Per-stage default max_tokens (output budget). Calibrated for
# gpt-oss:20b's 32,768-token output ceiling and the per-stage artefact
# shapes the generation stages emit.
#
# Rule of thumb: set a **generous ceiling**. The cost of slack is wasted
# token budget; the cost of a too-tight cap is silently-truncated
# artefacts (finish_reason="length"). gpt-oss also burns up to several
# thousand tokens on the hidden reasoning channel *before* it starts
# emitting content, so the floor is much higher than you'd guess for
# short outputs.
#
# These are defaults; per-call overrides are common — e.g. Stage C
# Slack threads pass 1024, Stage C long ADRs pass 6000, Stage C
# meeting-transcript chunks pass 2000.
STAGE_DEFAULT_MAX_TOKENS: dict[str, int] = {
    # Defaults are ~2× the typical expected output, because max_tokens
    # is a *hard cutoff* — if the model needs more, the artefact is
    # silently truncated (finish_reason="length"). Slack is cheap;
    # truncation is expensive.
    "A": 12000,   # canon: skeleton ~3k, year-arc narrative ~1.5k, persona library batch ~6k, customer arc ~1k
    "B": 8000,    # graph: per-event YAML ~3-4k; cross-event linking call lists triples for many events
    "C": 8000,    # corpus default (genres override; Slack thread overrides down to 1500, ADR up to 12000, transcript chunks 4000)
    "D": 2000,    # noise: small prose insertions ~500-1000
    "E": 4000,    # questions: phrasing + rubric ~1500-2000
    "F": 8000,    # validation: answerability test gives the model the evidence + asks for the answer
}


def _resolve_effort(stage: str | None, override: str | None) -> str | None:
    """Resolve reasoning_effort for a call: explicit override > env var > stage default > None."""
    if override:
        return override
    env_override = os.getenv("HELIX_REASONING_EFFORT", "").strip().lower()
    if env_override:
        return env_override
    if stage and stage in STAGE_REASONING_EFFORT:
        return STAGE_REASONING_EFFORT[stage]
    return None


def _resolve_max_tokens(stage: str | None, override: int | None) -> int:
    """Resolve max_tokens: explicit override > stage default > 4000 generic fallback."""
    if override is not None:
        return override
    if stage and stage in STAGE_DEFAULT_MAX_TOKENS:
        return STAGE_DEFAULT_MAX_TOKENS[stage]
    return 4000


class HelixLLM:
    """Single-turn text-in/text-out wrapper for gpt-oss:20b.

    Thin layer over ``OpenAICompatClient``. Construct once per pipeline
    run; reuse across all stage calls (the underlying client holds an
    httpx connection pool and an ``asyncio.Semaphore(1)``).
    """

    def __init__(self, client: OpenAICompatClient | None = None) -> None:
        self._client = client or _build_default_client()
        # Circuit breaker: a systemic failure (laptop sleep, internet
        # drop, endpoint down) makes the endpoint return empty content
        # fast. Without this, stage loops mark every slot "empty"-done
        # and poison their checkpoints (a re-run then SKIPS the work).
        # After N CONSECUTIVE empties we raise instead, so the stage
        # crashes cleanly with its checkpoint intact and a re-run
        # resumes. A genuine one-off empty resets on the next success.
        self._consecutive_empty = 0
        try:
            self._empty_breaker = int(os.getenv("HELIX_EMPTY_BREAKER", "8"))
        except ValueError:
            self._empty_breaker = 8

    @property
    def client(self) -> OpenAICompatClient:
        return self._client

    async def call_text(
        self,
        *,
        system: str | None = None,
        user: str,
        stage: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Single-turn prompt, returns the assistant's text content.

        ``stage`` selects the per-stage defaults for both
        ``reasoning_effort`` (from :data:`STAGE_REASONING_EFFORT`) and
        ``max_tokens`` (from :data:`STAGE_DEFAULT_MAX_TOKENS`). Per-call
        overrides win.

        Notes on ``max_tokens``:
        - gpt-oss:20b reserves output budget for its hidden reasoning
          channel BEFORE emitting content. A too-tight ``max_tokens``
          returns empty content even though the model "knew" the answer.
        - Default-by-stage is a *ceiling*, not a target. The model stops
          at end-of-turn regardless.
        - Hard ceiling per call is 32,768; default behaviour ranges
          1,000-6,000 across stages. For specific genres (a long ADR,
          a meeting-transcript chunk) override at the call site.
        """
        effort = _resolve_effort(stage, reasoning_effort)
        budget = _resolve_max_tokens(stage, max_tokens)

        chat_messages: list[dict[str, str]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.append({"role": "user", "content": user})

        body: dict[str, Any] = {
            "model": self._client.default_model,
            "messages": chat_messages,
            "temperature": temperature if temperature is not None else self._client.temperature,
            "max_tokens": budget,
        }
        if effort:
            body["reasoning_effort"] = effort

        async with self._client.semaphore:
            msg = await self._client._post_chat_message(body)

        content = (msg.get("content") or "").strip()
        # gpt-oss frequently puts everything in 'reasoning' and leaves
        # content empty — for single-turn generation we want the user-
        # facing answer, so we accept content even if empty and let the
        # caller decide whether to retry. Logging the reasoning preview
        # for debugging.
        if not content:
            self._consecutive_empty += 1
            logger.warning(
                "helix_corpus.llm: empty content (stage=%s effort=%s "
                "consecutive=%d reasoning_preview=%r)",
                stage, effort, self._consecutive_empty, (msg.get("reasoning") or "")[:200],
            )
            if self._consecutive_empty >= self._empty_breaker:
                raise RuntimeError(
                    f"helix_corpus.llm: {self._consecutive_empty} consecutive empty "
                    "responses — likely a systemic failure (sleep / internet drop / "
                    "endpoint down). Aborting so the stage checkpoint is preserved; "
                    "re-run to resume."
                )
        else:
            self._consecutive_empty = 0
        return content

    async def aclose(self) -> None:
        aclose = getattr(self._client, "aclose", None)
        if callable(aclose):
            await aclose()


def _build_default_client() -> OpenAICompatClient:
    """Build the OpenAICompatClient from the ``GRAPHIFY_LLM_*`` env vars.

    Errors with a helpful message if a required var is missing.
    """
    base_url = os.getenv("GRAPHIFY_LLM_BASE_URL", "").strip()
    api_key = os.getenv("GRAPHIFY_LLM_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RuntimeError(
            "helix_corpus.llm: missing env vars. Required: GRAPHIFY_LLM_BASE_URL and "
            "GRAPHIFY_LLM_API_KEY (plus optional GRAPHIFY_LLM_EXTRA_HEADERS, a JSON "
            "object of extra request headers if your endpoint sits behind a proxy)."
        )
    model = os.getenv("GRAPHIFY_AGENT_MODEL", "gpt-oss:20b").strip() or "gpt-oss:20b"

    timeout_raw = os.getenv("GRAPHIFY_LLM_TIMEOUT", "600")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 600.0

    temp_raw = os.getenv("GRAPHIFY_LLM_TEMPERATURE", "0.2")
    try:
        temperature = float(temp_raw)
    except ValueError:
        temperature = 0.2

    conc_raw = os.getenv("GRAPHIFY_LLM_OPENAI_COMPAT_CONCURRENCY", "1")
    try:
        concurrency = int(conc_raw)
    except ValueError:
        concurrency = 1

    return OpenAICompatClient(
        base_url=base_url,
        api_key=api_key,
        default_model=model,
        extra_headers=_parse_extra_headers(),
        timeout=timeout,
        concurrency=concurrency,
        temperature=temperature,
    )


async def _smoke() -> int:
    """One-shot smoke test you can run with: python -m helix_corpus.llm"""
    llm = HelixLLM()
    out = await llm.call_text(
        system="You are a terse echo.",
        user="Reply with exactly the word PONG and nothing else.",
        max_tokens=16,
    )
    print(f"reply={out!r}")
    await llm.aclose()
    return 0 if "pong" in out.lower() else 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(_smoke()))
