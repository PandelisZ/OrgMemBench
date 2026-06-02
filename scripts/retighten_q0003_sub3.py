#!/usr/bin/env python3
"""
Re-tighten Q-0003 C2.sub3 now that both alternatives are corpus-recoverable
via ART-EV-2022-013-001 (the new primary transcript).

Earlier patch loosened sub3 because alternatives were source-of-truth-only
(not in any corpus artifact). With -2022-013-001 in place, both alternatives
are mentioned in dialogue (Omar's monolith-refactoring attempt + Arjun's
hybrid-cloud note about Priya's analysis). Restore the stricter sub3 that
requires the system to surface both.

Q-0002's sub3 stays loosened — the corpus situation didn't change there
(the "maintain spreadsheet" alternative is still source-of-truth-only).
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "datasets/helix/small/benchmark_v0.0.jsonl"
CHG  = ROOT / "datasets/helix/small/CHANGELOG.md"

rows = [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]

for q in rows:
    if q["id"] != "Q-0003":
        continue
    for sp in q["rubric_subpoints"]:
        if sp["id"] != "C2.sub3":
            continue
        sp["criterion"] = (
            "The answer must identify both alternatives that were considered "
            "before the cloud-native decision: (a) keeping the monolith with "
            "incremental refactoring / carving out modules to isolate Fleet "
            "data within the existing schema, and (b) a hybrid cloud approach "
            "with legacy services on-prem plus new Fleet services in the "
            "cloud as a sidecar. Both alternatives are recoverable from the "
            "2022-08-20 meeting transcript (ART-EV-2022-013-001). Full credit "
            "if both alternatives are identified; half credit for one; zero "
            "if neither is identified or only a vague 'other options' framing."
        )
        sp["fail_criterion"] = (
            "fewer than two alternatives mentioned, or alternatives that don't "
            "match the corpus content (incremental monolith refactoring + "
            "hybrid cloud)."
        )

    notes = q.setdefault("metadata", {}).get("audit_notes", "")
    q["metadata"]["audit_notes"] = (
        notes
        + " [2026-05-26 re-tightening] Now that ART-EV-2022-013-001 has been "
        "generated and includes both alternatives in dialogue (Omar's "
        "monolith-carve-out attempt + Arjun's hybrid-cloud note about "
        "Priya's analysis), C2.sub3 is re-tightened to require both — the "
        "previous loosening was a workaround for the missing-from-corpus gap "
        "that no longer applies."
    ).strip()

PATH.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in rows) + "\n")

CHG.write_text(
    CHG.read_text()
    + "\n## 2026-05-26 — q0003-sub3-retightening\n\n"
    "Re-tightened Q-0003 C2.sub3 to require both alternatives now that "
    "ART-EV-2022-013-001 has both monolith-refactoring + hybrid-cloud paths "
    "mentioned in dialogue (scattered, not enumerated). Q-0002's sub3 stays "
    "loosened since the 'maintain spreadsheet' alternative is still SoT-only.\n"
)

print("retightened Q-0003 C2.sub3")
