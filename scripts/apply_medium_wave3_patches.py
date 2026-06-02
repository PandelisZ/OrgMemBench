#!/usr/bin/env python3
"""
Apply wave-3 patches to medium/benchmark_v0.0.jsonl.

Different wave-3 agents emitted slightly different schemas (some packaged the
real patch values inside audit-wrappers like `audit_verdict`/`issues`/`severity`).
This script normalizes all six wave-3 patch files into a single per-qid set of
benchmark-field updates and applies them.

Inputs:
    results/_bench_audit/medium-c{1..6}-wave3-patches.json

Output:
    datasets/helix/medium/benchmark_v0.0.jsonl  (in place)
    datasets/helix/medium/benchmark_v0.0.pre-wave3.jsonl  (backup)
    datasets/helix/medium/CHANGELOG.md  (append entry)
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "datasets/helix/medium/benchmark_v0.0.jsonl"
PATCH_DIR = ROOT / "results/_bench_audit"
CHG = ROOT / "datasets/helix/medium/CHANGELOG.md"

# Fields that actually live in benchmark_v0.0.jsonl questions. Anything in a
# wave-3 patch file matching one of these names is a real patch; other keys
# (audit_verdict, issues, severity, audit_notes, audit_note, issues_fixed,
# chain, original_event_id, _meta, etc.) are audit metadata, ignored here.
BENCH_FIELDS = {
    "text",
    "category",
    "paraphrases",
    "ground_truth_answer",
    "ground_truth_answer_patch",   # C5 used this name; normalized below
    "rubric_subpoints",
    "evidence_artefact_ids",
    "as_of_date",
    "anchor_event_id",
    "anchor_event_ids",
    "metadata",
}

PATCH_FILES = [
    PATCH_DIR / "medium-c1-wave3-patches.json",
    PATCH_DIR / "medium-c2-wave3-patches.json",
    PATCH_DIR / "medium-c3-wave3-patches.json",
    PATCH_DIR / "medium-c4-wave3-patches.json",
    PATCH_DIR / "medium-c5-wave3-patches.json",
    PATCH_DIR / "medium-c6-wave3-patches.json",
]


def load_lenient_json(path: pathlib.Path) -> dict:
    """Load a JSON file. If it fails due to backslash escapes the agents
    produced as a side effect of quoting natural-language text containing
    apostrophes, repair the most common error and retry."""
    txt = path.read_text()
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        # Most common: `\'` inside a string (agents quoted contractions).
        # JSON only allows \" \\ \/ \b \f \n \r \t \uXXXX. Replace \' with '
        # everywhere; it's only a problem inside strings, but replacing
        # globally is safe since the only valid place outside strings is
        # impossible (no apostrophes outside strings in JSON).
        repaired = txt.replace(r"\'", "'")
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e2:
            print(f"  ! could not repair {path.name}: {e2}")
            raise


def extract_patch(qid_blob: dict) -> dict:
    """Pull only benchmark-field-name keys out of an agent's per-qid blob,
    so audit-only fields are dropped."""
    out = {}
    for k, v in qid_blob.items():
        if k == "ground_truth_answer_patch":
            # C5 wrote partial GT patches under this key; merge later.
            # 2026-06-01 BUGFIX: many C5 patches carried `ground_truth_answer_patch: null`
            # (no actual GT change). The old code set ground_truth_answer = None,
            # NULLING the real GT and making 10 C5 questions unscoreable (every
            # system auto-scored 0). NEVER let a null/empty patch overwrite a GT.
            if v:
                out["ground_truth_answer"] = v
        elif k in BENCH_FIELDS:
            out[k] = v
    return out


def main() -> int:
    if not BENCH.exists():
        raise SystemExit(f"benchmark file missing: {BENCH}")
    backup = BENCH.with_name(BENCH.name + ".pre-wave3.jsonl")
    if not backup.exists():
        backup.write_text(BENCH.read_text())

    rows = [json.loads(l) for l in BENCH.read_text().splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}

    summary = {}     # category -> {patched: [qids], skipped: [qids]}
    bad_qids = []    # patches with no benchmark-field updates

    for pf in PATCH_FILES:
        if not pf.exists():
            print(f"  ! missing patch file: {pf.name}")
            continue
        try:
            blob = load_lenient_json(pf)
        except Exception as exc:
            print(f"  ! failed to load {pf.name}: {exc}")
            continue
        cat = re.search(r"medium-c(\d)-", pf.name).group(1)
        summary[cat] = {"file": pf.name, "patched": [], "skipped": []}

        # Some agents wrap patches under a `patches:` key (with a sibling
        # `validation_summary` block); reach into it if present.
        if isinstance(blob.get("patches"), dict) and any(
            k.startswith("Q-") for k in blob["patches"].keys()
        ):
            iter_blob = blob["patches"]
        else:
            iter_blob = blob

        for qid, qblob in iter_blob.items():
            if not qid.startswith("Q-"):
                continue
            if qid not in by_id:
                print(f"  ! unknown qid {qid} in {pf.name}")
                continue
            patch = extract_patch(qblob if isinstance(qblob, dict) else {})
            if not patch:
                summary[cat]["skipped"].append(qid)
                bad_qids.append((qid, pf.name))
                continue
            row = by_id[qid]
            # Stash prior text if rewriting
            if "text" in patch and patch["text"] != row.get("text"):
                row.setdefault("metadata", {})["text_pre_wave3_2026_05_26"] = row.get("text", "")
            # Merge ground_truth_answer if both are dicts (C5 may emit partial)
            if "ground_truth_answer" in patch and isinstance(patch["ground_truth_answer"], dict) \
               and isinstance(row.get("ground_truth_answer"), dict):
                merged = dict(row["ground_truth_answer"])
                merged.update(patch["ground_truth_answer"])
                row["ground_truth_answer"] = merged
                patch.pop("ground_truth_answer")
            # Merge metadata dict-additively
            if "metadata" in patch and isinstance(patch["metadata"], dict):
                row.setdefault("metadata", {}).update(patch["metadata"])
                patch.pop("metadata")
            # Replace remaining fields wholesale
            for field, value in patch.items():
                row[field] = value
            summary[cat]["patched"].append(qid)

    # Write the benchmark
    BENCH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")

    # CHANGELOG
    entry = (
        "\n## 2026-05-26 — wave-3 patches applied (C1–C6)\n\n"
        "Validation-+-repair pass over wave-2. Each wave-3 patch file was schema-"
        "normalized (real benchmark fields kept, audit metadata dropped) before "
        "merging. Per-category change counts:\n"
    )
    for cat in sorted(summary):
        info = summary[cat]
        entry += (
            f"- **C{cat}**: {len(info['patched'])} patched, "
            f"{len(info['skipped'])} skipped (no benchmark-field updates) "
            f"— from {info['file']}\n"
        )
    if bad_qids:
        entry += (
            "\nSkipped qids (audit metadata only, no actionable patch — "
            "the question was either already correct or flagged for a future pass):\n"
        )
        for qid, src in bad_qids:
            entry += f"  - {qid}  ({src})\n"
    entry += (
        "\nPre-wave-3 benchmark preserved at benchmark_v0.0.pre-wave3.jsonl. "
        "All 73 questions retained.\n"
    )
    CHG.write_text(CHG.read_text() + entry)

    # Console summary
    total_patched = sum(len(v["patched"]) for v in summary.values())
    total_skipped = sum(len(v["skipped"]) for v in summary.values())
    print(f"\n✓ Applied {total_patched} patches to {BENCH.name}  (skipped {total_skipped} as audit-only)")
    for cat, info in sorted(summary.items()):
        print(f"  C{cat}: patched={len(info['patched'])}  skipped={len(info['skipped'])}")
    print(f"\nBackup: {backup.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
