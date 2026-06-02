# helix-medium benchmark CHANGELOG

## 2026-05-26 — slot-id-collision-fix-wave-1

**Scope:** `corpus/` (file renames only, no content edits), `corpus_index.jsonl` (rebuilt), `benchmark_v0.0.jsonl` (`evidence_artefact_ids` updates only)

**Root cause:** The Stage C corpus generator reset its slot-ID counter to `-001` on each new generation batch while the event-ID counter kept advancing. This produced 443 corpus files with only 311 unique slot_ids. 24 slot_ids appeared 2–10 times across different event directories.

### 1. File renames applied: 140

Every file whose `slot_id:` header did not match the canonical convention for its containing directory was renamed. Rule applied:

> A file in `corpus/EV-YYYY-NNN/` must carry slot_id `ART-EV-YYYY-NNN-PPP`, where PPP is the three-digit position suffix from the original filename.

Both the filename on disk and the `slot_id:` header value were updated. No artifact body content was altered.

Key collision groups resolved:

| Old slot_id prefix (shared) | Occurrences | Directories affected (renamed to correct NNN) |
|---|---|---|
| `ART-EV-2023-001-{001-003}` | 5× | EV-018, 026, 058, 074, 115 |
| `ART-EV-2023-002-{001-003}` | 6× | EV-003, 027, 035, 051, 123, 147 |
| `ART-EV-2023-003-{001-003}` | 3× | EV-012, 020, 036 |
| `ART-EV-2023-004-{001-003}` | 5–6× | EV-045, 053, 077, 085, 093, 133 |
| `ART-EV-2023-005-{001-003}` | 2–4× | EV-022, 062, 086, 118 |
| `ART-EV-2023-006-{001-002}` | 9× | EV-015, 023, 047, 055, 095, 103, 111, 119, 143 |
| `ART-EV-2023-007-{001-003}` | 7× | EV-016, 056, 072, 096, 136, 144, 152 |
| `ART-EV-2023-008-{001-002}` | 9× | EV-017, 025, 033, 041, 049, 073, 105, 113, 129 |

### 2. corpus_index.jsonl rebuilt from scratch

443 entries, 0 duplicate slot_ids. Each entry: `{"slot_id": "...", "path": "corpus/EV-YYYY-NNN/ART-EV-YYYY-NNN-PPP.md", "event_id": "EV-YYYY-NNN"}`.

### 3. benchmark_v0.0.jsonl — evidence_artefact_ids updated: 35 questions

All `ART-EV-2023-001-*` phantom citations were resolved by GT context (question text and ground_truth_answer content). `EV-2023-001` does not exist in `source_of_truth/events.jsonl`; events begin at `EV-2023-002`.

| Phantom cite | GT match | Resolved to | Questions |
|---|---|---|---|
| `ART-EV-2023-001-{001-003}` | Priority Queue ticket triage (Nia Osei + Diego Alvarez) | `ART-EV-2023-058-{001-003}` | Q-0001–Q-0015 (C1), Q-0038–Q-0052 (C4), Q-0024 (C2), Q-0069 (C6) |
| `ART-EV-2023-001-{001-003}` | B2C marketplace pivot (Maya Patel + Daniel Kim) | `ART-EV-2023-026-{001-003}` | Q-0020 (C2) |
| `ART-EV-2023-001-{001-003}` | MongoDB→PostgreSQL migration (Daniel Kim + Mei Lin) | `ART-EV-2023-074-{001-003}` | Q-0027 (C2) |
| `ART-EV-2023-001-{001-003}` | Shipment tracking failure / emergency sprint | `ART-EV-2023-018-{001-003}` | Q-0066 (C5) |

Non-`001` colliding slots cited in the benchmark (e.g. `ART-EV-2023-002-*`, `ART-EV-2023-006-*`, etc.) already referenced the home-directory version, which was not renamed. No changes needed for those cites.

### 4. Remaining issues for wave-2 category agents

The following slot_ids are cited in `benchmark_v0.0.jsonl` but have no corresponding file in `corpus_index.jsonl`. The artifact was never generated for the home event directory. Citations left intact (not removed or silently re-pointed).

| Missing slot_id | Home dir | Questions affected |
|---|---|---|
| `ART-EV-2023-002-003` | `corpus/EV-2023-002/` | Q-0002 (C1), Q-0039 (C4), Q-0053 (C5) |
| `ART-EV-2023-006-003` | `corpus/EV-2023-006/` | Q-0013 (C1), Q-0019 (C2), Q-0050 (C4), Q-0064 (C5) |
| `ART-EV-2023-066-001` | `corpus/EV-2023-066/` | Q-0025 (C2) |

