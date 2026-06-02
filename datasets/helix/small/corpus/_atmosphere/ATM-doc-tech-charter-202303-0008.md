<!-- atmosphere wiki doc_type=governance_doc topic=TechnicalLeadership 2023-03 role=secondary testimony_type=direct author=P-0008 event_id=ATM-EVT-2023-TECH-001 -->

[WIKI: governance_doc] Technical Decision-Making Charter — version 1.0, published 2023-03-06

---

# Helix Technical Decision-Making Charter v1.0

**Owner:** Daniel Kim, VP of Engineering  
**Approved by:** Maya Patel, CEO; Luis Hernandez, COO  
**Effective date:** 2023-03-06  
**Context:** Issued upon Daniel Kim's appointment as VP of Engineering (2023-02-01) to clarify technical decision authority following the rapid engineering headcount growth in 2022.

> This charter defines the formal technical decision-making authority at Helix Logistics. It establishes clear ownership, escalation paths, and sign-off requirements for architectural and engineering decisions. All Engineering, Product, and Operations teams are expected to operate within this framework from the effective date.

---

## 1. Designated Technical Lead

**Daniel Kim** (VP of Engineering) is hereby designated as the **Official Technical Lead** for Helix Logistics, effective 2023-02-01.

As Technical Lead, Daniel Kim holds:

- Final decision authority over all architecture changes classified as **medium complexity or above** (see Section 3 for the complexity rubric).
- Veto authority over technology choices that conflict with the approved tech stack (Appendix A).
- Sign-off authority on all production infrastructure changes.
- Formal representation of the Engineering function in executive and board-level technical discussions.

No architecture decision of medium complexity or above is considered ratified without Daniel Kim's explicit written approval.

---

## 2. Decision Authority Matrix

| Decision Type | Complexity | Final Authority | Consulted | Informed |
|---------------|------------|-----------------|-----------|----------|
| New service introduction | High | Daniel Kim | Arjun Mehta, Sophia Liu | Maya Patel |
| API contract change (external) | High | Daniel Kim | Arjun Mehta | Maya Patel, Luis Hernandez |
| Data model change (production) | High | Daniel Kim | Arjun Mehta, Sophia Liu | Luis Hernandez |
| Infrastructure scaling | Medium | Daniel Kim | Sophia Liu, DevOps | — |
| Internal refactor | Low | Engineering Manager | — | Daniel Kim |
| Dependency version update (non-breaking) | Low | Lead Engineer | — | Daniel Kim |

Sophia Liu (Engineering Manager) retains autonomous authority over low-complexity decisions and day-to-day team delivery coordination.

---

## 3. Complexity Rubric

| Classification | Criteria |
|----------------|----------|
| **High** | Affects an external-facing API; changes data storage layer; introduces a new runtime dependency; modifies deployment topology; estimated blast radius affects more than one team. |
| **Medium** | Internal service boundary change; non-breaking API evolution; infrastructure configuration change with production impact; changes to shared libraries. |
| **Low** | Single-service internal change; documentation updates; test-only changes; dependency patches (non-breaking). |

---

## 4. Escalation Path

1. **Engineering Manager (Sophia Liu)** — first point of escalation for day-to-day technical disagreements within a team.
2. **VP of Engineering (Daniel Kim)** — escalation for cross-team disputes or decisions above low complexity.
3. **CEO (Maya Patel)** — escalation for decisions with significant commercial or strategic implications.

Escalations must be documented in writing (Slack thread or email) and resolved within 2 business days.

---

## 5. Sign-Off Record

| Name | Title | Signature Date |
|------|-------|----------------|
| Daniel Kim | VP of Engineering | 2023-03-06 |
| Maya Patel | CEO | 2023-03-06 |
| Luis Hernandez | COO | 2023-03-07 |

---

## 6. Changelog

| Date | Author | Change |
|------|--------|--------|
| 2023-03-06 | Daniel Kim | v1.0 published; signed by Maya Patel and Luis Hernandez |
| 2023-02-28 | Daniel Kim | Draft reviewed by Maya Patel |
| 2023-02-20 | Daniel Kim | Initial draft following VP of Engineering appointment |

---
