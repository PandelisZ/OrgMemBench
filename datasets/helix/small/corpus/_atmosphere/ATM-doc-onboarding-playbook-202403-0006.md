<!-- atmosphere wiki doc_type=policy_doc topic=CustomerOnboarding 2024-03 role=secondary testimony_type=direct author=P-0009 event_id=ATM-EVT-2024-ONBK-001 -->

[WIKI: policy_doc] Customer Onboarding — version 1.0, published 2024-03-14

---

# Helix Customer Onboarding Playbook v1.0

**Owner:** Priya Nair, Head of Customer Success  
**Approved by:** Maya Patel, CEO; Luis Hernandez, COO  
**Effective date:** 2024-03-14  
**Review cycle:** Bi-annual  

> This playbook defines the standard end-to-end process for onboarding new Helix Logistics customers. All Customer Success, Engineering, and Sales teammates are expected to follow this process from contract signature onwards.

---

## 1. Onboarding Stages

### Stage 1 — Discovery (Days 1–5)
**Owner:** Customer Success  
**Activities:**
- Kickoff call with the customer's operations lead and Priya Nair (Head of CS).
- Collect environment specs: API consumers, data volumes, integration endpoints.
- Complete the [Helix Onboarding Intake Form] in Salesforce (required before Stage 2 begins).
- Create a dedicated Slack Connect channel named `#helix-[customer-slug]-onboarding`.

**Exit criteria:** Intake Form submitted; Slack channel confirmed with at least one customer contact.

---

### Stage 2 — Configuration (Days 6–15)
**Owner:** Engineering (Arjun Mehta or Sophia Liu, as assigned)  
**Activities:**
- Provision isolated sandbox environment via the `helix-infra` Terraform module.
- Generate customer-scoped API credentials and deliver securely via 1Password link.
- Configure webhook endpoints per the customer's specification.
- Complete the [API Integration Checklist] in Confluence and assign to customer Jira epic.

**Exit criteria:** Sandbox provisioned; API keys delivered; integration checklist 100% complete.

---

### Stage 3 — Training (Days 16–22)
**Owner:** Customer Success + Product  
**Activities:**
- Deliver a 90-minute Helix Platform Walkthrough (recorded for the customer's knowledge base).
- Share the [Helix API Reference v2] and the [Integration Best Practices Guide].
- Schedule a live Q&A session within 48 hours of the walkthrough.
- Customer nominates a primary technical contact to be granted [Integration Certified] status.

**Exit criteria:** Walkthrough completed; customer technical contact completes the Helix Certification Quiz (≥ 80% pass score required).

---

### Stage 4 — Go-Live (Days 23–30)
**Owner:** Engineering + Customer Success  
**Activities:**
- Migrate customer from sandbox to production environment.
- Confirm live webhook delivery (≥ 99.5% success rate over a 24-hour window).
- Rename Slack channel from `#helix-[slug]-onboarding` to `#helix-[slug]-support`.
- Conduct the [Go-Live Readiness Review] call with customer stakeholders.

**SLA commitment:** Production environment live within 30 calendar days of contract signature.

---

### Stage 5 — Quarterly Business Reviews (Ongoing)
**Owner:** Priya Nair + assigned Account Executive  
**Activities:**
- QBR call in months 3, 6, 9, 12.
- Review usage metrics dashboard (export from Datadog → QBR Deck template).
- Document action items in the customer's Salesforce account record.
- Renewal flag raised to Omar Al-Zahra (VP Sales) if health score drops below 7.0.

---

## 2. Ownership Matrix

| Stage | Primary Owner | Secondary Owner | Escalation |
|-------|---------------|-----------------|------------|
| Discovery | Priya Nair | Assigned AE | Luis Hernandez |
| Configuration | Arjun Mehta / Sophia Liu | DevOps (Miguel Torres backup) | Daniel Kim |
| Training | Priya Nair | Maya Rojas (Product) | Luis Hernandez |
| Go-Live | Sophia Liu | Priya Nair | Daniel Kim |
| QBRs | Priya Nair | Omar Al-Zahra | Maya Patel |

---

## 3. SLA Commitments

| Milestone | Commitment |
|-----------|------------|
| Kickoff call scheduled | Within 2 business days of contract signature |
| Sandbox provisioned | Within 5 business days of kickoff |
| API credentials delivered | Same day as sandbox provisioning |
| Go-Live | Within 30 calendar days of contract signature |
| First QBR | Within 90 days of Go-Live |

---

## 4. Slack Channel Naming Conventions

- **During onboarding:** `#helix-[customer-slug]-onboarding`  
- **Post-Go-Live (support):** `#helix-[customer-slug]-support`  
- **VIP / Enterprise accounts:** prefix with `vip-`, e.g. `#helix-vip-[slug]-support`  
- Customer slug = lowercase company name, hyphens for spaces, max 20 chars.

---

## 5. Changelog

| Date | Author | Change |
|------|--------|--------|
| 2024-03-14 | Priya Nair | v1.0 published post Series A |
| 2024-03-08 | Priya Nair | Draft reviewed by Maya Patel and Luis Hernandez |
| 2024-02-28 | Priya Nair | Initial draft from CS retrospective notes |

---