Note: files with these slot_ids existed in OTHER directories and have been renamed to their correct per-directory slot_ids. The home-directory instances were simply never generated.

**Total unresolved benchmark cites after wave-1: 8** (across 8 questions, 3 distinct slot_ids)

---

## 2026-05-26 — persona-registry-and-name-typo-fixes

Persona registry disambiguation, missing persona additions, and corpus
surname-typo repairs. Covers PART A (duplicate display names), PART B
(missing personas), and PART C (surname typos).

### PART A — Duplicate display name disambiguation

Two display-name collisions existed in `helix_canon/personas.jsonl`:

**Daniel Kim (P-0002 vs P-0035)**
- P-0002 is the canonical CTO/founder; display name unchanged.
- P-0035 (QA Engineer, long-tail) renamed: `Daniel Kim` → `Daniel R. Kim`.
- Corpus artifacts updated: EV-2023-080 (ART-001 and ART-002) — the layoff
  context refers to P-0035 ("Senior Product Engineer" being laid off), not
  the CTO/founder. All "Daniel Kim" in EV-2023-042 and EV-2023-074 left
  unchanged (CTO context, P-0002 signature phrases, CTO title in email sign-off).

**Marco Rossi (P-0033 vs P-0073)**
- P-0033 (UI/UX Designer, joined 2023, active) is the canonical referent for
  all 2023 corpus appearances; display name unchanged.
- P-0073 (DevOps Engineer, departed 2021) renamed: `Marco Rossi` → `Marco S. Rossi`.
- No corpus text required updating for P-0073: all post-2021 "Marco Rossi"
  occurrences are in 2023 events and therefore refer to P-0033 (active).

### PART B — Missing personas added

**P-0009 — Omar Al-Jabri (Sales Operations Leader)**
- P-0009 was referenced in C2 event EV-2023-002 and C5 events EV-2023-005,
  EV-2023-006, EV-2023-007, EV-2023-008 but absent from personas.jsonl.
- Context (meeting transcripts, incident reports, email threads) consistently
  identifies the author/participant as "Omar" in a senior ops/sales role,
  distinct from P-0029 (Omar Al-Jabri, Data Analyst, joined 2022). P-0009
  pre-dates P-0029, joined 2020, and has a sales-operations remit.
- Added P-0009 as Omar Al-Jabri, Head of Sales Operations, joined 2020.
- benchmark_v0.0.jsonl Q-0016: `deciders` field updated from `["Maya Patel",
  "P-0009"]` to `["Maya Patel", "Omar Al-Jabri"]`; matching rubric subpoint
  updated from "P-0009" to "Omar Al-Jabri".

**P-0090 — Sarah Patel (stub)**
- Appears in EV-2023-005, EV-2023-009, EV-2023-016, EV-2023-040, EV-2023-071,
  EV-2023-079, EV-2023-088, EV-2023-093, EV-2023-096, EV-2023-129,
  EV-2023-135, EV-2023-068 and others as Sales Ops Coordinator / Head of
  Data Ops. No canonical referent in original registry.
- Added as stub: Sales Operations Coordinator, joined 2022, long-tail.

**P-0091 — Ethan Kim (stub)**
- Appears in EV-2023-005 (Engineering Lead, Adobe XD) and EV-2023-112
  (dev perspective, sprint planning). No canonical referent; likely generation
  cross-contamination of "Ethan Brooks" + "Daniel Kim".
- Added as stub: Engineering Lead, joined 2022, long-tail.

**P-0092 — Emily Carter (stub)**
- Appears in EV-2023-070 (ART-EV-2023-070-003) as Chief Operating Officer
  communicating SLA policy. No canonical referent.
- Added as stub: Chief Operating Officer, joined 2021, left 2024, long-tail.

### PART C — Surname typo corpus fixes

**Luis Hernandez → Luis Ramirez (confirmed)**
- File: EV-2023-036/ART-EV-2023-003-002.md (2 occurrences)
- Confirmed by Q-0070 GT which cites ART-EV-2023-003-002 as evidence for
  "Luis Ramirez" in a hotfix deployment context.

