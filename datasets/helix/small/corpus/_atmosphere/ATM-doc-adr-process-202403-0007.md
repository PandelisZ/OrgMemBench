<!-- atmosphere wiki doc_type=policy_doc topic=ArchitectureDecisionRecords 2024-03 role=secondary testimony_type=direct author=P-0008 event_id=ATM-EVT-2024-ADR-001 -->

[WIKI: policy_doc] Architecture Decision Records — version 1.0, published 2024-03-21

---

# Architecture Decision Records Process Charter v1.0

**Owner:** Daniel Kim, VP of Engineering  
**Approved by:** Maya Patel, CEO  
**Effective date:** 2024-03-21  
**Trigger:** Formalized following the Q3 2023 outage post-mortem, which identified undocumented architectural assumptions as a root-cause contributor.

> This charter establishes the mandatory process for recording, reviewing, and archiving Architecture Decision Records (ADRs) at Helix Logistics. All decisions meeting the threshold criteria below must follow this process.

---

## 1. What Requires an ADR

An ADR is required for any change that:

- Introduces or removes a service dependency (internal or external).
- Changes the data storage layer for a production system.
- Modifies an API contract that has external consumers.
- Introduces a new programming language or framework to the production stack.
- Alters the deployment topology (regions, cloud provider, orchestration layer).
- Is assessed by the author as having an estimated blast radius of "high" or above.

Minor bug fixes, dependency version patches (non-breaking), and purely internal refactors below "medium" blast radius do not require an ADR.

---

## 2. ADR Template

Every ADR must use the canonical template stored at `docs/adr/TEMPLATE.md` in the `helix-platform` repository. Required sections:

1. **Title** — Short imperative phrase (e.g., "Adopt PostgreSQL read replicas for reporting queries").
2. **Status** — One of: `Proposed`, `Accepted`, `Superseded`, `Deprecated`.
3. **Context** — What forces are at play? What problem are we solving?
4. **Decision** — The change we are making.
5. **Consequences** — What becomes easier or harder as a result?
6. **Alternatives Considered** — At least two alternatives with a brief rationale for rejection.
7. **Decision Date** — ISO-8601 date the ADR was accepted.
8. **Decision Makers** — Names of all reviewers who voted.

---

## 3. Review Board and Voting Quorum

The ADR Review Board consists of:

| Member | Role | Voting Weight |
|--------|------|---------------|
| Daniel Kim | VP of Engineering (Chair) | 1 vote |
| Arjun Mehta | Principal Engineer | 1 vote |
| Sophia Liu | Engineering Manager | 1 vote |
| Miguel Torres | Senior DevOps Engineer | 1 vote (infra-relevant ADRs only) |

**Quorum:** A minimum of 3 Review Board members must participate. For infra-relevant ADRs, all 4 members must be present.

**Acceptance threshold:** Simple majority (≥ 2 of 3 voting members, or ≥ 3 of 4 for infra-relevant ADRs).

**Chair sign-off:** Daniel Kim (VP of Engineering) must provide explicit written sign-off on all accepted ADRs before they are merged to the `docs/adr/` directory. An ADR without Daniel Kim's sign-off is not considered accepted regardless of the board vote.

---

## 4. Process Steps

1. **Author drafts ADR** using the canonical template and opens a PR against `helix-platform/docs/adr/`.
2. **Author posts the PR link** in `#arch-decisions` Slack channel, tagging all Review Board members.
3. **Review window:** 3 business days for standard ADRs; 1 business day for urgent (P0/P1 incident-driven) ADRs.
4. **Board discussion** in the PR comments (Slack threads may supplement but do not replace PR comments as the record of decision).
5. **Vote recorded** by each board member as a PR review approval (`APPROVE`) or rejection (`REQUEST_CHANGES`) with written rationale.
6. **Chair sign-off:** Daniel Kim adds a final approval comment and merges the PR.
7. **ADR numbered** sequentially: `ADR-YYYY-NNN` (e.g., `ADR-2024-001`).
8. **Confluence mirroring:** Kenji Sato (Technical Writer) mirrors the accepted ADR to the `Architecture` Confluence space within 2 business days of merge.

---

## 5. Archival and Supersession

- Accepted ADRs are immutable. To change a decision, a new ADR must be filed with status `Proposed`, citing the ADR being superseded.
- When a new ADR is accepted that supersedes an older one, the older ADR's status field is updated to `Superseded: ADR-YYYY-NNN` (the successor ADR number).
- ADRs are never deleted from `docs/adr/`. The directory is the authoritative record.
- Annual review: Daniel Kim conducts an annual review of all `Accepted` ADRs in Q1 to flag any that may need revisiting.

---

## 6. Changelog

| Date | Author | Change |
|------|--------|--------|
| 2024-03-21 | Daniel Kim | v1.0 published; approved by Maya Patel |
| 2024-03-15 | Daniel Kim | Draft circulated to Review Board for comment |
| 2024-03-07 | Daniel Kim | Initial draft following Q3 2023 post-mortem action item #4 |

---
