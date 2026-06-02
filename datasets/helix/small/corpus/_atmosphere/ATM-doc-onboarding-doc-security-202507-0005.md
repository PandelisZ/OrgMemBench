<!-- atmosphere wiki doc_type=onboarding_doc topic=Security 2025-07 role=noise -->

[WIKI: onboarding_doc] Security — updated 2025-07-18  

## 1. Overview  
Welcome to the Security Team at Helix Logistics. This onboarding document provides the essential information and resources you need to get started, including access setup, key tools, and team processes.  

---

## 2. Quick Start Checklist  

| Step | Action | Owner | Notes |
|------|--------|-------|-------|
| 1 | Receive company email & Slack invite | HR | Check spam folder |
| 2 | Set up MFA on all accounts | IT | Use Authy or Google Authenticator |
| 3 | Join #security channel on Slack | Kenji Sato | Ask for channel access |
| 4 | Review Security Handbook | Daniel Kim | Link in Confluence |
| 5 | Complete Security Awareness Training | HR | Deadline: 5 days |
| 6 | Meet with Security Lead | Maya Patel | Intro call scheduled |
| 7 | Access internal tools (GitHub, Jira, Confluence) | IT | Request via ServiceNow ticket |
| 8 | Clone repo `security-ops` | Kenji Sato | Repo URL in Confluence |
| 9 | Run `setup.sh` to install dev environment | Kenji Sato | Requires Docker & Node 18 |
| 10 | Attend first sprint planning | Sophia Liu | 10 AM PT, 2‑hour slot |

---

## 3. Key Resources  

- **Confluence Space**: `Security` – contains policies, runbooks, and SOPs.  
- **GitHub Organization**: `helix-security` – all code repos.  
- **Slack**: `#security`, `#security-oncall`.  
- **ServiceNow**: Incident & change management.  
- **Auth0 Dashboard**: Manage user roles.  

---

## 4. Team Structure  

| Role | Name | Primary Responsibility |
|------|------|------------------------|
| Security Lead | Maya Patel | Strategy & compliance |
| Engineering Manager | Sophia Liu | Team delivery |
| VP of Engineering | Daniel Kim | Cross‑team coordination |
| QA Lead | Daniel Ortiz | Security testing |
| Customer Success Associate | Priyanka Desai | Incident triage |
| Customer Support Specialist | Sofia Martinez | Support escalation |
| COO | Luis Hernandez | Operational oversight |
| VP of Sales | Omar Al‑Zahra | Security requirements for sales |

---

## 5. Core Processes  

### 5.1 Code Review  
- **Tool**: GitHub PRs + Confluence checklist.  
- **Checklist**:  
  1. Security impact assessment.  
  2. OWASP Top 10 review.  
  3. Dependency audit.  
  4. Automated test coverage ≥ 90%.  
- **Lead Reviewer**: Sophia Liu.  
- **Timeline**: 2 days max.  

### 5.2 Sprint Cadence  
- **Length**: 2 weeks.  
- **Events**:  
  - Sprint Planning (Mon 10 AM PT).  
  - Daily Standup (Mon‑Fri 9 AM PT).  
  - Sprint Review (Fri 4 PM PT).  
  - Retrospective (Fri 5 PM PT).  

### 5.3 Release Process  
1. **Feature Freeze** – 3 days before release.  
2. **Security Scan** – Snyk + custom script.  
3. **Staging Deployment** – GitHub Actions.  
4. **Production Cut‑over** – 2‑hour window, coordinated with Ops.  
5. **Post‑Release Review** – 24‑hour monitoring.  

---

## 6. Incident Response Runbook  

1. **Detection** – Alerts from Datadog, SIEM.  
2. **Triage** – #security-oncall, assign to triage owner.  
3. **Containment** – Isolate affected services.  
4. **Eradication** – Patch or rollback.  
5. **Recovery** – Restore from backup, verify integrity.  
6. **Post‑mortem** – Document in Confluence, update runbook.  

---

## 7. On‑Call Rotation  

- **Schedule**: 2‑week rotation, 24/7 coverage.  
- **Tool**: PagerDuty.  
- **Escalation Path**:  
  1. On‑call engineer → Security Lead (Maya Patel).  
  2. Security Lead → VP of Engineering (Daniel Kim).  

---

## 8. Documentation Standards  

- **Format**: Markdown in GitHub, Confluence for policy docs.  
- **Versioning**: Semantic versioning for runbooks.  
- **Review Cycle**: Quarterly review by Security Lead.  

---

## 9. FAQ  

| Question | Answer |
|----------|--------|
| How do I request a new API key? | Submit a ServiceNow ticket, tag `security`. |
| Who approves new third‑party integrations? | Maya Patel (Security Lead). |
| Where do I find the latest vulnerability list? | Confluence page `Vulnerability Tracker`. |
| What is the policy on personal devices? | Must be enrolled in MDM, see `BYOD Policy`. |

---

## 10. Meeting Notes Index  

- **2025‑07‑15**: Sprint Planning – Security Team (link)  
- **2025‑07‑10**: Incident Review – Data Breach (link)  
- **2025‑07‑02**: Quarterly Security Review (link)  

---

## 11. Changelog  

| Date | Change | Author |
|------|--------|--------|
| 2025‑07‑18 | Added on‑call rotation details | Kenji Sato |
| 2025‑07‑12 | Updated code review checklist | Sophia Liu |
| 2025‑06‑30 | Re‑structured release process | Daniel Kim |
| 2025‑05‑20 | Initial draft | Maya Patel |

---