**Miguel Alvarez → Miguel Torres (confirmed)**
- Files: EV-2023-123/ART-EV-2023-002-001.md, -002.md, -003.md (7 occurrences)
- Role: Business Development Representative (matches P-0055 Miguel Torres).
- Cross-contamination: "Miguel" (Torres first name) + "Alvarez" (Diego Alvarez
  surname). BDR role and freight-forwarding sales context uniquely match P-0055.

**Ethan Patel → Ethan Brooks (confirmed)**
- File: EV-2023-040/ART-EV-2023-040-002.md (1 occurrence, "Sales Lead" label)
- Author of the parent event is P-0027 (Luis Ramirez). Context: pilot
  discussion alongside Omar Al-Jabri. Engineering/field role aligns with P-0031
  Ethan Brooks (DevOps); "Patel" surname is cross-contamination.

### PART C — Ambiguous cases flagged for category-agent attention

The following names were NOT changed due to insufficient context to make a
confident canonical assignment:

- **Marco Ruiz** (EV-2023-028, Jan 2023): DevOps/rollback context. P-0033
  (Marco Rossi UI/UX) joined April 2023; P-0073 (Marco S. Rossi DevOps)
  departed March 2021. Neither persona overlaps cleanly with January 2023 date.
  Needs category-agent investigation.

- **Kevin Patel** (EV-2023-095): API architecture review. No "Kevin" persona
  in registry. Ambiguous; could be a stub hire or generation hallucination.
  Needs category-agent investigation.

- **Maya Lin** (EV-2023-067): API latency review, rate-limiting and Grafana
  alerts context. Could be cross-contamination of "Maya" (Patel/Chen/Singh)
  + "Lin" (Mei Lin surname). Ambiguous; neither fits cleanly by role or date.
  Needs category-agent investigation.

- **Luis Martinez** (EV-2023-112): Sprint planning, client deadline pressure.
  P-0027 Luis Ramirez (SDR) doesn't match PM-style behaviour here. Could be
  a separate stub or generation hallucination. Needs category-agent investigation.

### Summary counts

- Persona display-name disambiguations: 2 (P-0035, P-0073)
- New persona rows added: 4 (P-0009, P-0090, P-0091, P-0092)
- Corpus artifact surname fixes applied: 3 (Luis Hernandez, Miguel Alvarez,
  Ethan Patel)
- Corpus files modified: 7
- Benchmark GT fields changed: 2 (Q-0016 deciders + rubric subpoint)
- Ambiguous cases flagged: 4 (Marco Ruiz, Kevin Patel, Maya Lin, Luis Martinez)

## 2026-05-26 — gt-generator-bug-fixes-c5-labels-sot-attribution

Three generator bugs fixed across `benchmark_v0.0.jsonl` (BUG 1 + BUG 2) and
`source_of_truth/events.jsonl` (BUG 3).

### BUG 1 — C5 `inferential_steps` char-array (0 fixes applied)

Audit finding: the char-array bug (`list(reason_string)` instead of
`[reason_string]`) was NOT present in the medium-tier data. All 15 C5 rows
already carried `inferential_steps` as a plain string (matching small-tier
post-fix convention). No changes made to this field.

### BUG 2 — C5 testimony-label drift (90 fixes across 15 rows)

`ground_truth_answer.testimony_attribution[*].testimony_type` and
`ground_truth_answer.evidence_summary[*]` strings in every C5 row used
generator-internal labels instead of corpus-artifact-header labels.

Normalisation applied (matches small-tier convention from
`gt-audit-q0008-bi-temporal-expansion-and-c5-label-normalisation`):

  - `"direct_testimony"` → `"direct"`   (testimony_attribution + evidence_summary)
  - `"inference"` → `"inferred"`        (testimony_attribution + evidence_summary)

Counts:
  - `testimony_attribution` fixes: 45  (3 per row × 15 C5 rows)
  - `evidence_summary` string fixes:  45  (3 per row × 15 C5 rows)
  - Total field changes: 90

No other fields touched (question text, rubric subpoints, inferential_steps,
slot_ids, persona IDs all unchanged).

### BUG 3 — SoT summary field persona drift (2 events)

`source_of_truth/events.jsonl` EV-2023-054 and EV-2023-055 had `summary`
fields naming "Ethan Brooks (P-0051)" while the `decision` field in both
events correctly named "Diego Alvarez" as P-0051. The persona mapping in
`helix_canon/personas.jsonl` designates P-0051 as Diego Alvarez.

