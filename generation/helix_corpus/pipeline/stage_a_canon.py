"""Stage A — Company canon generation.

Five gpt-oss passes (design doc §5):

* A1 — skeleton: structured-Markdown brief (founding, year arcs,
  eras, products, customer count, tooling timeline).
* A2 — year-arc expansion: per-year 2-3-paragraph narrative.
* A3 — persona library: YAML records (active + long-tail).
* A4 — customer arcs: one YAML per customer.
* A5 — persona critique-and-revise: gpt-oss flags voice-collision pairs.

Wire format is structured text (Markdown / YAML). Parsing is lenient
(:mod:`helix_corpus.parsers`); validation against Pydantic schemas
follows. The artefact tree at the end of Stage A is described in
:func:`run`'s docstring.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM
from helix_corpus.parsers import (
    normalize_smart_quotes,
    parse_keyed_markdown,
    parse_yaml_lenient,
    strip_code_fences,
)
from helix_corpus.schemas import CustomerArc, Persona

logger = logging.getLogger("helix_corpus.stage_a")


# ---------------------------------------------------------------------------
# Size-dependent parameters
# ---------------------------------------------------------------------------

# Persona / customer counts. Companies have history — a 6-year-old
# company will have churned customers, ex-employees, dead deals,
# political fights, failed fundraises. These counts must support
# that breadth, not just the *current* org chart.
#
# Per-size:
# - active_personas: people currently at the company
# - longtail_personas: minor characters who appear in current artefacts
# - departed_personas: ex-employees who appear in OLD artefacts
#   (retrospectives, postmortems, mentions in newer Slack threads)
# - active_customers: currently-paying named customers
# - historical_customers: churned / lost-the-pitch / design-partners
#   who left — appear in old artefacts and references
# - depth_arcs: number of "emotional / failed / messy" arc narratives
#   (failed fundraise, near-pivot, competitor fight, political battle)
SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"active_personas":  8, "longtail_personas": 20, "departed_personas":  8, "active_customers":  5, "historical_customers":  5, "depth_arcs":  6, "years": 6},
    "medium": {"active_personas": 25, "longtail_personas": 50, "departed_personas": 20, "active_customers": 12, "historical_customers": 18, "depth_arcs": 12, "years": 6},
    "large":  {"active_personas": 50, "longtail_personas":100, "departed_personas": 50, "active_customers": 25, "historical_customers": 40, "depth_arcs": 24, "years": 6},
}

# Anchor seeds — the ONLY Helix-specific content humans provide.
COMPANY_NAME = "Helix Logistics"
COMPANY_ARCHETYPE = (
    "B2B SaaS for mid-market freight-forwarding companies, "
    "founded in 2020, ~85 employees by 2025"
)
COMPANY_ONE_LINER = f"{COMPANY_NAME}: {COMPANY_ARCHETYPE}."
CURRENT_YEAR = 2026


# Resolve the prompts directory relative to THIS file (which sits at
# helix_corpus/pipeline/stage_a_canon.py). Parent of pipeline/ is the
# package root; prompts/stage_a/ sits next to pipeline/.
#
# We avoid importlib.resources here because editable installs cause the
# top-level "helix_corpus" name to multiplex with the project-root
# directory, returning an ambiguous MultiplexedPath. And we avoid
# helix_corpus.__file__ because namespace-package resolution can set it
# to None on editable installs.
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_a"


def _load_template(name: str) -> str:
    """Read a prompt template from helix_corpus/prompts/stage_a/."""
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Pass A1 — skeleton
# ---------------------------------------------------------------------------


async def _pass_a1_skeleton(llm: HelixLLM, params: dict, data_dir: Path) -> dict[str, Any]:
    """Run pass A1 and return the parsed skeleton object.

    Output: data/helix_canon/skeleton.md (raw gpt-oss) +
    data/helix_canon/skeleton.json (parsed).
    """
    out_md = data_dir / "helix_canon" / "skeleton.md"
    out_json = data_dir / "helix_canon" / "skeleton.json"

    if out_md.exists() and out_json.exists():
        logger.info("A1 skeleton already present at %s, skipping", out_md)
        parsed = json.loads(out_json.read_text(encoding="utf-8"))
        # JSON serialises dict keys as strings — restore year_arcs to int
        # keys so downstream passes that do arithmetic on years work.
        if "year_arcs" in parsed and isinstance(parsed["year_arcs"], dict):
            parsed["year_arcs"] = {
                int(k): v for k, v in parsed["year_arcs"].items() if str(k).isdigit()
            }
        return parsed

    if out_md.exists():
        # Raw output is on disk from a previous run but parsing failed
        # (skeleton.json missing). Re-parse without burning another
        # gpt-oss call.
        logger.info("A1 raw markdown present at %s; re-parsing without LLM call", out_md)
        text = out_md.read_text(encoding="utf-8")
    else:
        prompt = _load_template("a1_skeleton.md").format(
            company_name=COMPANY_NAME,
            company_archetype=COMPANY_ARCHETYPE,
            current_year=CURRENT_YEAR,
            year_arc_count=params["years"] + 1,  # founding through current year inclusive
        )
        text = await llm.call_text(stage="A", user=prompt)
        if not text.strip():
            raise RuntimeError("A1 returned empty content")

        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(text, encoding="utf-8")

    parsed = _parse_skeleton(text)
    out_json.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
    logger.info(
        "A1 skeleton written: founding=%s founders=%s year_arcs=%d eras=%d products=%d customers=%s",
        parsed.get("founding_year"),
        ", ".join(f["name"] for f in parsed.get("founders", [])) or "?",
        len(parsed.get("year_arcs", {})),
        len(parsed.get("eras", [])),
        len(parsed.get("products", [])),
        parsed.get("customer_arc_count"),
    )
    return parsed


_YEAR_ARC_RE = re.compile(r"^\s*-\s*(\d{4})\s*:\s*(.+?)\s*$", re.MULTILINE)
_FOUNDING_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ERA_BLOCK_RE = re.compile(
    r"###\s*Era\s+(\d+)\s*:\s*(.+?)\n"
    r"(?:.*?\n)*?"
    r".*?Date span:\s*(\d{4}-\d{2})\s*to\s*(\d{4}-\d{2})\s*\n"
    r"(?:.*?\n)*?"
    r".*?Discipline level:\s*(low|medium|high)\s*\n"
    r"(?:.*?\n)*?"
    r".*?Characterisation:\s*(.+?)(?=\n###|\n##|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_TOOLING_RE = re.compile(
    r"^\s*-\s*(\d{4})(?:-Q([1-4]))?\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)
_PRODUCT_RE = re.compile(r"^\s*-\s*(.+?)\s*$", re.MULTILINE)


def _parse_skeleton(text: str) -> dict[str, Any]:
    """Parse the A1 skeleton Markdown into a structured dict.

    Tolerant — we expect gpt-oss to be a little loose with formatting.
    Required fields raise; optional fields default to empty.
    """
    sections = {s.key.lower(): s.body for s in parse_keyed_markdown(text)}
    if "founding" not in sections:
        raise RuntimeError("A1 skeleton missing 'Founding' section")

    founding_body = sections["founding"]
    fy_match = _FOUNDING_YEAR_RE.search(founding_body)
    if not fy_match:
        raise RuntimeError("A1 skeleton 'Founding' section missing a 4-digit year")
    founding_year = int(fy_match.group(0))

    # Founder names: heuristic — capitalised first-last sequences in the
    # Founding section. We don't enforce structure here because gpt-oss
    # writes founders as prose. We'll extract more carefully in later passes.
    founders = _extract_founders(founding_body)
    if len(founders) < 2:
        raise RuntimeError(
            f"A1 skeleton needs 2 founders; extracted {len(founders)}. "
            "Body: {founding_body[:300]}"
        )
    founders = founders[:2]

    # Year arcs
    year_arcs: dict[int, str] = {}
    if "year arcs" in sections:
        for m in _YEAR_ARC_RE.finditer(sections["year arcs"]):
            year_arcs[int(m.group(1))] = m.group(2).strip()
    if not year_arcs:
        raise RuntimeError("A1 skeleton has no parseable year arcs")

    # Doc-discipline eras
    eras = []
    if "doc-discipline eras" in sections:
        for m in _ERA_BLOCK_RE.finditer(sections["doc-discipline eras"]):
            eras.append({
                "n": int(m.group(1)),
                "name": m.group(2).strip(),
                "start": m.group(3),
                "end": m.group(4),
                "discipline_level": m.group(5).lower(),
                "characterisation": m.group(6).strip(),
            })
    if len(eras) != 5:
        raise RuntimeError(f"A1 skeleton needs exactly 5 eras; got {len(eras)}")
    levels = {e["discipline_level"] for e in eras}
    if "low" not in levels or "high" not in levels:
        raise RuntimeError(
            f"A1 eras must include >=1 low AND >=1 high discipline era; got {levels}"
        )

    # Products
    products = []
    if "product lines" in sections:
        for m in _PRODUCT_RE.finditer(sections["product lines"]):
            line = m.group(1).strip()
            if line and not line.startswith("#"):
                products.append(line)
    if not products:
        raise RuntimeError("A1 skeleton has no parseable product lines")

    # Customer count
    customer_count: int | None = None
    if "customer arc count" in sections:
        for tok in sections["customer arc count"].split():
            if tok.isdigit():
                customer_count = int(tok)
                break
    if not (customer_count and 8 <= customer_count <= 10):
        raise RuntimeError(
            f"A1 'Customer arc count' must be 8-10; got {customer_count!r}"
        )

    # Tooling timeline
    tooling = []
    if "tooling timeline" in sections:
        for m in _TOOLING_RE.finditer(sections["tooling timeline"]):
            tooling.append({
                "year": int(m.group(1)),
                "quarter": int(m.group(2)) if m.group(2) else None,
                "description": m.group(3).strip(),
            })
    if not tooling:
        raise RuntimeError("A1 skeleton has no parseable tooling timeline")

    return {
        "founding_year": founding_year,
        "founders": founders,
        "year_arcs": year_arcs,
        "eras": eras,
        "products": products,
        "customer_arc_count": customer_count,
        "tooling": tooling,
    }


_PERSON_NAME_RE = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+(?:[- ][A-Z][a-z]+)?)")


def _extract_founders(founding_body: str) -> list[dict[str, str]]:
    """Heuristic founder extraction from the Founding section's prose."""
    seen: list[str] = []
    out: list[dict[str, str]] = []
    for m in _PERSON_NAME_RE.finditer(founding_body):
        full = f"{m.group(1)} {m.group(2)}"
        if full in seen:
            continue
        # Filter common false positives.
        if any(stop in full for stop in ("Helix Logistics", "Helix ", "B2B")):
            continue
        seen.append(full)
        out.append({"name": full, "blurb": ""})
    return out


