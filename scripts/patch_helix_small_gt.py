#!/usr/bin/env python3
"""
Patch helix-small benchmark_v0.0.jsonl against the audit findings in
results/_bench_audit/*.md.

Reads:   datasets/helix/small/benchmark_v0.0.original.jsonl   (back-up, immutable)
Writes:  datasets/helix/small/benchmark_v0.0.jsonl            (patched)
Logs:    datasets/helix/small/CHANGELOG.md                    (append-only)

Run once. Idempotent w.r.t. the .original backup: re-running rebuilds the
patched file from .original each time.
"""

from __future__ import annotations
import json, sys, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC  = ROOT / "datasets/helix/small/benchmark_v0.0.original.jsonl"
DST  = ROOT / "datasets/helix/small/benchmark_v0.0.jsonl"
CHG  = ROOT / "datasets/helix/small/CHANGELOG.md"

PATCH_VERSION = "v0.0.1-bench-audit-2026-05-26"

# ─── Patch table ──────────────────────────────────────────────────────────────
# Each patcher takes the question dict and mutates it in place. Returns a
# short string describing what it did (for the changelog).

def patch_Q_0010(q: dict) -> str:
    """C5 Q-0010: LB hypothesis was retroactively superseded by DNS finding.
    Update the GT claim to reflect the supersession; expand evidence set;
    invert C5.sub3 so citing the superseding record is rewarded, not punished."""
    gt = q["ground_truth_answer"]
    gt["claim"] = (
        "Omar Khaled and Omar Farah originally attributed the 2-hour outage on "
        "2021-05-22 to a load balancer misconfiguration (ART-EV-2021-003-001). "
        "Arjun Mehta rolled back the deployment, restored the previous load "
        "balancer settings, and re-deployed; the team added a health-check "
        "validation step to the pipeline. This causal claim was later ruled out: "
        "the 2022-06-15 postmortem (ART-EV-2022-008-002, corroborated by "
        "ART-EV-2022-008-003) established DNS record misconfiguration as the "
        "actual root cause and the load balancer hypothesis was explicitly "
        "ruled out by Arjun Mehta and Luis Hernandez."
    )
    gt["evidence_summary"] = [
        "1. slack_thread by P-0035 (primary) → direct_testimony   # 2021-05-22 original LB claim",
        "2. meeting_notes by P-0005 (secondary) → inference         # 2021-05-22 LB rollback discussion",
        "3. incident_report by P-0035 (secondary) → inference       # 2021-05-22 LB incident write-up",
        "4. meeting_transcript by P-0004 (supersession) → direct_testimony   # 2022-06-15 postmortem ruling LB out",
        "5. slack_thread by P-0005 (supersession) → direct_testimony         # 2022-06-15 confirmation of DNS root cause",
    ]
    gt["evidence_types"] = ["slack_thread", "meeting_notes", "incident_report",
                            "meeting_transcript", "slack_thread"]
    gt["testimony_attribution"] = [
        {"slot_id": "ART-EV-2021-003-001", "testimony_type": "direct_testimony"},
        {"slot_id": "ART-EV-2021-003-002", "testimony_type": "inference"},
        {"slot_id": "ART-EV-2021-003-003", "testimony_type": "inference"},
        {"slot_id": "ART-EV-2022-008-002", "testimony_type": "direct_testimony"},
        {"slot_id": "ART-EV-2022-008-003", "testimony_type": "direct_testimony"},
    ]
    gt["inferential_steps"] = (
        "The outage on 2021-05-22 was originally attributed to a load balancer "
        "misconfiguration (missing health-check). On 2022-06-15 a postmortem "
        "ruled this out and established DNS misconfiguration as the root cause."
    )

    q["evidence_artefact_ids"] = [
        "ART-EV-2021-003-001",
        "ART-EV-2021-003-002",
        "ART-EV-2021-003-003",
        "ART-EV-2022-008-002",
        "ART-EV-2022-008-003",
    ]

    # Rewrite the rubric: reward the supersession cite, do NOT penalise it.
    q["rubric_subpoints"] = [
        {
            "id": "C5.sub1",
            "max_score": 0.30,
            "criterion": (
                "The answer must recall the three 2021-05-22 evidence items "
                "(slack_thread by P-0035, meeting_notes by P-0005, "
                "incident_report by P-0035) and their roles. Full points if "
                "all three are recalled; half points if two are recalled; zero "
                "if fewer than two."
            ),
            "fail_criterion": "missing any of the three 2021-05-22 evidence items.",
        },
        {
            "id": "C5.sub2",
            "max_score": 0.30,
            "criterion": (
                "The answer must correctly distinguish each 2021-05-22 evidence "
                "item as direct testimony or inference per the corpus headers "
                "(slack_thread: direct, meeting_notes: inferred, "
                "incident_report: inferred)."
            ),
            "fail_criterion": "any 2021-05-22 evidence item is mislabeled.",
        },
        {
            "id": "C5.sub3",
            "max_score": 0.40,
            "criterion": (
                "The answer must surface the bi-temporal supersession: it "
                "must note that the load balancer attribution was later ruled "
                "out by the 2022-06-15 postmortem (ART-EV-2022-008-002) in "
                "favour of a DNS record misconfiguration. Full points if both "
                "the supersession AND the new DNS root cause are stated; half "
                "points if only one is stated; zero if the answer treats the "
                "LB hypothesis as the current truth."
            ),
            "fail_criterion": (
                "The answer presents the LB hypothesis as the final / current "
                "root cause without noting the 2022-06-15 supersession."
            ),
        },
    ]

    # Re-tag the question category to flag the bi-temporal element.
    q.setdefault("metadata", {})
    q["metadata"]["audit_notes"] = (
        "Patched 2026-05-26 to incorporate the 2022-06-15 supersession that "
        "the original GT silently ignored. The corpus's own cross-references "
        "on ART-EV-2021-003-001 marked it as `retroactively_corrected_by` "
        "ART-EV-2022-008-002. See CHANGELOG."
    )
    return "Q-0010 rewritten to reward bi-temporal supersession; LB→DNS; +2 evidence; new C5.sub3"