Fix: replaced `"Ethan Brooks (P-0051)"` → `"Diego Alvarez (P-0051)"` in
`summary` for both events. `decision` fields were already correct and
unchanged.

  - EV-2023-054 summary: "Product Owner Ethan Brooks (P-0051) formally …"
    → "Product Owner Diego Alvarez (P-0051) formally …"
  - EV-2023-055 summary: "… Product Owner Ethan Brooks (P-0051) clash …"
    → "… Product Owner Diego Alvarez (P-0051) clash …"

## 2026-05-26 — wave-2 category patches applied (C1–C6)

Applied all 6 wave-2 category patch files to benchmark_v0.0.jsonl. Per-category change counts:
- C1: 15 questions patched (from medium-c1-patches.json)
- C2: 0 questions patched (from medium-c2-patches.json)
- C3: 0 questions patched (from medium-c3-patches.json)
- C4: 0 questions patched (from medium-c4-patches.json)
- C5: 0 questions patched (from medium-c5-patches.json)
- C6: 0 questions patched (from medium-c6-patches.json)

Pre-patch benchmark preserved at benchmark_v0.0.pre-wave2.jsonl. All 73 questions retained (no retirements per user directive); Q-0031, Q-0032, Q-0033, Q-0069 carry best-effort patches and are flagged for wave-3 iteration.

## 2026-05-26 — wave-2 category patches applied (C1–C6)

Applied all 6 wave-2 category patch files to benchmark_v0.0.jsonl. Per-category change counts:
- C1: 15 questions patched (from medium-c1-patches.json)
- C2: 0 questions patched (from medium-c2-patches.json)
- C3: 0 questions patched (from medium-c3-patches.json)
- C4: 0 questions patched (from medium-c4-patches.json)
- C5: 0 questions patched (from medium-c5-patches.json)
- C6: 0 questions patched (from medium-c6-patches.json)

Pre-patch benchmark preserved at benchmark_v0.0.pre-wave2.jsonl. All 73 questions retained (no retirements per user directive); Q-0031, Q-0032, Q-0033, Q-0069 carry best-effort patches and are flagged for wave-3 iteration.

## 2026-05-26 — wave-3 name-propagation (re-applied to correct path)

The wave-3 name-propagation agent edited a misplaced copy outside this dataset instead of `OrgMemBench/datasets/helix/medium/...`. Re-applied the changes here:

- corpus/EV-2023-112/ART-EV-2023-112-002.md — 2 occurrences of "Luis Martinez" corrected to "Luis Ramirez" (typo for P-0027)
- helix_canon/personas.jsonl — P-0005 Rajesh Kumar added (CTO 2020 → COO 2023-05-15; was referenced in 56+ artifacts but missing from registry)

Marco Ruiz / Kevin Patel / Maya Lin left as Scenario C (single-occurrence ambiguous, no confident canonical mapping).

## 2026-05-26 — wave-3 patches applied (C1–C6)

Validation-+-repair pass over wave-2. Each wave-3 patch file was schema-normalized (real benchmark fields kept, audit metadata dropped) before merging. Per-category change counts:
- **C1**: 6 patched, 0 skipped (no benchmark-field updates) — from medium-c1-wave3-patches.json
- **C2**: 15 patched, 0 skipped (no benchmark-field updates) — from medium-c2-wave3-patches.json
- **C3**: 7 patched, 0 skipped (no benchmark-field updates) — from medium-c3-wave3-patches.json
- **C4**: 15 patched, 0 skipped (no benchmark-field updates) — from medium-c4-wave3-patches.json
- **C5**: 15 patched, 0 skipped (no benchmark-field updates) — from medium-c5-wave3-patches.json
- **C6**: 6 patched, 0 skipped (no benchmark-field updates) — from medium-c6-wave3-patches.json

Pre-wave-3 benchmark preserved at benchmark_v0.0.pre-wave3.jsonl. All 73 questions retained.

## 2026-05-27 — wave-3 follow-up: missing-artifact citation fixes

Two questions had `evidence_artefact_ids` pointing at slot_ids that don't exist on disk. The wave-3 C5 agent fixed each question's `ground_truth.testimony_attribution` to point at the real anchor event, but left the `evidence_artefact_ids` field stale.