# ---------------------------------------------------------------------------
# Pass A2 — year-arc expansion
# ---------------------------------------------------------------------------


async def _pass_a2_year_arcs(
    llm: HelixLLM, skeleton: dict, data_dir: Path
) -> None:
    """Expand each year arc into a 2-3-paragraph narrative."""
    out_dir = data_dir / "helix_canon" / "year_arcs"
    out_dir.mkdir(parents=True, exist_ok=True)

    cp = Checkpoint(data_dir / "helix_canon" / ".checkpoints" / "a2.jsonl")

    template = _load_template("a2_year_arc.md")
    years = sorted(skeleton["year_arcs"].keys())
    founders_block = "\n".join(f"- {f['name']}" for f in skeleton["founders"])

    for year in years:
        unit_id = f"year-{year}"
        out_file = out_dir / f"{year}.md"
        if cp.is_done(unit_id) and out_file.exists():
            continue

        # Build the per-year context: adjacent years' themes for continuity,
        # tooling already adopted by that year.
        adj_years = [y for y in years if abs(y - year) <= 1 and y != year]
        adj_block = "\n".join(
            f"- {y}: {skeleton['year_arcs'][y]}" for y in adj_years
        )
        tooling_active = [
            f"- {t['description']} (adopted {t['year']})"
            for t in skeleton["tooling"]
            if t["year"] <= year
        ]
        tooling_block = "\n".join(tooling_active) if tooling_active else "- (none yet)"

        era = next(
            (e for e in skeleton["eras"]
             if int(e["start"][:4]) <= year <= int(e["end"][:4])),
            skeleton["eras"][0],
        )

        prompt = template.format(
            company_one_liner=COMPANY_ONE_LINER,
            founders_block=founders_block,
            year=year,
            era_name=era["name"],
            era_discipline_level=era["discipline_level"],
            year_theme=skeleton["year_arcs"][year],
            adjacent_years_block=adj_block or "(none)",
            tooling_block=tooling_block,
        )
        text = await llm.call_text(stage="A", user=prompt, max_tokens=3000)
        if not text.strip():
            logger.warning("A2 year %s returned empty content; skipping", year)
            continue
        out_file.write_text(text, encoding="utf-8")
        cp.mark_done(unit_id, year=year, chars=len(text))
        logger.info("A2 year %s written (%d chars)", year, len(text))


