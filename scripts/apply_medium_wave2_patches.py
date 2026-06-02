#!/usr/bin/env python3
"""
Merge all 6 wave-2 category patch files into medium/benchmark_v0.0.jsonl.

Source patch files at results/_bench_audit/medium-c{1-6}-patches.json.
Each patch is {qid: {field_changes}}. Only changed fields are present.

The 'flagged_for_removal' Q-0069 + the 'retired' Q-0031/32/33 still have
patches with their best-effort GT — they stay in the bench (no retiring,
per the user's directive). Wave 3 will iterate on them.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "datasets/helix/medium/benchmark_v0.0.jsonl"
PATCH_DIR = ROOT / "results/_bench_audit"
CHG = ROOT / "datasets/helix/medium/CHANGELOG.md"

PATCH_FILES = [
    PATCH_DIR / "medium-c1-patches.json",
    PATCH_DIR / "medium-c2-patches.json",
    PATCH_DIR / "medium-c3-patches.json",
    PATCH_DIR / "medium-c4-patches.json",
    PATCH_DIR / "medium-c5-patches.json",
    PATCH_DIR / "medium-c6-patches.json",
]

# Back up original
BACKUP = BENCH.with_name(BENCH.name + ".pre-wave2.jsonl")
if not BACKUP.exists():
    BACKUP.write_text(BENCH.read_text())

# Load benchmark
rows = [json.loads(l) for l in BENCH.read_text().splitlines() if l.strip()]
by_id = {r["id"]: r for r in rows}

# Load + merge patches
def extract_patches(blob: dict) -> dict:
    """Different agents wrapped their output differently. Find the flat
    {qid: {fields}} mapping inside the file regardless of wrapper key."""
    # If keys look like qids already, blob is flat
    if all(k.startswith("Q-") for k in blob.keys() if not k.startswith("_")):
        return {k: v for k, v in blob.items() if k.startswith("Q-")}
    # Otherwise look for common wrapper keys
    for wrapper_key in ("patches", "questions", "edits"):
        if wrapper_key in blob and isinstance(blob[wrapper_key], dict):
            inner = blob[wrapper_key]
            if all(k.startswith("Q-") for k in inner.keys()):
                return inner
    # Fall back: gather any top-level keys that look like qids
    return {k: v for k, v in blob.items() if k.startswith("Q-")}


merged_summary = {}
for pf in PATCH_FILES:
    if not pf.exists():
        print(f"  ! missing patch file: {pf.name}")
        continue
    blob = json.loads(pf.read_text())
    patches = extract_patches(blob)
    cat_name = pf.stem.replace("medium-c", "").replace("-patches", "")
    merged_summary[cat_name] = {"file": pf.name, "questions": []}
    for qid, fields in patches.items():
        if qid not in by_id:
            print(f"  ! unknown qid {qid} in {pf.name}")
            continue
        q = by_id[qid]
        # Stash original text if patch changes it
        if "text" in fields and "text" != q.get("text"):
            q.setdefault("metadata", {})["text_pre_wave2_2026_05_26"] = q["text"]
        for field, value in fields.items():
            if field == "metadata":
                # Merge metadata rather than replacing
                q.setdefault("metadata", {}).update(value)
            else:
                q[field] = value
        merged_summary[cat_name]["questions"].append(qid)

# Write back
BENCH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

# CHANGELOG entry
entry = (
    "\n## 2026-05-26 — wave-2 category patches applied (C1–C6)\n\n"
    "Applied all 6 wave-2 category patch files to benchmark_v0.0.jsonl. "
    "Per-category change counts:\n"
)
for cat, info in merged_summary.items():
    entry += f"- C{cat}: {len(info['questions'])} questions patched (from {info['file']})\n"
entry += (
    "\nPre-patch benchmark preserved at benchmark_v0.0.pre-wave2.jsonl. "
    "All 73 questions retained (no retirements per user directive); "
    "Q-0031, Q-0032, Q-0033, Q-0069 carry best-effort patches and are "
    "flagged for wave-3 iteration.\n"
)
CHG.write_text(CHG.read_text() + entry)

# Print summary
print(f"Merged {sum(len(v['questions']) for v in merged_summary.values())} patches into {BENCH.name}")
for cat, info in merged_summary.items():
    print(f"  C{cat}: {len(info['questions'])} questions")
print(f"\nBackup: {BACKUP.name}")
