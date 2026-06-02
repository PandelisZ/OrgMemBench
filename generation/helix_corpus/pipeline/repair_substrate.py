"""Substrate repair pass.

After Stage F's per-artefact substrate check, some artefacts score
below the completeness threshold — the generation prompt failed to
embed all the canonical facts the artefact's slot was supposed to
carry (most often long meeting_transcripts where gpt-oss buried or
dropped the decision / date / participant names).

This pass repairs them so the ground-truth information is GUARANTEED
present in the corpus — the whole point of the benchmark is that a
future memory system can recover the ground truth from the corpus, so
the corpus must actually contain it.

Two-tier repair per deficient artefact:

1. **gpt-oss regeneration** (natural): re-prompt with the original
   artefact + the exact missing facts + "MUST contain every fact",
   re-run the substrate check. Up to 2 attempts.

2. **Deterministic append** (guaranteed fallback): if gpt-oss still
   can't get every fact in after 2 attempts, append a clearly-marked
   "Reference details" section containing the missing facts verbatim.
   This is less natural but GUARANTEES the corpus contains the
   ground-truth pieces. Marked with an HTML comment so it's auditable.

After repair, the artefact_validation_report is updated in place and
the question-level roll-up is recomputed (callers should re-run the
Stage F question pass, or this module's recompute helper).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from helix_corpus.llm import HelixLLM
from helix_corpus.pipeline.stage_c_corpus import (
    _GENRE_TESTIMONY_TYPE,
    _testimony_header,
)
from helix_corpus.pipeline.stage_f_validate import (
    _canonical_facts_for_artefact,
    _check_artefact_substrate,
    _load_template as _load_f_template,
)

logger = logging.getLogger("helix_corpus.repair")

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "stage_c"
REPAIR_THRESHOLD = 0.7
MAX_GPT_ATTEMPTS = 2

# Strip any testimony_metadata header from artefact text before repair
# (the pipeline re-adds a fresh one).
_HEADER_RE = re.compile(r"^<!--\s*artefact_metadata.*?-->\s*", re.DOTALL)


def _load_repair_template() -> str:
    return (_PROMPTS_DIR / "repair_artefact.md").read_text(encoding="utf-8")


def _strip_header(text: str) -> str:
    return _HEADER_RE.sub("", text, count=1)


def _load_inputs(data_dir: Path) -> dict[str, Any]:
    base = data_dir
    events = [
        json.loads(l) for l in (base / "source_of_truth" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    corpus_index = [
        json.loads(l) for l in (base / "corpus_index.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    artefact_reports = [
        json.loads(l) for l in (base / "artefact_validation_report.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    personas = []
    personas_path = base / "helix_canon" / "personas.jsonl"
    if personas_path.exists():
        personas = [
            json.loads(l) for l in personas_path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    return {
        "events_by_id": {e["id"]: e for e in events},
        "index_by_slot": {r["slot_id"]: r for r in corpus_index},
        "artefact_reports": {a["slot_id"]: a for a in artefact_reports},
        "persona_by_id": {p["persona_id"]: p for p in personas},
    }


def _facts_split(report: dict) -> tuple[list[str], list[str]]:
    """Return (missing_facts, present_facts) from an artefact report."""
    missing, present = [], []
    for f in report.get("facts", []):
        if f["verdict"] == "no":
            missing.append(f["fact"])
        else:
            present.append(f["fact"])
    return missing, present


def _deterministic_append(artefact_text: str, missing_facts: list[str]) -> str:
    """Guaranteed fallback: append the missing facts as a reference block."""
    lines = [
        "",
        "<!-- substrate_repair: the following ground-truth details were "
        "under-represented in the generated artefact and appended to "
        "guarantee the corpus contains them. -->",
        "",
        "## Reference details",
        "",
    ]
    for f in missing_facts:
        # Each fact string is like 'The decision: "..."' or
        # 'At least one participant by name (any of: P-0009, P-0033)'.
        # We surface the human-meaningful part.
        lines.append(f"- {f}")
    return artefact_text.rstrip() + "\n" + "\n".join(lines) + "\n"


async def repair_artefact(
    llm: HelixLLM,
    slot_id: str,
    inputs: dict,
    data_dir: Path,
) -> dict:
    """Repair one deficient artefact. Returns updated report record."""
    report = inputs["artefact_reports"][slot_id]
    art_index = inputs["index_by_slot"][slot_id]
    event = inputs["events_by_id"].get(art_index["event_id"], {})
    art_path = data_dir / art_index["path"]

    raw = art_path.read_text(encoding="utf-8")
    body = _strip_header(raw)
    facts = _canonical_facts_for_artefact(
        art_index, event, inputs["events_by_id"], inputs.get("persona_by_id"),
    )
    missing, present = _facts_split(report)

    if not missing:
        return report  # nothing to do

    template = _load_repair_template()

    # --- Tier 1: gpt-oss regeneration ---
    best_body = body
    best_results = None
    for attempt in range(MAX_GPT_ATTEMPTS):
        prompt = template.format(
            artefact_text=body[:6000],
            missing_facts_block="\n".join(f"- {m}" for m in missing),
            present_facts_block="\n".join(f"- {p}" for p in present) or "(none)",
        )
        new_body = await llm.call_text(
            stage="C",
            user=prompt,
            reasoning_effort="medium",
            max_tokens=6000,
        )
        new_body = new_body.strip()
        if not new_body:
            continue
        # Re-check substrate on the new body
        results = await _check_artefact_substrate(llm, art_index, new_body, facts)
        n_ok = sum(1 for r in results if r["verdict"] in ("yes", "partial"))
        score = sum(1.0 if r["verdict"] == "yes" else 0.5 if r["verdict"] == "partial" else 0 for r in results) / max(1, len(facts))
        logger.info(
            "Repair %s attempt %d: score %.2f (%d/%d facts)",
            slot_id, attempt + 1, score, n_ok, len(facts),
        )
        if score >= REPAIR_THRESHOLD:
            best_body = new_body
            best_results = results
            break
        # Keep the best attempt so far
        if best_results is None or score > _score_of(best_results, facts):
            best_body = new_body
            best_results = results

    # --- Tier 2: deterministic append fallback ---
    final_score = _score_of(best_results, facts) if best_results else 0.0
    used_fallback = False
    if final_score < REPAIR_THRESHOLD:
        # Recompute which facts are still missing after the best gpt-oss attempt
        if best_results:
            still_missing = [
                facts[i] for i, r in enumerate(best_results) if r["verdict"] == "no"
            ]
        else:
            still_missing = missing
        best_body = _deterministic_append(best_body, still_missing)
        used_fallback = True
        logger.info(
            "Repair %s: gpt-oss reached %.2f (<%.2f); appended %d facts deterministically",
            slot_id, final_score, REPAIR_THRESHOLD, len(still_missing),
        )

    # Write the repaired artefact back (with a fresh testimony header)
    header = _testimony_header(
        genre=art_index.get("genre", "slack_thread"),
        slot_id=slot_id,
        author=str(art_index.get("author", "?")),
        event_id=art_index.get("event_id", "?"),
        role=str(art_index.get("role", "primary")),
    )
    art_path.write_text(header + best_body, encoding="utf-8")

    # Final verification
    final_results = await _check_artefact_substrate(llm, art_index, best_body, facts)
    final_score = _score_of(final_results, facts)
    from collections import Counter
    vc = Counter(r["verdict"] for r in final_results)
    updated = {
        **report,
        "yes": vc.get("yes", 0),
        "partial": vc.get("partial", 0),
        "no": vc.get("no", 0),
        "score": round(final_score, 3),
        "repaired": True,
        "repair_used_fallback": used_fallback,
        "facts": [
            {"fact": f, "verdict": r["verdict"], "justification": r.get("justification", "")}
            for f, r in zip(facts, final_results)
        ],
    }
    logger.info("Repair %s DONE: final score %.2f (fallback=%s)", slot_id, final_score, used_fallback)
    return updated


def _score_of(results: list[dict] | None, facts: list[str]) -> float:
    if not results:
        return 0.0
    return sum(
        1.0 if r["verdict"] == "yes" else 0.5 if r["verdict"] == "partial" else 0
        for r in results
    ) / max(1, len(facts))


async def run(*, size: str, data_dir: str) -> None:
    """Repair all artefacts scoring below REPAIR_THRESHOLD."""
    data_root = Path(data_dir)
    inputs = _load_inputs(data_root)

    deficient = [
        slot_id for slot_id, rep in inputs["artefact_reports"].items()
        if rep.get("score", 1.0) < REPAIR_THRESHOLD and rep.get("facts")
    ]
    logger.info("Repair: %d artefacts below %.2f threshold", len(deficient), REPAIR_THRESHOLD)

    if not deficient:
        logger.info("Nothing to repair.")
        return

    llm = HelixLLM()
    updated_reports: dict[str, dict] = dict(inputs["artefact_reports"])
    try:
        for slot_id in deficient:
            updated = await repair_artefact(llm, slot_id, inputs, data_root)
            updated_reports[slot_id] = updated
    finally:
        await llm.aclose()

    # Rewrite the artefact_validation_report with the repaired records
    report_path = data_root / "artefact_validation_report.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for slot_id, rep in updated_reports.items():
            f.write(json.dumps(rep, default=str) + "\n")

    n_now_ok = sum(1 for r in updated_reports.values() if r.get("score", 0) >= REPAIR_THRESHOLD)
    logger.info(
        "Repair complete. %d/%d artefacts now ≥ %.2f",
        n_now_ok, len(updated_reports), REPAIR_THRESHOLD,
    )
