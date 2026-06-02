# helix-small benchmark CHANGELOG

## 2026-05-26 — corpus-name-typo-fix-maya-singh

  Investigated "Maya Singh" flagged during Q-0009 testing (ART-EV-2021-002-002).

  Finding: "Maya Singh" is a generation-time typo for "Maya Patel" (P-0001, CEO). Evidence:
  (1) No persona named "Maya Singh" exists in personas.jsonl; the only Mayas are P-0001/P-0003
      (Maya Patel, CEO) and P-0007 (Maya Rojas, VP of Product, joined 2023-01-10 — post-dates
      both affected artifacts).
  (2) EV-2021-002 source-of-truth participants are P-0005, P-0011, P-0037; no Maya in the
      canonical record.
  (3) EV-2021-006 source-of-truth participants are P-0005, P-0037; no Maya in the canonical
      record.
  (4) "Maya Singh" appeared in exactly two artifacts (both Daniel Ortiz meeting notes, genre:
      meeting_notes, testimony_type: inferred), never elsewhere in the corpus.
  (5) In both artifacts the "Maya" voice is consistent with Maya Patel's CEO/Product role and
      2021 tenure.
  Scenario A applied.

  ✓ ART-EV-2021-002-002: "Maya Singh (Product)" → "Maya Patel (Product)" in Attendees header;
    "@Maya Singh" → "@Maya Patel" in Action items.
  ✓ ART-EV-2021-006-002: "Maya Singh" → "Maya Patel" in Attendees header.
  ✓ Collateral sweep: no other "Maya Singh" instances found outside these two artifacts.

Patches applied to `benchmark_v0.0.jsonl`. The pristine pre-patch file lives at `benchmark_v0.0.original.jsonl` and is never modified by this script.

## 2026-05-26 — formalization-trap-artifacts

Planted three formalization-trap corpus artifacts to ground the EMERGENT.sub8 fail conditions for Q-EMG-0000, Q-EMG-0001, and Q-EMG-0002. Prior to this patch the rubric cited formal documents that did not exist in the corpus, so the trap only fired on outright hallucination. These artifacts make the trap corpus-grounded: a retrieval system that surfaces any of these docs as authoritative without temporal qualification will lose the EMERGENT.sub8 (or EMERGENT.sub7 for Q-EMG-0002) point.

  + ATM-doc-onboarding-playbook-202403-0006.md — Helix Customer Onboarding Playbook v1.0, dated 2024-03-14, authored by Priya Nair (P-0009). Formalizes Discovery/Configuration/Training/Go-Live/QBR stages, Slack channel naming conventions, SLA matrix. Distractor for Q-EMG-0000 (question asks about pre-playbook 2020-2023 de-facto process).
  + ATM-doc-adr-process-202403-0007.md — Architecture Decision Records Process Charter v1.0, dated 2024-03-21, authored by Daniel Kim (P-0008). Formalizes ADR template, Review Board quorum (Daniel Kim chair, Arjun Mehta, Sophia Liu, Miguel Torres), voting thresholds, archival rules. Distractor for Q-EMG-0001 (question asks about pre-ADR 2020-2023 de-facto pattern).
  + ATM-doc-tech-charter-202303-0008.md — Helix Technical Decision-Making Charter v1.0, dated 2023-03-06, authored by Daniel Kim (P-0008). Designates Daniel Kim as Official Technical Lead with formal sign-off authority over all medium+ complexity decisions. Distractor for Q-EMG-0002 (question asks about de-facto 2022 authority; charter post-dates hypergrowth and names Daniel Kim, not Arjun Mehta).
  + corpus_index.jsonl: three new entries appended with role=secondary, genre=notion_doc, testimony_type=direct, distractor_for, and planted_date fields.
  + benchmark_v0.0.jsonl: formalization field in Q-EMG-0000/0001/0002 ground_truth_answer updated to cite the corpus slot_id of each planted artifact so the EMERGENT.sub8 fail_if condition is now corpus-grounded.

