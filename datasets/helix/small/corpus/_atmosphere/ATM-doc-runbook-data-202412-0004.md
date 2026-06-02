<!-- atmosphere wiki doc_type=runbook topic=Data 2024-12 role=noise -->

[WIKI: runbook] Data — updated 2024-12-25  

---

## status_page  
**Week of 2024-12-22**

| Shipped | In Progress | Blocked | Next |
|---------|-------------|---------|------|
| • Data ingestion pipeline v2.3 deployed to prod (Mon) | • Schema migration for `shipment_status` (Tue) | • API rate‑limit issue with carrier API (pending vendor fix) | • Rollout of new data quality dashboard (Wed) |

**Notes**  
- Rate‑limit issue resolved after carrier sent new credentials.  
- QA flagged a regression in `delivery_time` calculation; will be fixed in next sprint.

---

## runbook  

### 1. Deploying a Data Service  
1. **Pull latest code**  
   ```bash
   git checkout main
   git pull origin main
   ```
2. **Run tests**  
   ```bash
   make test
   ```
3. **Build Docker image**  
   ```bash
   docker build -t helix-data:${TAG} .
   ```
4. **Push to registry**  
   ```bash
   docker push registry.helix.com/helix-data:${TAG}
   ```
5. **Deploy to staging** (via Helm)  
   ```bash
   helm upgrade --install helix-data ./helm/helix-data --namespace data --set image.tag=${TAG}
   ```
6. **Smoke test**  
   - Run `curl http://helix-data.staging.helix.com/healthz`.  
   - Verify logs in Grafana for no errors.
7. **Promote to prod**  
   - Merge PR to `main`.  
   - Tag release (`git tag vX.Y.Z`).  
   - Run same Helm command with `--namespace prod`.

### 2. On‑call Rotation  
- **Schedule**: 24/7 rotation, 2‑week cycles.  
- **Tool**: PagerDuty.  
- **Escalation**:  
  1. Data Engineer (first 15 min)  
  2. VP of Engineering (next 30 min)  
  3. COO (if unresolved > 1 h)

### 3. Incident Response  
1. **Identify** – PagerDuty alert triggers.  
2. **Triage** – Check Grafana dashboards, logs.  
3. **Contain** – If data pipeline failing, pause ingestion via `helm upgrade --set enabled=false`.  
4. **Root Cause** – Use `kubectl logs` + `kubectl describe pod`.  
5. **Fix** – Commit patch, run tests, deploy.  
6. **Post‑mortem** – Create Jira ticket, add to runbook.

---

## onboarding_doc  

### New Data Engineer Onboarding (Week 1)

| Day | Activity | Owner |
|-----|----------|-------|
| Mon | Set up workstation (VS Code, Docker, kubectl). | HR |
| Tue | Join Slack #data, read README.md in `data-service`. | Maya Rojas |
| Wed | Pair with Sienna Patel on data ingestion task. | Sienna |
| Thu | Attend “Data Architecture” walkthrough. | Daniel Kim |
| Fri | Deploy a test feature to staging. | Daniel Ortiz |

**Resources**  
- GitHub repo: `helix-data`  
- Helm charts: `helm/helix-data`  
- Documentation: Confluence “Data Pipeline Overview”

---

## process_doc  

### Code Review Process  
- **Pull Request**: Must pass CI (`make test`).  
- **Reviewers**: 2 senior engineers (e.g., Daniel Kim, Sienna Patel).  
- **Checklist**:  
  1. Tests added/updated.  
  2. Documentation updated.  
  3. Performance impact assessed.  
- **Merge**: After approvals, merge to `main` and trigger automated deployment.

### Sprint Cadence  
- **Length**: 2 weeks.  
- **Planning**: Monday 10 AM (VP of Product).  
- **Daily Standup**: 9 AM, 15 min.  
- **Demo**: Friday 4 PM.  

### Release Process  
1. **Feature Freeze**: 3 days before release.  
2. **Smoke Tests**: Run on staging.  
3. **Deploy**: Helm upgrade to prod.  
4. **Rollback Plan**: Keep previous image tag.

**Last Updated**: 2024-12-25  
**Changelog**  
- 2024-12-25: Added rollback plan to release process.  
- 2024-10-01: Updated code review checklist to include performance assessment.  

---

## okr_page  

| Objective | Key Result | Progress |
|-----------|------------|----------|
| Improve data pipeline reliability | 1. Reduce downtime to < 5 min/month | 80% |
| Enhance data quality | 1. Achieve 99.9% data accuracy | 70% |
| Accelerate feature delivery | 1. Deploy 3 new features per quarter | 60% |

*Notes*: QA Lead Daniel Ortiz will track accuracy metrics via automated tests.

---

## meeting_notes_index  

- **Data Ops Sync – 2024-12-20**: <https://wiki.helix.com/meetings/data-ops-2024-12-20>  
- **Sprint Planning – 2024-12-17**: <https://wiki.helix.com/meetings/sprint-planning-2024-12-17>  
- **Incident Review – 2024-12-12**: <https://wiki.helix.com/meetings/incident-review-2024-12-12>  

---

## how_to / faq  

**Q: How do I access the production database?**  
A: Use the `db-ssh` bastion. Run `ssh -i ~/.ssh/helix_prod.pem db-ssh@bastion.helix.com` and then `psql -h prod-db.helix.com -U helix_user`.

**Q: Where are the data quality metrics stored?**  
A: In the `metrics` namespace, table `data_quality`. Query via `SELECT * FROM metrics.data_quality;`.

**Q: Who approves a new data source integration?**  
A: VP of Product (Maya Rojas) after review by Data Engineering Lead (Daniel Kim).

**Q: What is the backup schedule for data services?**  
A: Daily snapshots at 02:00 UTC, retained for 30 days. Managed by Kubernetes CronJob `data-backup`.

---