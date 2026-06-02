"""Stage G — Emergent-pattern questions (Tier 3, deeply nuanced).

The hardest class of question: the answer was NEVER written down. It is a
de-facto pattern that must be reconstructed from how people actually
behaved over years — scattered across Slack, meetings, calls, retros,
often before any formal version existed. "What was the onboarding
approach before the playbook?" has no document to retrieve; you infer the
implicit playbook from dozens of behaviours, and must not confuse it with
the late formalisation.

Per theme:
1. gpt-oss DEFINES the pattern grounded in canon: a surface-simple
   question, a temporal qualifier, the (wrong-answer) formalisation, a
   synthesised GT answer, and 4-6 FACETS — each a concrete behaviour.
2. gpt-oss SEEDS evidence: for each facet, a few short artefacts that
   *exhibit* it (never state it), scattered across the relevant years,
   genres and authors, mixed into the corpus as role="emergent_evidence".
3. We assemble an EMERGENT question: surface-simple text, GT answer =
   the facet set, rubric = one sub-point per facet + a synthesis
   sub-point + a distractor sub-point (don't answer with the formal
   version). evidence_artefact_ids = the seeded artefacts.

Validation is union-mode (Stage F): the question passes when every facet
is present in at least ONE of its evidence artefacts (the answer is
spread; no single artefact suffices).

Appends to corpus_index.jsonl + writes emergent_questions.jsonl. Additive;
does not touch events.jsonl (safe to run alongside / after B6).
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from helix_corpus.checkpoint import Checkpoint
from helix_corpus.llm import HelixLLM
from helix_corpus.parsers import strip_code_fences, normalize_smart_quotes

logger = logging.getLogger("helix_corpus.stage_g")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_g"
COMPANY_ONE_LINER = (
    "Helix Logistics: B2B SaaS for mid-market freight-forwarding "
    "companies, founded in 2020, ~85 employees by 2025."
)
_EVIDENCE_GENRES = ["slack_thread", "meeting_notes", "email_thread", "customer_call_notes", "retro_note"]

# Emergent-pattern themes (scaffolding — gpt-oss fills each with a
# concrete, canon-grounded pattern). Deliberately varied in subtlety.
THEMES: list[str] = [
    "the de-facto customer-onboarding approach before any onboarding playbook existed",
    "how engineering actually made architecture decisions before the ADR process",
    "who the de-facto technical authority was during the 2022 hypergrowth, regardless of title",
    "what customers consistently struggled with in the early years, before it was tracked as a metric",
    "the company's real attitude to technical debt before any written policy",
    "how pricing and discounts were actually decided before a pricing model existed",
    "the informal path for who got pulled into production incidents before the on-call rotation",
    "the early warning signs shared by customers who eventually churned, before churn risk was flagged",
    "how communication norms shifted after the 2023 layoff, though no one announced a change",
    "the de-facto hiring bar — what kind of people Helix actually hired early vs later",
    "the recurring mid-market objection sales kept hearing that quietly shaped the roadmap",
    "the real reason the v3 rewrite stalled, beyond the stated reason",
    "how the team actually decided what to build before formal product prioritisation",
    "the company's evolving real attitude to documentation over time",
    "which customer relationships were quietly at risk in 2024 despite healthy dashboards",
    "the de-facto definition of 'done' on the engineering team before any written standard",
    "how the company really handled its first major outage, culturally as well as technically",
    "the unwritten norm about who interacted with investors and how",
    "the de-facto QA / testing discipline before any formal testing requirement",
    "how cross-team collaboration between sales and engineering actually worked in practice",
    "the real meeting culture — which meetings mattered and which were theatre",
    "how budget and spend decisions actually got made before finance discipline arrived",
    "the unspoken product principles that guided what got built and what got rejected",
    "how bugs were actually prioritised against features in practice",
    "what the real onboarding experience was for new engineers joining the team",
    "the de-facto ownership of customer relationships across sales, CS and founders",
    "the company's real risk appetite, shown in the bets it made and avoided",
    "how the team actually responded to competitor moves over the years",
    "the informal escalation norms when a customer was unhappy, before a formal process",
    "how the company's tone with customers shifted as it moved from B2C to mid-market",
]

SIZE_PARAMS: dict[str, dict[str, int]] = {
    "small":  {"n_patterns": 3,  "evidence_per_facet": 2},
    "medium": {"n_patterns": 8,  "evidence_per_facet": 2},
    "large":  {"n_patterns": 30, "evidence_per_facet": 2},
}


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_canon(data_dir: Path) -> dict[str, Any]:
    canon = data_dir / "helix_canon"
    skeleton = json.loads((canon / "skeleton.json").read_text(encoding="utf-8"))
    personas = [
        json.loads(l) for l in (canon / "personas.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {"skeleton": skeleton, "personas": personas}


def _year_arcs_block(skeleton: dict) -> str:
    return "\n".join(f"- {y}: {t}" for y, t in sorted(skeleton.get("year_arcs", {}).items()))


def _personas_block(personas: list[dict], limit: int = 30) -> str:
    out = []
    for p in personas[:limit]:
        role = (p.get("role_history") or [{}])[0].get("role", "?")
        out.append(f"- {p.get('display_name','?')} ({role})")
    return "\n".join(out)


def _parse_pattern(text: str) -> dict | None:
    text = strip_code_fences(normalize_smart_quotes(text))
    rec: dict[str, Any] = {"facets": []}
    in_facets = False
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^(QUESTION|TEMPORAL_QUALIFIER|FORMALIZATION|GT_ANSWER|FACETS)\s*:\s*(.*)$", s, re.I)
        if m:
            key = m.group(1).upper()
            if key == "FACETS":
                in_facets = True
                continue
            in_facets = False
            rec[key.lower()] = m.group(2).strip()
        elif in_facets:
            fm = re.match(r"^\d+[.)]\s*(.+)$", s) or re.match(r"^[-*]\s*(.+)$", s)
            if fm:
                rec["facets"].append(fm.group(1).strip())
    if rec.get("question") and len(rec["facets"]) >= 2:
        return rec
    return None


def _years_from_qualifier(qualifier: str, skeleton: dict) -> list[int]:
    yrs = sorted(int(y) for y in skeleton.get("year_arcs", {}).keys())
    found = [int(y) for y in re.findall(r"\b(20\d{2})\b", qualifier or "")]
    if len(found) >= 2:
        lo, hi = min(found), max(found)
        return [y for y in yrs if lo <= y <= hi] or yrs
    if len(found) == 1:
        return [y for y in yrs if y <= found[0]] or yrs
    return yrs


async def run(*, size: str, data_dir: str) -> None:
    if size not in SIZE_PARAMS:
        raise ValueError(f"unknown size {size}")
    params = SIZE_PARAMS[size]
    data_root = Path(data_dir)
    canon = _load_canon(data_root)
    skeleton = canon["skeleton"]
    yblock = _year_arcs_block(skeleton)
    pblock = _personas_block(canon["personas"])

    em_dir = data_root / "corpus" / "_emergent"
    em_dir.mkdir(parents=True, exist_ok=True)
    index_file = data_root / "corpus_index.jsonl"
    q_file = data_root / "emergent_questions.jsonl"
    cp = Checkpoint(data_root / ".checkpoints" / "stage_g.jsonl")

    themes = THEMES[: params["n_patterns"]]
    rng = random.Random(47)
    llm = HelixLLM()
    n_written = 0
    try:
        for ti, theme in enumerate(themes):
            unit = f"pattern-{ti}"
            if cp.is_done(unit):
                continue
            # 1. define pattern
            dprompt = _load_template("define_pattern.md").format(
                company_one_liner=COMPANY_ONE_LINER, year_arcs_block=yblock,
                personas_block=pblock, theme=theme,
            )
            dtext = await llm.call_text(stage="E", user=dprompt, reasoning_effort="medium", max_tokens=2500)
            pat = _parse_pattern(dtext)
            if not pat:
                logger.warning("G pattern %d (%s): unparseable — skipping", ti, theme[:40])
                cp.mark_done(unit, status="skip-parse")
                continue
            facets = pat["facets"][:6]
            years = _years_from_qualifier(pat.get("temporal_qualifier", ""), skeleton)

            # 2. seed evidence per facet
            evidence_ids: list[str] = []
            facet_to_ids: dict[int, list[str]] = {}
            pdir = em_dir / f"P{ti:02d}"
            pdir.mkdir(parents=True, exist_ok=True)
            for fi, facet in enumerate(facets):
                facet_to_ids[fi] = []
                for k in range(params["evidence_per_facet"]):
                    genre = _EVIDENCE_GENRES[(fi + k) % len(_EVIDENCE_GENRES)]
                    year = rng.choice(years)
                    adate = f"{year}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
                    sprompt = _load_template("seed_evidence.md").format(
                        company_one_liner=COMPANY_ONE_LINER, facet=facet,
                        temporal_qualifier=pat.get("temporal_qualifier", ""),
                        artefact_date=adate, genre=genre, personas_block=pblock,
                    )
                    text = await llm.call_text(stage="C", user=sprompt, reasoning_effort="low", max_tokens=1500)
                    if not text.strip():
                        continue
                    slot_id = f"EMG-P{ti:02d}-F{fi}-{k}"
                    out_path = pdir / f"{slot_id}.md"
                    out_path.write_text(
                        f"<!-- emergent_evidence pattern=P{ti:02d} facet={fi} {adate} role=emergent_evidence -->\n\n" + text,
                        encoding="utf-8",
                    )
                    with index_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "slot_id": slot_id, "event_id": None, "role": "emergent_evidence",
                            "genre": "slack_thread" if "slack" in genre else genre,
                            "emergent_pattern": f"P{ti:02d}", "facet": fi, "author": None,
                            "path": str(out_path.relative_to(data_root)), "chars": len(text),
                        }, default=str) + "\n")
                    evidence_ids.append(slot_id)
                    facet_to_ids[fi].append(slot_id)

            if not evidence_ids:
                cp.mark_done(unit, status="skip-no-evidence")
                continue

            # 3. assemble EMERGENT question + facet rubric
            rubric = []
            per_facet_w = round(0.7 / max(1, len(facets)), 3)
            for fi, facet in enumerate(facets):
                rubric.append({
                    "id": f"EMERGENT.sub{fi+1}", "weight": per_facet_w,
                    "criterion": f"Identifies the facet: {facet[:160]}",
                    "fail_if": "facet absent from the answer",
                    "facet_index": fi,
                    "evidence_ids": facet_to_ids.get(fi, []),
                })
            rubric.append({
                "id": f"EMERGENT.sub{len(facets)+1}", "weight": 0.2,
                "criterion": "Synthesises the facets into the de-facto pattern (not a list of disconnected facts)",
                "fail_if": "answer is a disconnected list / quotes one artefact only",
            })
            rubric.append({
                "id": f"EMERGENT.sub{len(facets)+2}", "weight": 0.1,
                "criterion": "Answers the DE-FACTO pattern for the period asked, not a later formal version",
                "fail_if": f"answers with the formal version: {pat.get('formalization','')[:160]}",
            })
            qid = f"Q-EMG-{ti:04d}"
            record = {
                "id": qid, "category": "EMERGENT", "difficulty": "hard",
                "text": pat["question"],
                "paraphrases": [pat["question"]],
                "ground_truth_answer": {
                    "gt_answer": pat.get("gt_answer", ""),
                    "facets": facets,
                    "temporal_qualifier": pat.get("temporal_qualifier", ""),
                    "formalization": pat.get("formalization", ""),
                },
                "rubric_subpoints": rubric,
                "evidence_artefact_ids": evidence_ids,
                "metadata": {"emergent": True, "n_facets": len(facets), "theme": theme,
                             "validation_mode": "union"},
            }
            with q_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            cp.mark_done(unit, status="ok", facets=len(facets), evidence=len(evidence_ids))
            n_written += 1
            logger.info("G pattern %d/%d '%s...': %d facets, %d evidence artefacts",
                        ti + 1, len(themes), theme[:40], len(facets), len(evidence_ids))

        logger.info("Stage G complete. %d emergent questions written.", n_written)
    finally:
        await llm.aclose()