## 2026-05-26 — corpus-name-typo-fix-EV-2021-006

  ✓ ART-EV-2021-006-001: standalone `@Daniel` mention → `@DanielOrtiz` (P-0037) in @SofiaLee's Slack message
  ✓ ART-EV-2021-006-002: attendee "Arjun Patel" → "Arjun Mehta" (P-0005) in meeting notes header
  ✓ ART-EV-2021-006-003: all 3 occurrences of "Daniel Patel" → "Daniel Ortiz" (P-0037) in email thread (To: header, reply From: line, Maya's To: line)
  ✓ Collateral sweep: no "Daniel Patel" or "Arjun Patel" instances found outside EV-2021-006

## 2026-05-26T19:35:18Z — v0.0.1-bench-audit-2026-05-26

  ✓ Q-0001: Q-0001 sub3/sub4 accept either policy transition; phantom -2022-013-001 removed
  ✓ Q-0002: Q-0002 C2.sub3 narrowed to the corpus-recoverable hybrid alternative only
  ✓ Q-0003: Q-0003 C2.sub3 loosened (both alternatives are source-of-truth-only); phantom -2022-013-001 removed
  ✓ Q-0005: Q-0005 phantom -2022-008-001 removed; GT content unchanged (already corpus-faithful via secondary artifacts)
  ✓ Q-0007: Q-0007 phantom -2022-013-001 removed; GT content unchanged (already corpus-faithful via secondary artifacts)
  ✓ Q-0010: Q-0010 rewritten to reward bi-temporal supersession; LB→DNS; +2 evidence; new C5.sub3
  ✓ Q-0011: Q-0011 resolution_status flipped to `resolved`; phantom -2022-008-001 removed; C6.sub3 inverted
  ✓ Q-EMG-0000: Q-EMG-0000 facet 0 date corrected (until-2022 → through-2023); changed=True
  ✓ Q-EMG-0001: Q-EMG-0001 softened 'often swaying' qualifier; changed=True
  ✓ Q-EMG-0002: Q-EMG-0002 facet 2 date corrected (12-Feb-2022 → 16-Jul-2022); changed=True

## 2026-05-26 — primary-artifact-repair-EV-2022-008-EV-2022-013

  ✓ ART-EV-2022-008-001 (new): Primary postmortem for EV-2022-008 written and placed at
    corpus/EV-2022-008/ART-EV-2022-008-001.md (~6.6 KB). Genre: postmortem. Author: P-0005.
    Establishes DNS record misconfiguration as the corrected root cause of the 2021-05-22 outage;
    rules out the load-balancer hypothesis via config-snapshot and DNS-log evidence;
    includes revised timeline (2021-05-21 DNS record change through 2022-06-15 correction),
    contributing factors, remediation action items, and lessons learned.
    Cross-reference: retroactively_corrects ART-EV-2021-003-001.

  ✓ ART-EV-2022-013-001 (new): Primary meeting_transcript for EV-2022-013 written and placed at
    corpus/EV-2022-013/ART-EV-2022-013-001.md (~4.8 KB). Genre: meeting_transcript. Author: P-0005.
    Records the 2022-08-20 Arjun Mehta / Omar Farah decision to shift to cloud-native microservices,
    including rationale (Fleet scaling, major-customer data-privacy requirement), two alternatives
    considered (incremental monolith refactoring; hybrid cloud on-prem sidecar), explicit
    supersession of the 90-day data-retention policy (EV-2022-012), and the monolith decommission
    target of Q3 2023. Originates the transcription-error note that "Omar Khaled" was a mis-read
    for "Omar Farah" (propagated into secondary ART-EV-2022-013-002).
    Cross-reference: supersedes ART-EV-2022-006-001.

  ✓ corpus_index.jsonl: Two new lines appended for ART-EV-2022-008-001 and ART-EV-2022-013-001.

  ✓ benchmark_v0.0.jsonl: Primary artifact IDs restored to evidence_artefact_ids:
      Q-0001  += ART-EV-2022-013-001 (appended to EV-2022-013 cluster)
      Q-0003  += ART-EV-2022-013-001 (prepended, as in original)
      Q-0005  += ART-EV-2022-008-001 (prepended, as in original)
      Q-0007  += ART-EV-2022-013-001 (appended to EV-2022-013 cluster)
      Q-0011  += ART-EV-2022-008-001 (prepended, as in original)

## 2026-05-26 — gt-audit-q0008-bi-temporal-expansion-and-c5-label-normalisation

  ✓ Q-0008 (Task 1 — interpretation B): ART-EV-2022-007-001 materially reverses the
    API-first pivot claim (actual decision was cloud-based analytics platform), making
    this structurally identical to the Q-0010 LB-to-DNS pattern. GT expanded to
    include the 2022-05-10 supersession as a 4th evidence item
    (ART-EV-2022-007-001, slack_thread, direct). Question text updated to
    explicitly invite inclusion of correction records. GT claim updated to
    describe both the original (2021-04-15) and superseded (2022-05-10) accounts.
    Rubric restructured: sub1+sub2 cover the 3 original evidence items (max 0.25
    each); sub3 (max 0.5) rewards surfacing the supersession. metadata.audit_notes
    added explaining the interpretation choice.

  ✓ Q-0008 / Q-0009 / Q-0010 (Task 2 — testimony label normalisation): All
    testimony_attribution[*].testimony_type values standardised to corpus-header
    convention: "direct_testimony" → "direct", "inference" → "inferred". Rubric
    criterion text updated accordingly (example: Q-0009 C5.sub2 before:
    "slack_thread: direct_testimony, meeting_notes: inference, email_thread:
    direct_testimony" → after: "slack_thread: direct, meeting_notes: inferred,
    email_thread: direct"). No other fields changed.

## 2026-05-26 — corpus-incoherence-fix-EV-2022-007

  ✓ ART-EV-2022-007-001 (primary slack_thread): Rewrote to establish a coherent two-layer bi-temporal narrative.
    - Removed the incoherent 09:08 line that named "spreadsheet integration" as the prior documented belief.
    - Replaced with a clear establishment that the 2021-04-15 record has always said "API-first architecture" (the superseded belief, valid_at 2021-04-15).
    - 09:12 Maya correction now flows cleanly from that: the actual pivot was to cloud-based analytics platform (the corrected truth, correction_recorded_at 2022-05-12).
    - Luis Hernandez confirmation added to reinforce the original-belief → corrected-belief arc without telegraphing the answer.
    - Thread remains ~30+ lines; metadata header and cross-reference blocks preserved unchanged.
  ✓ ART-EV-2022-007-002 (secondary meeting_notes): Fixed the Discussion section.
    - Removed the incoherent Arjun line stating "the 2021 record still lists a spreadsheet-centric pivot".
    - Replaced with: the 2021-04-15 record documents API-first (consistent with -001 and EV-2021-001).
    - Maya's correction line now reads: API-first framing was inaccurate; actual decision was cloud-based analytics platform.
    - All other sections (Agenda, Decisions, Action items, Open questions) left unchanged.

## 2026-05-26 — q0008-revert-to-interpretation-a

Reverted Q-0008 GT from interpretation B (full evidence chain incl. supersession) back to interpretation A (pure C5 evidence chain) per C5 design intent. The 2022-05-10 supersession is now explicitly NOT treated as evidence for the original API-first pivot — C5.sub3 instructs the rubric to treat it as a later correction belonging to Q-0010 (C5+supersession) and Q-0011 (C6 contradiction) test coverage, not Q-0008's pure C5 evidence-chain walk. Restored 3 evidence items, 3 subpoints @ 0.333.

## 2026-05-26 — q0003-sub3-retightening

Re-tightened Q-0003 C2.sub3 to require both alternatives now that ART-EV-2022-013-001 has both monolith-refactoring + hybrid-cloud paths mentioned in dialogue (scattered, not enumerated). Q-0002's sub3 stays loosened since the 'maintain spreadsheet' alternative is still SoT-only.

## 2026-05-26 — natural-language question rewording (14 questions)

Reworded 11 of 14 helix-small question texts to remove benchmark-design artifacts ("the system", "your statement / your claim / your conclusion", and similar test-shape framings) and replace them with phrasings a person would actually use.

Key changes:
- C1 / C2 — light smoothing (Q-0001, Q-0002, Q-0003)
- C3 — dropped "the system's understanding" → "your current understanding" (Q-0004, Q-0005, Q-0006)
- C4 — dropped "reconstruct the knowledge held by the system" → "what did you know about ... as of" (Q-0007)
- C5 — dropped the "your statement / your claim / your conclusion" framing entirely; replaced with "tell me about X — walk me through the supporting records, and for each, say whether it's direct testimony or an inference" (Q-0008, Q-0009, Q-0010). C5 RUBRIC UNCHANGED — the new wording still elicits the enumerate-evidence + classify direct/inferred answer shape the existing rubric grades.
- C6 — dropped the "conflict between these two claims" tip-off while keeping both party names + dates (per C6 design) (Q-0011)
- EMG — already natural, intentionally unchanged (Q-EMG-0000/0001/0002)

All GTs and rubrics are unchanged from their state at the start of this rewording. The prior question text for each touched row is preserved at `metadata.text_pre_rewording_2026_05_26`.

## 2026-06-01 — emergent category removed from small tier

Removed the 3 emergent-pattern questions (Q-EMG-0000, Q-EMG-0001, Q-EMG-0002) from benchmark_v0.0.jsonl (14 -> 11 questions). The emergent-pattern category is deferred to the large tier and above, where a deep behavioural corpus makes the patterns reconstructable and comparable; it is not meaningful at small/medium scale (medium never generated it). Generator Stage G is now gated to large+ (helix_corpus/cli.py).

The 34 emergent-evidence background documents in corpus/_emergent/ are RETAINED as benign background noise so that the per-question scores already measured over the corpus-as-shipped remain valid (recalculation is a re-aggregation over the remaining 11 questions, not a re-run). Pre-removal benchmark preserved at benchmark_v0.0.jsonl.pre-emg-removal.jsonl.
