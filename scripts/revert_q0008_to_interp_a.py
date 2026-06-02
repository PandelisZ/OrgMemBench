#!/usr/bin/env python3
"""
Revert Q-0008 GT from interpretation B (full evidence chain incl. supersession)
back to interpretation A (pure C5 evidence chain only).

Rationale: C5's design intent (per generation/helix_corpus/prompts/stage_e/c5_justification_phrasing.md)
is "walk an asserted belief BACK to evidence." If the asserted belief is
"X was decided" then evidence FOR it is the original chain; the 2022
correction is evidence AGAINST it (which is what Q-0010 already tests — a
C5/C6 hybrid). Including the supersession in Q-0008's GT duplicates Q-0010's
test coverage and conflates two different category designs.

Restores Q-0008 to the original 3-item evidence chain + 3 subpoints @ 0.333 each,
using the corpus-canonical testimony labels (direct/inferred, not the original
direct_testimony/inference).
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "datasets/helix/small/benchmark_v0.0.jsonl"
CHG  = ROOT / "datasets/helix/small/CHANGELOG.md"

rows = [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]

for q in rows:
    if q["id"] != "Q-0008":
        continue

    # Restore original question text
    q["text"] = (
        "You concluded that Helix is moving away from spreadsheet-based integration "
        "toward an API-first approach. Please outline the precise conversations or "
        "documents that underpin this choice, and for each, indicate whether it "
        "represents direct testimony or an inference."
    )

    # Restore original ground truth — pure 2021-04-15 evidence chain
    q["ground_truth_answer"] = {
        "claim": (
            "Maya Patel, Luis Hernandez, and Arjun Mehta convened to decide that "
            "Helix would pivot from its existing spreadsheet-centric integration "
            "model to an API-first architecture. They agreed to reallocate "
            "engineering resources to build a robust API layer, update the "
            "product roadmap, and pursue a new funding round. The team secured a "
            "$2 M seed investment to support the transition and set a target "
            "launch for the API platform in Q3 2021.\n"
        ),
        "evidence_summary": [
            "1. meeting_transcript by P-0001 (primary) → direct",
            "2. email_thread by P-0002 (secondary) → direct",
            "3. meeting_notes by P-0005 (secondary) → inferred",
        ],
        "evidence_types": ["meeting_transcript", "email_thread", "meeting_notes"],
        "testimony_attribution": [
            {"slot_id": "ART-EV-2021-001-001", "testimony_type": "direct"},
            {"slot_id": "ART-EV-2021-001-002", "testimony_type": "direct"},
            {"slot_id": "ART-EV-2021-001-003", "testimony_type": "inferred"},
        ],
        "inferential_steps": (
            "The pivot decision was supported by the recorded meeting transcript, "
            "a follow-up email confirming the decision, and contemporaneous "
            "meeting notes summarising the agreed direction."
        ),
    }

    q["evidence_artefact_ids"] = [
        "ART-EV-2021-001-001",
        "ART-EV-2021-001-002",
        "ART-EV-2021-001-003",
    ]

    q["rubric_subpoints"] = [
        {
            "id": "C5.sub1",
            "max_score": 0.333,
            "criterion": (
                "The answer must list all three evidence items in the 2021-04-15 "
                "decision chain (meeting_transcript, email_thread, meeting_notes), "
                "correctly indicating each item's role (primary or secondary). "
                "Full credit if all three are listed with correct role; half "
                "credit for two; zero for fewer than two."
            ),
            "fail_criterion": (
                "missing any of the three 2021-04-15 evidence items, or "
                "mislabeling primary vs secondary."
            ),
        },
        {
            "id": "C5.sub2",
            "max_score": 0.333,
            "criterion": (
                "The answer must correctly distinguish each evidence item as "
                "direct testimony or inferred per the corpus headers "
                "(meeting_transcript: direct, email_thread: direct, "
                "meeting_notes: inferred). Full credit if all three labels "
                "match; half for two; zero for fewer than two."
            ),
            "fail_criterion": (
                "any of the three 2021-04-15 evidence items is mislabeled "
                "direct vs inferred."
            ),
        },
        {
            "id": "C5.sub3",
            "max_score": 0.333,
            "criterion": (
                "The answer must not introduce evidence items or testimony "
                "types beyond the three 2021-04-15 artifacts in the ground "
                "truth. The 2022-05-10 audit (ART-EV-2022-007-001) is a "
                "supersession event, NOT evidence supporting the original "
                "API-first claim — it is properly tested by Q-0010 / Q-0011 "
                "(C5/C6 supersession coverage). A correct C5 answer to Q-0008 "
                "may MENTION that the original record was later revised, but "
                "must not list the 2022-05-10 audit as evidence FOR the "
                "asserted belief. Full credit if no hallucinated evidence or "
                "testimony types are present; zero if any additional "
                "supporting-evidence items are introduced."
            ),
            "fail_criterion": (
                "any hallucinated evidence item or testimony type; or treating "
                "the 2022-05-10 supersession event as evidence FOR the original "
                "claim rather than as a later correction."
            ),
        },
    ]

    q.setdefault("metadata", {})["audit_notes"] = (
        "Reverted from interpretation B (full evidence chain incl. supersession) "
        "back to interpretation A (pure C5 evidence chain). C5's design intent "
        "(generation/helix_corpus/prompts/stage_e/c5_justification_phrasing.md) "
        "is 'walk an asserted belief BACK to evidence' — the asserted belief is "
        "the original API-first pivot; the 2022 correction is evidence AGAINST "
        "the belief and is properly the domain of Q-0010 (C5 with supersession) "
        "and Q-0011 (C6 contradiction). Including the supersession in Q-0008's "
        "GT would duplicate Q-0010 / Q-0011's test coverage. C5.sub3 acknowledges "
        "the supersession exists but bars treating it as evidence FOR the "
        "original claim."
    )

PATH.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in rows) + "\n")

CHG.write_text(
    CHG.read_text()
    + "\n## 2026-05-26 — q0008-revert-to-interpretation-a\n\n"
    "Reverted Q-0008 GT from interpretation B (full evidence chain incl. "
    "supersession) back to interpretation A (pure C5 evidence chain) per "
    "C5 design intent. The 2022-05-10 supersession is now explicitly NOT "
    "treated as evidence for the original API-first pivot — C5.sub3 instructs "
    "the rubric to treat it as a later correction belonging to Q-0010 (C5+supersession) "
    "and Q-0011 (C6 contradiction) test coverage, not Q-0008's pure C5 "
    "evidence-chain walk. Restored 3 evidence items, 3 subpoints @ 0.333.\n"
)

print(f"reverted Q-0008 to interpretation A")
