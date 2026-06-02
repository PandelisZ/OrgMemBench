"""Lenient parsers for gpt-oss output.

Design constraint (see design doc §4.3): gpt-oss:20b is much better at
natural-language generation than at strict-JSON output. We therefore ask
it for **structured text** (Markdown headers, YAML records, one-triple-per-line)
and parse leniently on this side. On parse failure we either:

1. **Sanitize and retry the parse** for common gpt-oss quirks (smart-
   quotes, trailing whitespace, code-fence wrappers) — synchronous,
   no LLM call.
2. **Ask gpt-oss to fix its output** with a format-nudge prompt — one
   LLM call mirroring the ``_llm_repair_submit_args`` pattern already
   proven in ``graphify_service/agentic_retrieve.py``.

Parsers exposed here:

- :func:`strip_code_fences` — peel triple-backtick code-fence wrappers
  (``yaml``, ``json``, or unmarked).
- :func:`normalize_smart_quotes` — replace curly quotes with ASCII.
- :func:`parse_yaml_lenient` — accepts a string of one or more YAML
  documents; tolerates code-fence wrap; returns a list of dicts.
- :func:`parse_keyed_markdown` — accepts Markdown text with ``## <KEY>``
  section headers; returns ``dict[key, body]``.
- :func:`parse_triples_line` — accepts text of the form
  ``A → <relation> → B`` (one per line, ``->`` also accepted); returns
  list of ``(source, relation, target)`` tuples.
- :func:`parse_yaml_records_with_repair` — async, takes an LLM and uses
  it to repair on parse failure.

These parsers never raise on partial-success input — they return what
they could parse and the caller decides what to do with parse coverage.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import yaml

logger = logging.getLogger("helix_corpus.parsers")


# Smart-quote substitutions. gpt-oss frequently emits curly quotes inside
# YAML / JSON values; PyYAML accepts them in some contexts but not others.
# We normalize at the boundary.
_SMART_QUOTE_MAP = str.maketrans({
    "‘": "'",   # left single quote
    "’": "'",   # right single quote
    "“": '"',   # left double quote
    "”": '"',   # right double quote
    "–": "-",   # en dash
    "—": "-",   # em dash
    "‑": "-",   # U+2011 non-breaking hyphen (gpt-oss emits these in
                # compound modifiers like "ex‑operations manager")
    " ": " ",  # non-breaking space
})


_FENCE_RE = re.compile(
    r"^```(?:yaml|yml|json|markdown|md|text|txt)?\s*\n(.*?)\n```\s*$",
    re.DOTALL,
)


def strip_code_fences(text: str) -> str:
    r"""Strip an outer triple-backtick code-fence wrapper if present.

    gpt-oss sometimes wraps its YAML or Markdown output in a code fence
    even when the prompt said not to. One-shot strip; if nested fences,
    only the outer one is removed (the inner becomes literal content).
    """
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def normalize_smart_quotes(text: str) -> str:
    """Replace smart quotes / dashes with ASCII equivalents.

    Applied as a sanitizer before YAML / JSON parsing. Loses some
    semantic distinction (an em dash becomes a hyphen) but the records
    we extract aren't typographically sensitive.
    """
    return text.translate(_SMART_QUOTE_MAP)


def parse_yaml_lenient(text: str) -> list[dict[str, Any]]:
    """Parse one or more YAML documents from ``text``.

    Strategy:
    1. Strip code fences.
    2. Normalize smart quotes.
    3. Try ``yaml.safe_load_all`` to handle multiple documents
       (``---``-separated). Filter out non-dict results.
    4. If that returns nothing, try parsing as a single document.

    Returns a list of dicts. Empty list on total parse failure (logged).
    """
    cleaned = normalize_smart_quotes(strip_code_fences(text))
    if not cleaned:
        return []
    try:
        docs = list(yaml.safe_load_all(cleaned))
    except yaml.YAMLError as exc:
        logger.warning("parse_yaml_lenient: safe_load_all failed: %s", exc)
        # Single-doc fallback
        try:
            single = yaml.safe_load(cleaned)
            docs = [single] if single is not None else []
        except yaml.YAMLError as exc2:
            logger.warning("parse_yaml_lenient: single-doc fallback failed: %s", exc2)
            return []
    return [d for d in docs if isinstance(d, dict)]


@dataclass(frozen=True)
class KeyedSection:
    """A single ``## <key>`` section parsed from structured Markdown."""

    key: str
    body: str


