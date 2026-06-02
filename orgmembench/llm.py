"""The single LLM client for all OrgMemBench LLM roles (judge, any reader).

Claude **Sonnet 4.6** with **extended thinking explicitly enabled** — we set the
thinking budget ourselves; we never rely on a vendor's auto-thinking. Hard
dry-run guard: in dry-run (the default) :meth:`complete` raises, so no role can
accidentally spend tokens. Callers (e.g. the judge) check dry-run *first* and
short-circuit to stubs; the raise here is the second line of defense.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from .config import JUDGE_MODEL, MAX_OUTPUT_TOKENS, THINKING_BUDGET_TOKENS, require_live

# Sonnet 4.6 public pricing (USD per token). Update if pricing changes; used for
# the cost-per-query metric.
_PRICE_IN = 3.0 / 1_000_000
_PRICE_OUT = 15.0 / 1_000_000


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class AnthropicLLM:
    """Thin wrapper over the Anthropic Messages API with thinking enabled."""

    def __init__(
        self,
        model: str = JUDGE_MODEL,
        thinking_budget: int = THINKING_BUDGET_TOKENS,
        max_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self.model = model
        self.thinking_budget = thinking_budget
        self.max_tokens = max(max_tokens, thinking_budget + 1024)
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("anthropic SDK not installed (pip install anthropic)") from exc
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        """Single-turn completion with extended thinking ON.

        Raises in dry-run — never spends tokens unless ORGMEMBENCH_DRY_RUN=0.
        """
        require_live("call the LLM")  # hard guard
        client = self._ensure_client()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            # Extended thinking requires temperature=1; we set the budget explicitly.
            "temperature": 1,
            "thinking": {"type": "enabled", "budget_tokens": self.thinking_budget},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        t0 = time.time()
        msg = client.messages.create(**kwargs)
        latency_ms = (time.time() - t0) * 1000.0

        # Concatenate the text blocks (skip thinking blocks).
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        usage = getattr(msg, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=in_tok * _PRICE_IN + out_tok * _PRICE_OUT,
            latency_ms=latency_ms,
        )

    def complete_json(self, prompt: str, system: str | None = None) -> tuple[dict, LLMResponse]:
        """complete() + best-effort JSON parse of the response text."""
        resp = self.complete(prompt, system=system)
        return _extract_json(resp.text), resp


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (handles code fences)."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}
