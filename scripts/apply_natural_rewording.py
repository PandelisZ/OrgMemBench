#!/usr/bin/env python3
"""
Apply the natural-language question rewordings (2026-05-26) to all 14
helix-small questions. Question TEXT only — rubrics + GT unchanged.

The C5 questions in particular: keep the current "enumerate evidence + classify
direct/inferred" rubric, but reshape the question so the system is prompted
naturally ("walk me through the supporting records, and for each, say whether
it's direct testimony or an inference") instead of with the awkward "your
statement / your claim / your conclusion" framing.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "datasets/helix/small/benchmark_v0.0.jsonl"
CHG  = ROOT / "datasets/helix/small/CHANGELOG.md"

REWORDINGS = {
    # C1
    "Q-0001": (
        "What's Helix's current data retention policy? What did it replace, "
        "when did the change happen, and what drove it?"
    ),
    # C2
    "Q-0002": (
        "Who led the decision to pivot Helix's architecture, when did they "
        "decide, what other options did they consider, and what was the main "
        "reason for the choice?"
    ),
    "Q-0003": (
        "Who decided to move Helix to cloud-native microservices, when did "
        "they decide, what alternatives did they consider, and what drove "
        "the call?"
    ),
    # C3
    "Q-0004": (
        "What's your current understanding of the choice Maya Patel, Luis "
        "Hernandez, and Arjun Mehta made about Helix? When did you first "
        "learn that, and when did you learn the later amendment? What would "
        "your answer have been if asked on 2021-10-01?"
    ),
    "Q-0005": (
        "What's your current understanding of the event involving Omar "
        "Khaled, Omar Farah, and Arjun Mehta? When did you first learn about "
        "it, and when did you learn the revised version? What would your "
        "answer have been on 2022-03-15?"
    ),
    "Q-0006": (
        "What's your current understanding of the API strategy discussion "
        "between Arjun Mehta and Daniel Ortiz? When did you first hear the "
        "conclusion, and when did the correction come in? What would your "
        "answer have been on 2022-01-15?"
    ),
    # C4
    "Q-0007": (
        "What did you know about Helix's data retention framework as of "
        "2022-05-31? For each thing you knew then, note whether it's still "
        "current or has since been changed or removed — and if changed, "
        "what replaced it."
    ),
    # C5 — keep rubric, reshape question to elicit enumeration + classification
    "Q-0008": (
        "Tell me about Helix's shift from spreadsheet-based integration to "
        "API-first — walk me through the supporting records, and for each, "
        "say whether it's direct testimony or an inference."
    ),
    "Q-0009": (
        "Tell me about the Helix API v1.0 launch — walk me through the "
        "supporting records, and for each, say whether it's direct testimony "
        "or an inference."
    ),
    "Q-0010": (
        "Tell me about the 2021-05-22 outage and what caused it — walk me "
        "through the supporting records, and for each, say whether it's "
        "direct testimony or an inference."
    ),
    # C6 — keep named-parties version; drop the "conflict between these claims"
    # tip-off but still name both speakers + dates (per C6 design that both
    # party names appear in the question)
    "Q-0011": (
        "What did Luis Hernandez say on 2022-06-15, and what did Omar Khaled "
        "say on 2021-05-22? How do those two accounts relate?"
    ),
    # EMG — already natural; leave unchanged. Listed here so the script
    # is explicit about what was reviewed and intentionally not touched.
}

EMG_KEEP_AS_IS = {"Q-EMG-0000", "Q-EMG-0001", "Q-EMG-0002"}


def main() -> int:
    rows = [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]
    touched = []
    for q in rows:
        qid = q["id"]
        if qid in REWORDINGS:
            old = q["text"]
            new = REWORDINGS[qid]
            if old == new:
                continue
            q["text"] = new
            touched.append((qid, old, new))
            # Stash the prior text in metadata for traceability.
            q.setdefault("metadata", {})["text_pre_rewording_2026_05_26"] = old

    PATH.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in rows) + "\n")

    # CHANGELOG entry
    chg_block = (
        "\n## 2026-05-26 — natural-language question rewording (14 questions)\n\n"
        "Reworded 11 of 14 helix-small question texts to remove benchmark-design "
        "artifacts (\"the system\", \"your statement / your claim / your "
        "conclusion\", and similar test-shape framings) and replace them with "
        "phrasings a person would actually use.\n\n"
        "Key changes:\n"
        "- C1 / C2 — light smoothing (Q-0001, Q-0002, Q-0003)\n"
        "- C3 — dropped \"the system's understanding\" → \"your current "
        "understanding\" (Q-0004, Q-0005, Q-0006)\n"
        "- C4 — dropped \"reconstruct the knowledge held by the system\" → "
        "\"what did you know about ... as of\" (Q-0007)\n"
        "- C5 — dropped the \"your statement / your claim / your conclusion\" "
        "framing entirely; replaced with \"tell me about X — walk me through "
        "the supporting records, and for each, say whether it's direct "
        "testimony or an inference\" (Q-0008, Q-0009, Q-0010). C5 RUBRIC "
        "UNCHANGED — the new wording still elicits the enumerate-evidence + "
        "classify direct/inferred answer shape the existing rubric grades.\n"
        "- C6 — dropped the \"conflict between these two claims\" tip-off "
        "while keeping both party names + dates (per C6 design) (Q-0011)\n"
        "- EMG — already natural, intentionally unchanged (Q-EMG-0000/0001/0002)\n\n"
        "All GTs and rubrics are unchanged from their state at the start of "
        "this rewording. The prior question text for each touched row is "
        "preserved at `metadata.text_pre_rewording_2026_05_26`.\n"
    )
    CHG.write_text(CHG.read_text() + chg_block)

    print(f"Updated {len(touched)} question texts in {PATH.name}")
    for qid, old, new in touched:
        print(f"  {qid}")
    print(f"\nEMG questions left unchanged: {sorted(EMG_KEEP_AS_IS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