def patch_Q_0011(q: dict) -> str:
    """C6 Q-0011: conflict IS resolved (DNS root cause); also drop phantom -001."""
    gt = q["ground_truth_answer"]
    gt["resolution_status"] = "resolved"
    gt["resolution_details"] = (
        "Resolved at the 2022-06-15 postmortem (ART-EV-2022-008-002). The "
        "team agreed that DNS record misconfiguration was the root cause of "
        "the 2021-05-22 outage and Arjun Mehta explicitly stated that the "
        "load balancer misconfiguration had been ruled out. Luis Hernandez "
        "and Arjun Mehta agreed to update the incident response playbook to "
        "include DNS health checks and to add a pre-deployment DNS "
        "verification step; Omar Khaled was assigned to draft the playbook "
        "changes and Omar Farah was assigned to update the ops checklist. "
        "ART-EV-2022-008-003 (Slack, same day) confirms the resolution."
    )

    # Drop the phantom artifact (does not exist on disk).
    q["evidence_artefact_ids"] = [
        e for e in q.get("evidence_artefact_ids", [])
        if e != "ART-EV-2022-008-001"
    ]

    # Invert sub3 so "resolved" is the correct answer.
    for sp in q["rubric_subpoints"]:
        if sp["id"] == "C6.sub3":
            sp["criterion"] = (
                "The answer must state that the conflict between the two "
                "claims was resolved at the 2022-06-15 postmortem in favour "
                "of the DNS record misconfiguration being the root cause; "
                "the load balancer hypothesis was ruled out and the team "
                "updated the incident response playbook to include DNS "
                "health checks."
            )
            sp["fail_criterion"] = (
                "The answer claims the conflict is unresolved, or fails to "
                "identify DNS as the resolution and the playbook update as "
                "the remediation."
            )

    q.setdefault("metadata", {})
    q["metadata"]["audit_notes"] = (
        "Patched 2026-05-26. Original GT said `unresolved`; corpus "
        "(ART-EV-2022-008-002 + -003) explicitly resolves in favour of DNS. "
        "Phantom ART-EV-2022-008-001 removed from evidence_artefact_ids "
        "(file does not exist on disk)."
    )
    return "Q-0011 resolution_status flipped to `resolved`; phantom -2022-008-001 removed; C6.sub3 inverted"