# Accept either # or ## section headers. gpt-oss occasionally uses # for
# top-level sections even when the prompt says ##; the *level* doesn't
# carry semantics here, only the section boundary does.
_MD_SECTION_RE = re.compile(r"^#{1,2}\s+(.+?)\s*$", re.MULTILINE)


def parse_keyed_markdown(text: str) -> list[KeyedSection]:
    """Parse Markdown into a sequence of top-level (``#`` or ``##``) sections.

    Each section's ``body`` is the text between its header and the next
    header at the same-or-shallower level (or end-of-text), stripped of
    leading/trailing whitespace. Order preserved. Smart-quotes are
    normalised before splitting (so a non-breaking hyphen in a header
    doesn't cause a mismatch downstream).

    Used for Stage A skeleton (``## Founding`` etc) and Stage B
    master-timeline blocks (``## EV-2024-001`` etc).
    """
    cleaned = normalize_smart_quotes(strip_code_fences(text))
    matches = list(_MD_SECTION_RE.finditer(cleaned))
    if not matches:
        return []
    sections: list[KeyedSection] = []
    for i, m in enumerate(matches):
        key = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body = cleaned[start:end].strip()
        sections.append(KeyedSection(key=key, body=body))
    return sections


_TRIPLE_RE = re.compile(
    r"^\s*(.+?)\s*(?:→|->|>)\s*(\w+)\s*(?:→|->|>)\s*(.+?)\s*$",
)


def parse_triples_line(text: str) -> list[tuple[str, str, str]]:
    """Parse ``A → <relation> → B`` triples, one per line.

    Accepts both unicode ``→`` and ASCII ``->`` (or ``>``) as separator.
    Lines that don't match the pattern are skipped (logged at debug).
    Returns list of ``(source_id, relation, target_id)`` with all
    fields stripped.
    """
    cleaned = strip_code_fences(text)
    out: list[tuple[str, str, str]] = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _TRIPLE_RE.match(line)
        if not m:
            logger.debug("parse_triples_line: skipping unparseable line: %r", line[:120])
            continue
        out.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return out


# ---------------------------------------------------------------------------
# LLM-assisted repair on parse failure
# ---------------------------------------------------------------------------


REPAIR_PROMPT = """\
The following output was supposed to be {format_name} but couldn't be parsed.

Parser error:
{error}

Original output:
{original}

Re-emit the output as VALID {format_name}, preserving all the semantic
content but fixing the formatting. Do not add commentary. Do not wrap
in code fences. Output ONLY the corrected {format_name}.
"""


async def parse_yaml_records_with_repair(
    text: str,
    llm,  # HelixLLM — typed loosely to avoid circular import
    *,
    max_repairs: int = 1,
    format_name: str = "YAML",
) -> list[dict[str, Any]]:
    """Parse YAML records; on failure, ask the LLM to fix and try again.

    Mirrors the ``_llm_repair_submit_args`` pattern from the retrieval
    shim. Single repair attempt by default — if the LLM can't fix it
    once, the input is degenerate and another retry won't help.
    """
    records = parse_yaml_lenient(text)
    if records:
        return records

    if max_repairs <= 0:
        return []

    # Probe what went wrong so we can show the LLM the error.
    cleaned = normalize_smart_quotes(strip_code_fences(text))
    try:
        list(yaml.safe_load_all(cleaned))
        error_msg = "YAML parsed but no dict records found"
    except yaml.YAMLError as exc:
        error_msg = str(exc)

    repair_prompt = REPAIR_PROMPT.format(
        format_name=format_name,
        error=error_msg,
        original=text[:4000],  # cap to avoid blowing prompt budget
    )

    try:
        repaired = await llm.call_text(
            user=repair_prompt,
            stage=None,  # no specific stage — repair calls use model default effort
            # Generous: repair output is the same size as the original
            # parse target, and we don't want a tight cap silently
            # truncating the fixed-up YAML.
            max_tokens=8000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("parse_yaml_records_with_repair: LLM call failed: %s", exc)
        return []

    records = parse_yaml_lenient(repaired)
    if not records:
        logger.warning(
            "parse_yaml_records_with_repair: even after LLM repair, no records "
            "(original_len=%d, repaired_len=%d)", len(text), len(repaired),
        )
    return records
