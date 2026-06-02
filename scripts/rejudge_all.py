#!/usr/bin/env python3
"""
Re-judge every system's helix-small answers against the patched GT.

For each system, we extract answer_text + cited_artifact_ids from the existing
results JSON into a JSONL submission, then re-run `judge-submission` on the
patched benchmark. The new run is written to results/<system>/helix-small.patched.json
alongside the originals (the originals are NOT overwritten).

A final summary table compares original vs patched scores per system per Q.
"""
from __future__ import annotations
import json, sys, pathlib, subprocess, tempfile, statistics, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

# (label, system_name_in_results_dir, source_json)
SYSTEMS = [
    ("gbrain",                 "gbrain",     "helix-small.json"),
]

def make_submission(src_path: pathlib.Path) -> str:
    """Extract a JSONL submission from a results JSON. Returns path to temp file."""
    d = json.loads(src_path.read_text())
    fd, tmp = tempfile.mkstemp(suffix=".jsonl", prefix="rejudge-")
    os.close(fd)
    with open(tmp, "w") as f:
        for qr in d.get("queries", []):
            rec = {
                "question_id": qr["question_id"],
                "answer_text": qr.get("answer_text") or "",
                "cited_artifact_ids": qr.get("cited_artifact_ids") or [],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return tmp

def main() -> int:
    summary = {}
    for label, sysname, fname in SYSTEMS:
        src = RESULTS / sysname / fname
        if not src.exists():
            print(f"  ! missing source: {src}")
            continue
        print(f"\n=== {label}  ({sysname}/{fname}) ===")
        sub_path = make_submission(src)
        try:
            # Run judge-submission. It writes to results/<system_arg>/<tier>.json by default.
            # We need a label that doesn't clobber the original.
            judge_label = f"{label.replace(' ', '_').lower()}_repatched"
            cmd = [
                sys.executable, "-m", "orgmembench.cli",
                "judge-submission",
                "--file", sub_path,
                "--system", judge_label,
                "--tier", "small",
                "--company", "helix",
            ]
            out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            print(out.stdout[-1500:] if out.stdout else "")
            if out.returncode != 0:
                print(f"  ERR: {out.stderr[-800:]}")
                continue

            # Load the re-judged result
            new_path = RESULTS / judge_label / "helix-small.json"
            if not new_path.exists():
                # try alternate location
                cands = list((RESULTS).glob(f"**/{judge_label}*/*.json"))
                if cands: new_path = cands[0]
                else:
                    print(f"  ! cannot find re-judged result for {label}")
                    continue
            new_d = json.loads(new_path.read_text())
            old_d = json.loads(src.read_text())
            old_by_q = {j["question_id"]: j for j in old_d["judgements"]}
            new_by_q = {j["question_id"]: j for j in new_d["judgements"]}
            summary[label] = {"old": old_by_q, "new": new_by_q,
                              "old_avg": sum(j["score"] for j in old_by_q.values()) / len(old_by_q),
                              "new_avg": sum(j["score"] for j in new_by_q.values()) / len(new_by_q),
                              "result_path": str(new_path.relative_to(ROOT))}
        finally:
            try: os.unlink(sub_path)
            except FileNotFoundError: pass

    # ─── Print summary table ────────────────────────────────────────────────
    if not summary:
        print("\nNo systems were re-judged.")
        return 1

    print("\n" + "="*100)
    print("OLD vs PATCHED scores")
    print("="*100)
    all_qids = sorted({q for s in summary.values() for q in s["new"]})
    cols = list(summary)
    header = f"{'qid':<10}" + "".join(f" {c:>22}" for c in cols)
    print(header)
    print("-"*len(header))
    for qid in all_qids:
        row = [f"{qid:<10}"]
        for c in cols:
            o = summary[c]["old"].get(qid)
            n = summary[c]["new"].get(qid)
            if not o or not n:
                row.append(f"{'—':>22}")
                continue
            os_ = o["score"]; ns = n["score"]; d = ns - os_
            sign = "+" if d > 0 else ("-" if d < 0 else " ")
            row.append(f" {os_:.2f}→{ns:.2f}({sign}{abs(d):.2f})".rjust(22))
        print("".join(row))
    print("-"*len(header))
    avg_row = [f"{'AVG':<10}"]
    for c in cols:
        o = summary[c]["old_avg"]; n = summary[c]["new_avg"]; d = n - o
        sign = "+" if d > 0 else ("-" if d < 0 else " ")
        avg_row.append(f" {o:.3f}→{n:.3f}({sign}{abs(d):.3f})".rjust(22))
    print("".join(avg_row))

    out_summary = ROOT / "results/_bench_audit/rejudge-summary.json"
    out_summary.parent.mkdir(exist_ok=True)
    out_summary.write_text(json.dumps({
        c: {"old_avg": summary[c]["old_avg"], "new_avg": summary[c]["new_avg"],
            "result_path": summary[c]["result_path"],
            "per_q": {qid: {"old": summary[c]["old"].get(qid,{}).get("score"),
                             "new": summary[c]["new"].get(qid,{}).get("score")}
                       for qid in all_qids}}
        for c in cols
    }, indent=2))
    print(f"\nSummary written to {out_summary.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