def patch_Q_EMG_0000(q: dict) -> str:
    """Q-EMG-0000 facet 0: 'until 2022' contradicted by F0-1 (2023-10-11)."""
    changed = False
    # Patch GT facet text if present
    gt = q.get("ground_truth_answer", {})
    facets = gt.get("facets")
    if isinstance(facets, list):
        for f in facets:
            if isinstance(f, dict):
                txt = f.get("text") or f.get("description") or ""
                if "until 2022" in txt:
                    new_txt = txt.replace("until 2022", "through at least 2023")
                    if "text" in f: f["text"] = new_txt
                    if "description" in f: f["description"] = new_txt
                    changed = True
    # Patch rubric subpoint criterion
    for sp in q.get("rubric_subpoints", []):
        crit = sp.get("criterion") or ""
        if "until 2022" in crit:
            sp["criterion"] = crit.replace("until 2022", "through at least 2023")
            changed = True
        fc = sp.get("fail_criterion") or ""
        if "until 2022" in fc:
            sp["fail_criterion"] = fc.replace("until 2022", "through at least 2023")
            changed = True
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Facet 0 'until 2022' contradicted by evidence "
        "artifact EMG-P00-F0-1 (2023-10-11). Updated to 'through at least 2023'."
    )
    return f"Q-EMG-0000 facet 0 date corrected (until-2022 → through-2023); changed={changed}"

def patch_Q_EMG_0002(q: dict) -> str:
    """Q-EMG-0002 facet 2: '12-Feb-2022' is wrong; F1-0 is 2022-07-16."""
    changed = False
    needles = ("12-Feb-2022", "12 February 2022", "2022-02-12", "February 12, 2022")
    repl = "16-Jul-2022"
    gt = q.get("ground_truth_answer", {})
    facets = gt.get("facets")
    if isinstance(facets, list):
        for f in facets:
            if isinstance(f, dict):
                for key in ("text", "description"):
                    if key in f and isinstance(f[key], str):
                        for n in needles:
                            if n in f[key]:
                                f[key] = f[key].replace(n, repl); changed = True
    for sp in q.get("rubric_subpoints", []):
        for key in ("criterion", "fail_criterion"):
            if key in sp and isinstance(sp[key], str):
                for n in needles:
                    if n in sp[key]:
                        sp[key] = sp[key].replace(n, repl); changed = True
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Facet 2 date '12-Feb-2022' corrected to "
        "'16-Jul-2022' (actual date of evidence artifact EMG-P02-F1-0)."
    )
    return f"Q-EMG-0002 facet 2 date corrected (12-Feb-2022 → 16-Jul-2022); changed={changed}"

def patch_Q_EMG_0001(q: dict) -> str:
    """Q-EMG-0001: 'often swaying' overstatement; reaction-vs-email-text dual mechanism."""
    changed = False
    for sp in q.get("rubric_subpoints", []):
        for key in ("criterion", "fail_criterion"):
            v = sp.get(key)
            if isinstance(v, str):
                if "often swaying" in v.lower():
                    sp[key] = v.replace("often swaying", "and could sway")
                    sp[key] = sp[key].replace("often Swaying", "and could sway")
                    changed = True
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Softened 'often swaying' → 'and could sway' "
        "(only two corpus instances support the causal claim). Approval "
        "mechanism is dual (email text OR Slack reaction) per F2-0 vs F2-1; "
        "answers describing either are corpus-faithful."
    )
    return f"Q-EMG-0001 softened 'often swaying' qualifier; changed={changed}"


