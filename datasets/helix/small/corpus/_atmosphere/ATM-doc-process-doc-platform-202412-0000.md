<!-- atmosphere wiki doc_type=process_doc topic=Platform 2024-12 role=noise -->

[WIKI: process_doc] Platform — updated 2024-12-20  

---

## Process: Platform Release Cadence  

**Owner:** Sophia Liu (Engineering Manager)  
**Last updated:** 2024-12-20  

### Overview  
The Platform team follows a bi‑weekly release cadence to ship new features, bug fixes, and infrastructure updates. Releases are coordinated with Product, Ops, and Customer Success to ensure minimal disruption and clear communication.

### Cadence Flow  

| Phase | Duration | Owner | Key Activities |
|-------|----------|-------|----------------|
| **Planning** | Mon‑Tue | Product & Engineering | Feature prioritization, sprint goal definition, backlog grooming |
| **Development** | Wed‑Fri | Engineers | Code implementation, unit tests, CI build |
| **Code Review** | Mon‑Tue (next sprint) | All Engineers | Peer review, merge to `develop` |
| **Staging** | Wed | DevOps | Deploy to staging, run smoke tests |
| **QA** | Thu | QA & Customer Support | Manual regression, UAT |
| **Release Prep** | Fri | Ops | Build Docker images, update Helm charts |
| **Production Release** | Mon (next sprint) | DevOps | Canary deploy, monitor metrics |
| **Post‑Release** | Tue‑Wed | All | Incident triage, post‑mortem, documentation |

### Release Checklist  

1. **Feature Flag** – Ensure all new features are behind a flag.  
2. **Version Tag** – Tag commit with `vX.Y.Z`.  
3. **Docker Image** – Build and push to registry.  
4. **Helm Chart** – Update `appVersion` and `image.tag`.  
5. **Canary Rollout** – 5% traffic, monitor latency & error rate.  
6. **Full Rollout** – 100% traffic if metrics are healthy.  
7. **Rollback Plan** – Pre‑defined rollback steps in case of failure.  

### Incident Response (Runbook)  

1. **Detection** – Alert from Datadog or PagerDuty.  
2. **Triage** – On‑call engineer acknowledges within 2 min.  
3. **Containment** – If critical, rollback to previous release.  
4. **Investigation** – Gather logs, run `kubectl describe pod`.  
5. **Resolution** – Fix code or config, deploy patch.  
6. **Post‑mortem** – Document root cause, update runbook.  

### Onboarding Checklist  

| Step | Owner | Tool | Notes |
|------|-------|------|-------|
| 1. Account Setup | Elena Rossi | Okta | Add to `platform-dev` group |
| 2. Repo Access | Sophia Liu | GitHub | Grant `write` to `platform` repo |
| 3. CI/CD Overview | Omar Khaled | Confluence | Walkthrough of GitHub Actions |
| 4. Infrastructure Tour | Omar Khaled | Terraform | Review `infra/` modules |
| 5. Code Review Guidelines | Sophia Liu | Confluence | Link to PR template |
| 6. On‑call Rotation | Priya Nair | PagerDuty | Add to `platform-oncall` schedule |
| 7. First Task | Sophia Liu | Jira | Create a small bug fix ticket |

### Changelog  

| Date | Author | Change |
|------|--------|--------|
| 2024-12-20 | Sophia Liu | Added detailed release checklist and incident runbook |
| 2024-10-05 | Sophia Liu | Updated cadence to bi‑weekly, added feature flag requirement |
| 2024-06-12 | Sophia Liu | Initial draft of release process |

---

## status_page  

**Platform Team Status – Week of 2024-12-18**  

| Shipped | In Progress | Blocked | Next |
|---------|-------------|---------|------|
| `v2.3.1` – API rate‑limit fix | `Feature X` – refactor auth module | `Database schema migration` – waiting on DB team | `Deploy `v2.4.0` to prod` |

---

## meeting_notes_index  

- [Platform Sync – 2024-12-18](https://wiki.helixlogistics.com/meetings/platform-sync-2024-12-18)  
- [Sprint Planning – 2024-12-12](https://wiki.helixlogistics.com/meetings/sprint-planning-2024-12-12)  
- [Ops Review – 2024-12-05](https://wiki.helixlogistics.com/meetings/ops-review-2024-12-05)  

---

## how_to / faq  

**Q: How do I roll back a production release?**  
A: Use the rollback command in the release script: `helm rollback platform 1`. Verify the previous version is running before removing the rollback flag.

**Q: Where are the environment variables stored?**  
A: In the `secrets/` directory of the repo, encrypted with `sops`. Access requires `platform-secrets` group permission.

**Q: Who approves a new feature for release?**  
A: The Product Owner (Maya Rojas) signs off on the sprint goal; the Engineering Manager (Sophia Liu) approves the merge to `develop`.

**Q: How do I add a new monitoring alert?**  
A: Create a new alert rule in Datadog, then add the rule to the `platform-alerts.yaml` file and merge via PR.

---