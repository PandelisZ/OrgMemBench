<!-- atmosphere wiki doc_type=status_page topic=Release process 2020-02 role=noise -->

[WIKI: status_page] Release process — updated 2020-02-01  

## status_page  
**Shipped**  
- 2020-01-15: Version 0.1.0 deployed to staging (Trevor Collins).  
- 2020-01-20: Version 0.1.1 hotfix for DB migration bug (Trevor Collins).  

**In Progress**  
- 0.2.0 feature “Batch Tracking API” – code merged, awaiting QA (Maya Patel).  
- 0.2.0 UI refresh for mobile app – Victor Chen working on design (Victor Chen).  

**Blocked**  
- 0.2.0 Batch Tracking API: waiting on external vendor API keys (Yara Al‑Hassan).  
- 0.2.0 UI refresh: legal review pending (Fatima Al‑Mansouri).  

**Next**  
- Complete QA for 0.2.0.  
- Deploy 0.2.0 to production by end of month.  

## runbook  
**Deploy**  
1. Pull latest `main` branch.  
2. Run `./scripts/build.sh`.  
3. Push Docker image to registry.  
4. Update Kubernetes manifests.  
5. Run `kubectl rollout status deployment/helix-backend`.  

**On‑call**  
- Primary on‑call: Trevor Collins (Backend).  
- Secondary: Victor Chen (Mobile).  
- On‑call rotation: 1 week each.  

**Incident Response**  
1. Detect via PagerDuty alert.  
2. Acknowledge and triage.  
3. If service degraded, rollback to last stable image.  
4. Post‑mortem: document in `incident_reports/`.  

## onboarding_doc  
1. **HR**: Elena Rossi sends offer, NDA, and benefits info.  
2. **IT**: Aisha Khan sets up laptop, VPN, and Slack.  
3. **Engineering**: Trevor Collins gives repo access, explains Git workflow.  
4. **Security**: Daniel O'Connor reviews security policies.  
5. **Legal**: Fatima Al‑Mansouri provides compliance checklist.  

## process_doc – Release Process  
**Last updated:** 2020-02-01 (Luis Hernandez)  

1. **Feature Freeze** – 2 weeks before release.  
2. **Code Review** – PR must pass 2 approvals (Trevor + Victor).  
3. **Automated Tests** – CI must succeed.  
4. **Staging Deployment** – Manual deploy to staging.  
5. **QA Sign‑off** – QA team signs off.  
6. **Production Deployment** – Scheduled at 02:00 UTC.  

**Changelog**  
- 2020-02-01: Added QA sign‑off step.  
- 2020-01-10: Introduced feature freeze rule.  

## okr_page  
**Objective:** Deliver stable releases on schedule.  
- KR1: 90% of releases meet deadline (Progress: 80%).  
- KR2: Zero critical bugs in production (Progress: 100%).  

**Objective:** Improve deployment automation.  
- KR1: CI pipeline time < 10 min (Progress: 60%).  
- KR2: Deploy scripts idempotent (Progress: 40%).  

## meeting_notes_index  
- [2020-01-28] Release Planning – notes (link)  
- [2020-01-15] Sprint Retrospective – notes (link)  

## how_to / faq  
**Q:** How do I trigger a rollback?  
**A:** Run `kubectl rollout undo deployment/helix-backend`.  

**Q:** Who approves a PR?  
**A:** Trevor Collins and Victor Chen.  

**Q:** Where are the release notes stored?  
**A:** In `docs/releases/` directory, one file per version.  

---