def patch_Q_0001(q: dict) -> str:
    """C1 Q-0001: clarify that change_date refers to the cloud-native supersession
    event (2022-08-20), not the 90-day policy adoption (2022-05-01). Remove the
    phantom artifact ART-EV-2022-013-001 from evidence_artefact_ids."""
    # Remove phantom artifact (does not exist on disk).
    q["evidence_artefact_ids"] = [
        e for e in q.get("evidence_artefact_ids", [])
        if e != "ART-EV-2022-013-001"
    ]

    # Add scoping note to the GT so judges/evaluators know the temporal frame.
    gt = q["ground_truth_answer"]
    gt.setdefault("scope_note",
        "The data retention policy went through TWO state transitions: "
        "(1) 2022-05-01 — the 180-day policy was superseded by a new 90-day "
        "policy (EV-2022-012, approved by Arjun Mehta and Maya Patel). "
        "(2) 2022-08-20 — the 90-day policy was in turn superseded by the "
        "cloud-native microservices architecture decision (EV-2022-013, "
        "approved by Arjun Mehta and Omar Farah). The GT's change_date / "
        "change_reason refer to (2), the most-recent supersession, because "
        "ART-EV-2022-013-002 explicitly frames the cloud-native decision as "
        "'replacing the existing data retention policy.' Answers that report "
        "either transition (2022-05-01 OR 2022-08-20) with corpus-accurate "
        "actors and rationale should be accepted; both are corpus-faithful "
        "reads of the policy's evolution.")

    # Loosen sub3 (date) and sub4 (reason) to accept either transition.
    for sp in q.get("rubric_subpoints", []):
        if sp["id"] == "C1.sub3":
            sp["criterion"] = (
                "The answer must give either 2022-08-20 (most-recent supersession by "
                "the cloud-native microservices decision) OR 2022-05-01 (when the "
                "90-day policy itself was first adopted). Either date is corpus-"
                "faithful; only zero credit if no policy-change date is given."
            )
            sp["fail_criterion"] = (
                "no policy-change date given, or a date unrelated to either "
                "EV-2022-012 (2022-05-01) or EV-2022-013 (2022-08-20)."
            )
        elif sp["id"] == "C1.sub4":
            sp["criterion"] = (
                "The answer must give a corpus-faithful rationale matching the "
                "transition cited in sub3. For 2022-05-01: customer-log data-"
                "privacy audit flagged risk of retaining logs beyond 90 days. "
                "For 2022-08-20: rapid Helix Fleet scaling needs and data-privacy "
                "concerns raised by a major customer. Award full credit for either "
                "matching rationale."
            )
            sp["fail_criterion"] = (
                "no rationale, or a rationale not present in either EV-2022-012 "
                "or EV-2022-013 artifacts."
            )

    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Loosened sub3/sub4 to accept either of the two "
        "policy transitions (2022-05-01 90-day adoption OR 2022-08-20 cloud-"
        "native supersession). Both are corpus-faithful reads of the policy "
        "evolution. Phantom ART-EV-2022-013-001 removed from "
        "evidence_artefact_ids (file does not exist)."
    )
    return "Q-0001 sub3/sub4 accept either policy transition; phantom -2022-013-001 removed"

def patch_Q_0002(q: dict) -> str:
    """C2 Q-0002: 'Maintain spreadsheet integration with incremental automation'
    is in source_of_truth metadata only — NOT in corpus text. Only the hybrid
    alternative is corpus-recoverable. Rewrite sub3 to require only the
    hybrid alternative."""
    for sp in q.get("rubric_subpoints", []):
        if sp["id"] == "C2.sub3":
            sp["criterion"] = (
                "The answer must mention the hybrid alternative ("
                "spreadsheet connectors combined with a new API layer) — this "
                "is the only alternative explicitly stated in corpus text "
                "(ART-EV-2021-001-001, [09:06:30] Arjun Mehta). "
                "A second alternative listed in source-of-truth metadata "
                "(maintain spreadsheet with incremental automation) is NOT "
                "in any corpus artifact and cannot be required from "
                "corpus-grounded answers. Award full credit if the hybrid "
                "alternative is mentioned; partial credit if only a vague "
                "'other options were considered' framing."
            )
            sp["fail_criterion"] = (
                "no alternative is mentioned at all, or only the "
                "source-of-truth-only alternative is cited (the latter would "
                "indicate metadata leakage)."
            )
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. C2.sub3 rewritten to require only the hybrid "
        "alternative (the only one in corpus text). The 'maintain spreadsheet "
        "with incremental automation' alternative exists ONLY in "
        "source_of_truth metadata and is unrecoverable by any corpus-only "
        "retrieval system."
    )
    return "Q-0002 C2.sub3 narrowed to the corpus-recoverable hybrid alternative only"