# ---------------------------------------------------------------------------
# Pass A3 — persona library (active + long-tail)
# ---------------------------------------------------------------------------


async def _pass_a3_personas(
    llm: HelixLLM, skeleton: dict, params: dict, data_dir: Path
) -> list[dict]:
    """Generate founder + active + long-tail + departed persona libraries.

    Four LLM calls:
    - A3-founders: P-0001 and P-0002 derived from the skeleton's founder
      info — first because the others need to know the founders exist.
    - A3a: active personas (current employees, rich voice profiles, with
      explicit leadership-team coverage and tenure spread).
    - A3b: long-tail personas (minor characters, sparser profiles).
    - A3c: departed personas (ex-employees who appear in old artefacts).

    Each parses N YAML documents from the response. Validates against
    :class:`helix_corpus.schemas.Persona`. Writes to
    data/helix_canon/personas.jsonl.
    """
    out_file = data_dir / "helix_canon" / "personas.jsonl"
    if out_file.exists():
        logger.info("A3 personas already present at %s, skipping", out_file)
        return [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    year_arcs_block = "\n".join(
        f"- {y}: {t}" for y, t in sorted(skeleton["year_arcs"].items())
    )
    eras_block = "\n".join(
        f"- Era {e['n']} {e['name']} ({e['start']} → {e['end']}, "
        f"{e['discipline_level']} discipline): {e['characterisation']}"
        for e in skeleton["eras"]
    )

    # Read the raw founding section from the skeleton's saved markdown
    # so we can hand the founder pass the verbatim blurb (names + voice
    # cues) the skeleton emitted.
    skeleton_md_path = data_dir / "helix_canon" / "skeleton.md"
    founding_section = ""
    if skeleton_md_path.exists():
        for s in parse_keyed_markdown(skeleton_md_path.read_text(encoding="utf-8")):
            if s.key.lower() == "founding":
                founding_section = s.body
                break
    if not founding_section:
        founding_section = ", ".join(f["name"] for f in skeleton["founders"])

    # --- A3-founders: generate P-0001 and P-0002 ---
    founders_template = _load_template("a3_personas_founders.md")
    founders_prompt = founders_template.format(
        company_one_liner=COMPANY_ONE_LINER,
        founding_section=founding_section,
        year_arcs_block=year_arcs_block,
        eras_block=eras_block,
    )
    founders_text = await llm.call_text(stage="A", user=founders_prompt, max_tokens=8000)
    founder_records = _parse_persona_yaml(founders_text, expected=2, is_long_tail=False)
    for p in founder_records:
        p.setdefault("is_founder", True)
    logger.info(
        "A3 founders: parsed %d / 2 expected (names: %s)",
        len(founder_records),
        ", ".join(p.get("display_name", "?") for p in founder_records),
    )

    # --- A3a: active personas (excluding founders) ---
    founders_block = "\n".join(
        f"- {p['persona_id']} {p.get('display_name', '?')} — "
        f"{p.get('role_history', [{}])[0].get('role', '?')}"
        for p in founder_records
    )
    active_template = _load_template("a3_personas_active.md")
    active_prompt = active_template.format(
        company_one_liner=COMPANY_ONE_LINER,
        founders_block=founders_block,
        year_arcs_block=year_arcs_block,
        eras_block=eras_block,
        persona_count=params["active_personas"],
    )
    # A3 active is a structured-fill task: fit N personas into a strict
    # schema with role + tenure coverage constraints. Treating it as a
    # creative-reasoning task burns the output budget on internal
    # planning before any YAML emerges. Use low reasoning_effort + a
    # very generous output budget.
    active_text = await llm.call_text(
        stage="A",
        user=active_prompt,
        reasoning_effort="low",
        max_tokens=24000,
    )
    active_records = _parse_persona_yaml(active_text, expected=params["active_personas"], is_long_tail=False)
    logger.info("A3 active: parsed %d / %d expected", len(active_records), params["active_personas"])
    if len(active_records) == 0:
        # Hard fail — long-tail and departed numbering needs active
        # records to anchor against; without them we get weird ID jumps.
        raise RuntimeError(
            "A3 active produced zero parseable persona records. "
            "Inspect the raw output and re-run. Likely causes: prompt "
            "too long, reasoning_effort too high, max_tokens too low."
        )

    # --- A3b: long-tail personas ---
    longtail_template = _load_template("a3_personas_longtail.md")
    active_summary = "\n".join(
        f"- {p['persona_id']} {p['display_name']}" for p in active_records
    )
    longtail_prompt = longtail_template.format(
        company_one_liner=COMPANY_ONE_LINER,
        active_personas_summary=active_summary,
        persona_count=params["longtail_personas"],
    )
    longtail_text = await llm.call_text(
        stage="A",
        user=longtail_prompt,
        reasoning_effort="low",
        max_tokens=24000,
    )
    longtail_records = _parse_persona_yaml(longtail_text, expected=params["longtail_personas"], is_long_tail=True)
    logger.info("A3 long-tail: parsed %d / %d expected", len(longtail_records), params["longtail_personas"])

    # --- A3c: departed personas (ex-employees) ---
    departed_template = _load_template("a3_personas_departed.md")
    existing_cast_summary = "\n".join(
        f"- {p['persona_id']} {p['display_name']}"
        for p in active_records + longtail_records
    )
    founding_year = skeleton["founding_year"]
    departed_prompt = departed_template.format(
        company_one_liner=COMPANY_ONE_LINER,
        year_arcs_block=year_arcs_block,
        existing_cast_summary=existing_cast_summary,
        persona_count=params["departed_personas"],
        min_departure_year=founding_year + 1,  # earliest plausible departure
        max_departure_year=CURRENT_YEAR - 1,   # left before now
    )
    departed_text = await llm.call_text(
        stage="A",
        user=departed_prompt,
        reasoning_effort="low",
        max_tokens=24000,
    )
    departed_records = _parse_persona_yaml(
        departed_text, expected=params["departed_personas"], is_long_tail=True,
    )
    # Departed personas carry an extra field (`left_year`); record it
    # explicitly on the dict for downstream consumption even though the
    # Pydantic Persona schema doesn't have a slot for it.
    for p in departed_records:
        p.setdefault("is_departed", True)
    logger.info(
        "A3 departed: parsed %d / %d expected",
        len(departed_records), params["departed_personas"],
    )

    all_records = founder_records + active_records + longtail_records + departed_records
    _enforce_persona_invariants(all_records, params)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for p in all_records:
            f.write(json.dumps(p, default=str) + "\n")
    logger.info(
        "A3 personas written: %d total (%d founders + %d active + %d long-tail + %d departed)",
        len(all_records), len(founder_records), len(active_records),
        len(longtail_records), len(departed_records),
    )
    return all_records


def _parse_persona_yaml(text: str, *, expected: int, is_long_tail: bool) -> list[dict]:
    """Parse the YAML-multi-doc persona output.

    Validates each record against :class:`Persona`. Drops records that
    fail validation (logs the failure). Tolerant — if we got 14 valid
    out of 15 expected, the caller's invariant check decides whether to
    proceed.
    """
    raw_docs = parse_yaml_lenient(text)
    out: list[dict] = []
    for i, doc in enumerate(raw_docs):
        # Tolerant normalisation: gpt-oss sometimes omits is_long_tail
        # and uses joined_year as either int or string.
        doc.setdefault("is_long_tail", is_long_tail)
        if "joined_year" in doc and isinstance(doc["joined_year"], str):
            try:
                doc["joined_year"] = int(doc["joined_year"])
            except ValueError:
                pass
        # Tolerant normalisation: gpt-oss sometimes uses 'left_year' in
        # long-tail records (which the long-tail prompt requests). The
        # base Persona schema doesn't have that field; we keep it as an
        # extra attribute for downstream use rather than dropping.
        try:
            Persona(**{k: v for k, v in doc.items() if k != "left_year"})
            out.append(doc)
        except ValidationError as exc:
            logger.warning(
                "A3 persona %d failed Pydantic validation: %s. Doc: %s",
                i, exc, json.dumps(doc, default=str)[:300],
            )
    return out


def _enforce_persona_invariants(records: list[dict], params: dict) -> None:
    """Code-validation per design doc §5 — raises if invariants fail."""
    active = [p for p in records if not p.get("is_long_tail")]
    longtail = [p for p in records if p.get("is_long_tail")]

    if len(active) < params["active_personas"]:
        logger.warning(
            "A3 active persona count below target: %d < %d",
            len(active), params["active_personas"],
        )
    if len(longtail) < params["longtail_personas"]:
        logger.warning(
            "A3 long-tail persona count below target: %d < %d",
            len(longtail), params["longtail_personas"],
        )

    # Signature-phrase dedup across the whole library
    seen_phrases: dict[str, str] = {}
    for p in records:
        for phrase in p.get("signature_phrases", []):
            key = phrase.lower().strip()
            if key in seen_phrases and seen_phrases[key] != p["persona_id"]:
                logger.warning(
                    "A3 signature-phrase collision: %r appears in both "
                    "%s and %s",
                    phrase, seen_phrases[key], p["persona_id"],
                )
            else:
                seen_phrases[key] = p["persona_id"]


# ---------------------------------------------------------------------------
# Pass A4 — customer arcs
# ---------------------------------------------------------------------------


_NARRATIVE_ROLES = [
    "design_partner", "near_churn", "happy_reference", "difficult_escalation",
    "expansion", "biggest_contract", "contracts_redline_drama",
    "design_partner", "happy_reference", "near_churn",
    "expansion", "happy_reference", "biggest_contract", "design_partner",
    "difficult_escalation", "happy_reference", "expansion", "near_churn",
    "happy_reference", "design_partner",
]

# Historical-customer outcome categories — cycle through these so the
# batch has a mix of failure modes.
_HISTORICAL_OUTCOMES = [
    "churned",
    "lost_at_pitch",
    "design_partner_left",
    "never_renewed_after_pilot",
    "acquired_out_of_business",
    "churned",
    "lost_at_pitch",
    "design_partner_left",
    "contract_dispute",
    "churned",
    "never_renewed_after_pilot",
    "lawsuit_separation",
    "lost_at_pitch",
    "churned",
    "design_partner_left",
    "never_renewed_after_pilot",
    "acquired_out_of_business",
    "contract_dispute",
    "lost_at_pitch",
    "churned",
]


async def _pass_a4_customers(
    llm: HelixLLM, skeleton: dict, params: dict, data_dir: Path
) -> list[dict]:
    """Generate active customer arcs.

    Active customers are currently-paying named accounts. Historical
    customers (churned / lost / dropped) come from :func:`_pass_a4b_historical_customers`.
    """
    out_file = data_dir / "helix_canon" / "customers.jsonl"
    cp = Checkpoint(data_dir / "helix_canon" / ".checkpoints" / "a4.jsonl")

    existing: list[dict] = []
    if out_file.exists():
        existing = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    template = _load_template("a4_customer_arc.md")
    target = params["active_customers"]
    founding_year = skeleton["founding_year"]
    year_arcs_block = "\n".join(
        f"- {y}: {t}" for y, t in sorted(skeleton["year_arcs"].items())
    )

    customers: list[dict] = list(existing)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    while len(customers) < target:
        idx = len(customers) + 1
        unit_id = f"customer-{idx}"
        if cp.is_done(unit_id):
            continue

        narrative_role = _NARRATIVE_ROLES[(idx - 1) % len(_NARRATIVE_ROLES)]
        first_year = founding_year + ((idx - 1) % 4)
        existing_block = "\n".join(
            f"- {c['customer_id']} {c.get('name','?')}: {c.get('industry','?')}"
            for c in customers
        ) or "(none yet)"

        prompt = template.format(
            company_one_liner=COMPANY_ONE_LINER,
            year_arcs_block=year_arcs_block,
            existing_customers_block=existing_block,
            customer_index=idx,
            total_customers=target,
            narrative_role=narrative_role,
            first_year=first_year,
            current_year=CURRENT_YEAR,
            customer_index_padded=f"{idx:04d}",
        )
        text = await llm.call_text(stage="A", user=prompt, max_tokens=3000)
        parsed = parse_yaml_lenient(text)
        if not parsed:
            logger.warning("A4 active customer %d returned no parseable YAML; retrying once", idx)
            text2 = await llm.call_text(
                stage="A",
                user=prompt + "\n\nIMPORTANT: emit ONLY one YAML document, no prose preamble.",
                max_tokens=3000,
            )
            parsed = parse_yaml_lenient(text2)
            if not parsed:
                logger.error("A4 active customer %d failed twice — skipping", idx)
                continue

        record = parsed[0]
        record.setdefault("is_active", True)
        try:
            CustomerArc(**{k: v for k, v in record.items() if k != "is_active"})
        except ValidationError as exc:
            logger.warning("A4 active customer %d failed Pydantic validation: %s", idx, exc)
        customers.append(record)
        with out_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        cp.mark_done(unit_id, customer_id=record.get("customer_id"))
        logger.info("A4 active customer %d/%d written: %s", idx, target, record.get("name", "?"))

    return customers


async def _pass_a4b_historical_customers(
    llm: HelixLLM,
    skeleton: dict,
    params: dict,
    active_customers: list[dict],
    data_dir: Path,
) -> list[dict]:
    """Generate historical (churned / lost / dropped) customer arcs.

    These customers are not currently active — they exist to populate
    the corpus with realistic references like "remember the Sterling
    deal that fell apart in 2023." Each has a terminal `last_year` and
    an `outcome` field that explains how they left.
    """
    out_file = data_dir / "helix_canon" / "historical_customers.jsonl"
    cp = Checkpoint(data_dir / "helix_canon" / ".checkpoints" / "a4b.jsonl")

    existing: list[dict] = []
    if out_file.exists():
        existing = [
            json.loads(line)
            for line in out_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    template = _load_template("a4_historical_customer.md")
    target = params["historical_customers"]
    founding_year = skeleton["founding_year"]
    year_arcs_block = "\n".join(
        f"- {y}: {t}" for y, t in sorted(skeleton["year_arcs"].items())
    )
    active_block = "\n".join(
        f"- {c['customer_id']} {c.get('name','?')}: {c.get('industry','?')}"
        for c in active_customers
    ) or "(none)"

    historical: list[dict] = list(existing)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    start_id = len(active_customers) + 1

    while len(historical) < target:
        local_idx = len(historical)  # 0-based within historical
        global_idx = start_id + local_idx  # 1-based global
        unit_id = f"historical-customer-{local_idx + 1}"
        if cp.is_done(unit_id):
            continue

        outcome = _HISTORICAL_OUTCOMES[local_idx % len(_HISTORICAL_OUTCOMES)]
        # Plausible tenure: scatter across the company's history
        first_year = founding_year + (local_idx % (CURRENT_YEAR - founding_year))
        max_tenure = CURRENT_YEAR - first_year - 1
        tenure = 1 if max_tenure < 1 else min(1 + (local_idx % max(1, max_tenure)), max_tenure)
        last_year = first_year + tenure

        existing_hist_block = "\n".join(
            f"- {c['customer_id']} {c.get('name','?')}: {c.get('outcome','?')}"
            for c in historical
        ) or "(none yet)"

        prompt = template.format(
            company_one_liner=COMPANY_ONE_LINER,
            year_arcs_block=year_arcs_block,
            active_customers_block=active_block,
            existing_historical_block=existing_hist_block,
            customer_index=local_idx + 1,
            total_historical=target,
            outcome_category=outcome,
            first_year=first_year,
            last_year=last_year,
            customer_index_padded=f"{global_idx:04d}",
        )
        text = await llm.call_text(stage="A", user=prompt, max_tokens=3000)
        parsed = parse_yaml_lenient(text)
        if not parsed:
            logger.warning(
                "A4b historical customer %d (%s) returned no parseable YAML; retrying once",
                local_idx + 1, outcome,
            )
            text2 = await llm.call_text(
                stage="A",
                user=prompt + "\n\nIMPORTANT: emit ONLY one YAML document, no prose preamble.",
                max_tokens=3000,
            )
            parsed = parse_yaml_lenient(text2)
            if not parsed:
                logger.error("A4b historical customer %d failed twice — skipping", local_idx + 1)
                continue

        record = parsed[0]
        record.setdefault("is_active", False)
        record.setdefault("outcome", outcome)
        historical.append(record)
        with out_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        cp.mark_done(unit_id, customer_id=record.get("customer_id"), outcome=outcome)
        logger.info(
            "A4b historical customer %d/%d written: %s (outcome=%s)",
            local_idx + 1, target, record.get("name", "?"), outcome,
        )

    return historical


# ---------------------------------------------------------------------------
# Pass A5 — persona critique
# ---------------------------------------------------------------------------


async def _pass_a5_critique(
    llm: HelixLLM, personas: list[dict], data_dir: Path
) -> None:
    """One critique pass over the persona library.

    For v0.x: we log collisions but do NOT auto-loop revisions. If
    collisions are reported, the user reviews them at the Phase 2 gate
    and decides whether to regenerate.
    """
    out_file = data_dir / "helix_canon" / "persona_critique.md"
    if out_file.exists():
        logger.info("A5 critique already present at %s, skipping", out_file)
        return

    template = _load_template("a5_persona_critique.md")
    # Compact persona block — just the fields the critique reads
    persona_lines = []
    for p in personas:
        phrases = "; ".join(p.get("signature_phrases", [])[:5])
        vm = p.get("voice_markers", {})
        persona_lines.append(
            f"- {p['persona_id']} {p.get('display_name', '?')}: "
            f"hedging={vm.get('hedging_frequency', '?')} "
            f"formality={vm.get('formality', '?')} "
            f"emoji={vm.get('emoji_use', '?')} "
            f"length={vm.get('typical_message_length_words', '?')}; "
            f"expertise={','.join(p.get('domain_expertise', []))}; "
            f"phrases={phrases!r}"
        )
    personas_block = "\n".join(persona_lines)

    prompt = template.format(personas_block=personas_block)
    # Critique is a mechanical comparison task — low reasoning effort
    # is fine, but we give it generous output budget because the
    # collision list could be long and we don't want it truncated.
    text = await llm.call_text(
        stage="A",
        user=prompt,
        reasoning_effort="low",
        max_tokens=8000,
    )
    text = strip_code_fences(text).strip()
    out_file.write_text(text, encoding="utf-8")

    if not text:
        logger.warning(
            "A5 critique returned EMPTY content — treating as inconclusive. "
            "Manually re-run if persona-collision review is critical."
        )
    elif text == "NO_COLLISIONS":
        logger.info("A5 critique: no persona collisions detected.")
    else:
        n_lines = sum(1 for line in text.splitlines() if line.strip())
        logger.info(
            "A5 critique: %d collision(s) reported. Inspect %s.",
            n_lines, out_file,
        )


# ---------------------------------------------------------------------------
# Pass A6 — Company history depth (messy emotional arcs)
# ---------------------------------------------------------------------------


async def _pass_a6_depth_arcs(
    llm: HelixLLM,
    skeleton: dict,
    personas: list[dict],
    active_customers: list[dict],
    historical_customers: list[dict],
    params: dict,
    data_dir: Path,
) -> None:
    """Generate emotional / messy / dropped-context backstory arcs.

    These don't directly map to ground-truth question targets; they
    populate the "ambient texture" the corpus will reference. Stage C
    will read these arcs when generating retrospectives, postmortems,
    and Slack threads that need to reference *something* off-stage to
    feel real (failed fundraises, near-pivots, lost-the-pitch deals,
    political fights, lunch-that-became-a-hire stories, etc).

    Single LLM call generates ``depth_arcs`` arcs in one go (cheaper
    than per-arc calls and lets gpt-oss balance pattern variety
    within one response).
    """
    out_file = data_dir / "helix_canon" / "depth_arcs.md"
    if out_file.exists():
        logger.info("A6 depth arcs already present at %s, skipping", out_file)
        return

    template = _load_template("a6_depth_arcs.md")

    year_arcs_block = "\n".join(
        f"- {y}: {t}" for y, t in sorted(skeleton["year_arcs"].items())
    )
    personas_block = "\n".join(
        f"- {p['persona_id']} {p.get('display_name', '?')} "
        f"({p.get('role_history', [{}])[0].get('role', '?')})"
        for p in personas
    )
    customers_block = "\n".join(
        f"- {c.get('customer_id', '?')} {c.get('name', '?')} "
        f"({c.get('outcome', 'active')})"
        for c in active_customers + historical_customers
    )

    # Generous output budget — N arcs × ~250 tokens each + reasoning
    # overhead. 2x to be safe per gpt-oss reasoning behaviour.
    n = params["depth_arcs"]
    budget = max(6000, n * 600)

    prompt = template.format(
        company_one_liner=COMPANY_ONE_LINER,
        year_arcs_block=year_arcs_block,
        personas_block=personas_block,
        customers_block=customers_block,
        arc_count=n,
        min_year=skeleton["founding_year"],
        max_year=CURRENT_YEAR,
    )
    text = await llm.call_text(
        stage="A",
        user=prompt,
        reasoning_effort="medium",
        max_tokens=budget,
    )
    text = strip_code_fences(text).strip()
    if not text:
        logger.warning("A6 depth arcs returned empty content")
        out_file.write_text("# A6 depth arcs — EMPTY (regenerate)\n", encoding="utf-8")
        return

    out_file.write_text(text, encoding="utf-8")
    n_arcs_found = text.count("## ARC:")
    logger.info(
        "A6 depth arcs written: %d arcs detected (target %d, budget %d tokens)",
        n_arcs_found, n, budget,
    )


# ---------------------------------------------------------------------------
# Pass A7 — Channel timeline (Slack channel lifecycle over the company's life)
# ---------------------------------------------------------------------------


# Team set for the channel timeline (matches Stage B Large team_set).
_CHANNEL_TEAMS = [
    "Engineering", "Sales", "Product", "Customer Success",
    "Operations", "Marketing", "Finance", "People",
]


def _parse_channels(text: str) -> list[dict]:
    """Parse the A7 channel timeline robustly.

    gpt-oss inconsistently separates the per-channel YAML blocks — some
    runs use ``---`` separators, others just blank lines. Relying on a
    single YAML parse collapses blank-line-separated blocks into one
    document with duplicate keys (keeping only the last channel). So we
    split on each ``channel:`` line (every record starts with one) and
    parse each block's simple ``key: value`` pairs ourselves.
    """
    text = strip_code_fences(normalize_smart_quotes(text))
    # Split into blocks: each block starts at a line beginning "channel:".
    lines = text.splitlines()
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        if re.match(r"^\s*channel\s*:", ln):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        blocks.append(cur)

    channels: list[dict] = []
    for blk in blocks:
        rec: dict[str, Any] = {}
        for ln in blk:
            m = re.match(r"^\s*([a-zA-Z_]+)\s*:\s*(.*)$", ln)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            val = val.strip().strip('"').strip("'")
            if val.lower() in ("null", "none", ""):
                val = None
            elif key == "peak_years":
                yrs = re.findall(r"\d{4}", val)
                val = [int(y) for y in yrs]
            rec[key] = val
        if rec.get("channel"):
            channels.append(rec)
    return channels


async def _pass_a7_channel_timeline(
    llm: HelixLLM, skeleton: dict, data_dir: Path,
) -> None:
    """Generate the Slack channel lifecycle (channels born / renamed /
    archived across 2020-2026). Backbone for Stage C2 atmosphere — the
    atmosphere generator only writes into channels alive in a given
    month.

    One LLM call. Cheap. Runs for any size (used by Large's atmosphere;
    harmless for Small/Medium).
    """
    out_file = data_dir / "helix_canon" / "channel_timeline.jsonl"
    if out_file.exists():
        logger.info("A7 channel_timeline already present at %s, skipping", out_file)
        return

    year_arcs_block = "\n".join(
        f"- {y}: {t}" for y, t in sorted(skeleton["year_arcs"].items())
    )
    eras_block = "\n".join(
        f"- Era {e['n']} {e['name']} ({e['start']}→{e['end']}, {e['discipline_level']}): "
        f"{e['characterisation']}"
        for e in skeleton["eras"]
    )
    tooling_block = "\n".join(
        f"- {t['year']}{'-Q'+str(t['quarter']) if t.get('quarter') else ''}: {t['description']}"
        for t in skeleton["tooling"]
    )
    teams_block = "\n".join(f"- {t}" for t in _CHANNEL_TEAMS)

    prompt = _load_template("a7_channel_timeline.md").format(
        company_one_liner=COMPANY_ONE_LINER,
        year_arcs_block=year_arcs_block,
        eras_block=eras_block,
        tooling_block=tooling_block,
        teams_block=teams_block,
        current_year=CURRENT_YEAR,
    )
    text = await llm.call_text(
        stage="A",
        user=prompt,
        reasoning_effort="low",
        max_tokens=10000,
    )
    channels = _parse_channels(text)
    if not channels:
        logger.warning("A7 channel_timeline returned no parseable channels")
        return

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for c in channels:
            f.write(json.dumps(c, default=str) + "\n")
    archived = sum(1 for c in channels if c.get("archived"))
    renamed = sum(1 for c in channels if c.get("renamed_from"))
    logger.info(
        "A7 channel_timeline written: %d channels (%d archived, %d renamed)",
        len(channels), archived, renamed,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run(*, size: str, data_dir: str) -> None:
    """Run all passes of Stage A.

    Artefacts under ``{data_dir}/helix_canon/``:

    - ``skeleton.md`` + ``skeleton.json`` — A1 output (raw + parsed).
    - ``year_arcs/<year>.md`` — A2 per-year narratives.
    - ``personas.jsonl`` — A3 active + long-tail + departed personas
      (one record per line).
    - ``customers.jsonl`` — A4 active customer arcs.
    - ``historical_customers.jsonl`` — A4b churned / lost / dropped
      customer arcs.
    - ``persona_critique.md`` — A5 collision report (or ``NO_COLLISIONS``).
    - ``depth_arcs.md`` — A6 messy / emotional / failed-arc narratives
      that the corpus will reference as off-stage ambient context.
    - ``.checkpoints/`` — resume state per pass.
    """
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size: {size}; expected one of {list(SIZE_PARAMS)}")
    params = SIZE_PARAMS[size]

    data_root = Path(data_dir)
    data_root.mkdir(parents=True, exist_ok=True)

    llm = HelixLLM()
    try:
        skeleton = await _pass_a1_skeleton(llm, params, data_root)
        await _pass_a2_year_arcs(llm, skeleton, data_root)
        personas = await _pass_a3_personas(llm, skeleton, params, data_root)
        active_customers = await _pass_a4_customers(llm, skeleton, params, data_root)
        historical_customers = await _pass_a4b_historical_customers(
            llm, skeleton, params, active_customers, data_root,
        )
        await _pass_a5_critique(llm, personas, data_root)
        await _pass_a6_depth_arcs(
            llm, skeleton, personas, active_customers, historical_customers,
            params, data_root,
        )
        await _pass_a7_channel_timeline(llm, skeleton, data_root)
        logger.info("Stage A complete.")
    finally:
        await llm.aclose()