- **Q-0053** (BDR hiring): `[ART-EV-2023-002-001, -002, -003]` -> `[ART-EV-2023-003-001, -002, -003]` (EV-2023-002 has no -003 on disk; EV-2023-003 is the actual BDR hiring event)
- **Q-0064** (SLA policy 99.9% uptime): `[ART-EV-2023-006-001, -002, -003]` -> `[ART-EV-2023-015-001, -002, -003]` (EV-2023-006 has no -003 on disk and is the wrong topic; EV-2023-015 is the actual SLA policy decision event)

Prior `evidence_artefact_ids` values preserved at `metadata.evidence_pre_2026_05_27_citation_fix` on each row.

## 2026-06-01 — C5 ground-truth restore (wave-3 null-GT regression fixed)

ROOT CAUSE: 10 of 15 C5 (justification_chain) questions had ground_truth_answer
nulled. The wave-3 C5 patches carried `ground_truth_answer_patch: null`, and
apply_medium_wave3_patches.py overwrote the real GT with null. A null answer key
is unscoreable -> every system auto-scored ~0 on those 10, masking C5 as a
"hard category" and deflating the stronger systems most.

FIX: restored ground_truth_answer for Q-0054/55/56/57/58/59/60/62/63/67 from
benchmark_v0.0.jsonl.pre-wave3.jsonl (the wave-3 GT patches were null, so a pure
restore is correct; text + paraphrases keep their wave-3 rewordings). Backup:
benchmark_v0.0.jsonl.pre-c5gt-restore.jsonl. apply script hardened to never let a
null/empty patch overwrite a GT.

RE-JUDGE (no re-ingest, no re-query — stored answers re-scored against fixed GT):
medium means moved gbrain 0.374->0.395, mem0-platform 0.273->0.280,
zep-cloud 0.209->0.210, graphify-oss 0.128->0.133.
Pre-rejudge result snapshots saved at results/<sys>/helix-medium.pre-c5rejudge.json.
The C5 questions are answerable (top systems now score 0.2-0.37); C5 was a data
bug, not a hard category.

## 2026-06-01 — strip EV-2023-058 spurious supersession burst (SoT cleanliness)

relations.jsonl carried 31 bogus "EV-2023-058 supersedes EV-2023-0NN" edges over the
contiguous EV-2023-003..033 range (a generator fan-out burst). EV-2023-058 is a
ticket-triage "Priority Queue" decision that supersedes nothing. Stripped all 31.
No scoring impact (the C4 GTs were already corrected to replacements=[] in wave-2/3,
and relations.jsonl is SoT-only, not retrieved by systems); this makes the SoT
consistent with the GTs and prevents the burst from re-poisoning any future GT
re-projection. The corpus artifact corpus/EV-2023-058/ still carries the mirrored
cross-reference blocks; these remain as benign retrieval distractors (removing them
would require re-running all systems). Backup: relations.jsonl.pre-ev058-strip.

## 2026-06-01 — per-question GT/rubric repair (17 questions)

Verify-then-fix pass (one agent per flagged question, grounded in the pinned corpus; all 17
confirmed broken, 0 false-positives, all patches verified before apply). Fixes:
- C1 Q-0001: re-anchored from the (stripped) EV-2023-058 tooling-decision conflation to the real
  Nia Osei departure chain EV-2023-004 -> EV-2023-105 (15% layoff, 2023-09-15); GT+rubric+evidence.
- C2 Q-0016/20/22/23/24/25/27/28/30: corrected deciders (removed participants/implementers wrongly
  listed as deciders) and removed alternatives absent from the cited artifacts; rubric updated so a
  corpus-faithful answer can earn full credit. Q-0018/19/26: repointed evidence_artefact_ids to the
  correct on-disk event (EV-022/023/073) whose artifacts actually contain the decision.
- C3 Q-0032/35: relaxed rubric sub2 to accept 2024-05-20 (the date in every EV-2024-155 artifact) OR
  the SoT recorded_at 2024-05-21.
- C4 Q-0043: restored the genuine later supersession (EV-2023-128, 2023-12-01 flat-12% commission)
  that the wave-3 audit over-stripped to []; as_of 2023-04-02 < 2023-12-01 so it is in scope.
- C6 Q-0071: reattributed the 2-hour-outage line from Diego Alvarez to its real speaker.
Originals stashed at metadata.pre_gt_repair_2026_06_01. Backup: benchmark_v0.0.jsonl.pre-gt-repair.jsonl.
All 17 re-judged against the corrected GT (stored answers, no re-ingest/re-query).