def patch_Q_0003(q: dict) -> str:
    """C2 Q-0003: BOTH alternatives are source-of-truth metadata only —
    neither is in corpus text. Soften sub3 to accept any alternative reasoning
    or note that this subpoint is structurally unsatisfiable from corpus."""
    for sp in q.get("rubric_subpoints", []):
        if sp["id"] == "C2.sub3":
            sp["criterion"] = (
                "The answer must acknowledge that alternative architectures "
                "were considered (e.g. maintaining the monolith with "
                "incremental refactoring, or a hybrid cloud approach with "
                "legacy services on-premises). NOTE: corpus artifacts "
                "(ART-EV-2022-013-002/003) describe the cloud-native decision "
                "but do NOT enumerate alternatives in the text — these "
                "alternatives appear only in source-of-truth metadata. "
                "Award full credit for any mention of monolith-maintenance OR "
                "hybrid-cloud reasoning; partial credit for a generic "
                "'other options were weighed' framing; zero only if no "
                "alternative reasoning appears at all."
            )
            sp["fail_criterion"] = (
                "no alternative reasoning is mentioned, even loosely."
            )
    # Drop phantom artifact.
    q["evidence_artefact_ids"] = [
        e for e in q.get("evidence_artefact_ids", [])
        if e != "ART-EV-2022-013-001"
    ]
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. C2.sub3 substantially loosened: BOTH alternatives "
        "in the original GT exist only in source_of_truth metadata, not in any "
        "corpus artifact text, making the original subpoint structurally "
        "unsatisfiable by a corpus-grounded system. Phantom "
        "ART-EV-2022-013-001 removed from evidence_artefact_ids."
    )
    return "Q-0003 C2.sub3 loosened (both alternatives are source-of-truth-only); phantom -2022-013-001 removed"

def patch_Q_0005(q: dict) -> str:
    """C3 Q-0005: GT is content-faithful; just drop the phantom -001 artifact."""
    q["evidence_artefact_ids"] = [
        e for e in q.get("evidence_artefact_ids", [])
        if e != "ART-EV-2022-008-001"
    ]
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Phantom ART-EV-2022-008-001 removed from "
        "evidence_artefact_ids (file does not exist on disk). GT content is "
        "fully derivable from -002 and -003."
    )
    return "Q-0005 phantom -2022-008-001 removed; GT content unchanged (already corpus-faithful via secondary artifacts)"

def patch_Q_0007(q: dict) -> str:
    """C4 Q-0007: GT is content-faithful; just drop the phantom -001 artifact."""
    q["evidence_artefact_ids"] = [
        e for e in q.get("evidence_artefact_ids", [])
        if e != "ART-EV-2022-013-001"
    ]
    q.setdefault("metadata", {})["audit_notes"] = (
        "Patched 2026-05-26. Phantom ART-EV-2022-013-001 removed from "
        "evidence_artefact_ids (file does not exist on disk). GT content is "
        "fully derivable from -002 and -003."
    )
    return "Q-0007 phantom -2022-013-001 removed; GT content unchanged (already corpus-faithful via secondary artifacts)"


PATCHES = {
    "Q-0001":     patch_Q_0001,
    "Q-0002":     patch_Q_0002,
    "Q-0003":     patch_Q_0003,
    "Q-0005":     patch_Q_0005,
    "Q-0007":     patch_Q_0007,
    "Q-0010":     patch_Q_0010,
    "Q-0011":     patch_Q_0011,
    "Q-EMG-0000": patch_Q_EMG_0000,
    "Q-EMG-0001": patch_Q_EMG_0001,
    "Q-EMG-0002": patch_Q_EMG_0002,
}

# ─── Driver ──────────────────────────────────────────────────────────────────

def main() -> int:
    if not SRC.exists():
        print(f"ERROR: backup missing at {SRC}. Restore from VCS first.", file=sys.stderr)
        return 2

    qs = [json.loads(line) for line in SRC.read_text().splitlines() if line.strip()]
    by_id = {q["id"]: q for q in qs}

    summary = []
    for qid, fn in PATCHES.items():
        q = by_id.get(qid)
        if q is None:
            summary.append(f"  ! {qid}: NOT FOUND in benchmark — patch skipped")
            continue
        msg = fn(q)
        summary.append(f"  ✓ {qid}: {msg}")

    DST.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in qs) + "\n")

    stamp = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    header = f"\n## {stamp} — {PATCH_VERSION}\n\n"
    body = "\n".join(summary) + "\n"
    if CHG.exists():
        CHG.write_text(CHG.read_text() + header + body)
    else:
        CHG.write_text(
            "# helix-small benchmark CHANGELOG\n\n"
            "Patches applied to `benchmark_v0.0.jsonl`. The pristine pre-patch "
            "file lives at `benchmark_v0.0.original.jsonl` and is never "
            "modified by this script.\n" + header + body
        )

    print(f"Patched {DST.relative_to(ROOT)}")
    print(f"  source: {SRC.name}")
    print(f"  rows:   {len(qs)}")
    print(f"  patches:")
    print("\n".join(summary))
    print(f"  changelog: {CHG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
