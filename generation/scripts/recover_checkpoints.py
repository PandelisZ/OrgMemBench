"""Recover from an internet-drop cascade.

When the laptop lost the orchestrator mid-run, gpt-oss calls returned
empty and the C2/C3/C4/C5 loops marked their remaining slots
"empty"-done (and Stage E produced no questions). Those poisoned
checkpoint entries would make a naive re-run SKIP the work.

This purges every checkpoint entry whose status is NOT "ok" for the
cascade-affected stages, so a re-run regenerates exactly the slots that
never really completed. Real artefacts on disk + corpus_index +
events.jsonl are untouched (the run only wrote those on success).

Idempotent. Safe to run repeatedly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(sys.argv[1] if len(sys.argv) > 1 else "data_v0.3_large")
CP = DATA / ".checkpoints"


def purge_non_ok(name: str) -> None:
    f = CP / name
    if not f.exists():
        print(f"  {name}: (absent)")
        return
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    ok = [r for r in rows if r.get("status") == "ok"]
    f.write_text("".join(json.dumps(r) + "\n" for r in ok))
    print(f"  {name}: {len(rows)} -> {len(ok)} ok (purged {len(rows) - len(ok)} non-ok)")


def delete(p: Path) -> None:
    if p.exists():
        p.unlink()
        print(f"  deleted {p.name}")
    else:
        print(f"  {p.name}: (absent)")


print("Purging cascade-poisoned checkpoints (keep only status=ok):")
for s in ("stage_c2.jsonl", "stage_c3.jsonl", "stage_c4.jsonl", "stage_c5.jsonl"):
    purge_non_ok(s)

print("Resetting Stage E + F (regenerate questions fresh over the full corpus):")
delete(CP / "stage_e.jsonl")
delete(DATA / "questions_draft.jsonl")
delete(CP / "stage_f_artefacts.jsonl")
delete(CP / "stage_f_questions.jsonl")
delete(DATA / "artefact_validation_report.jsonl")
delete(DATA / "question_validation_report.jsonl")
delete(DATA / "benchmark_v0.0.jsonl")

print("Done. Re-run: bash run_large.sh")
