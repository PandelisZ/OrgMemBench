<!-- atmosphere wiki doc_type=runbook topic=Operations 2020-04 role=noise -->

[WIKI: runbook] Operations — updated 2020-04-21  

---

## status_page  
**Weekly Team Status (Week of 2020-04-21)**  

| Shipped | In Progress | Blocked | Next |
|---------|-------------|---------|------|
| - Deploy v1.2 to staging (Mon) | - Finish API rate‑limit patch | - Await vendor API key from Yara Al‑Hassan | - Release to prod (Fri) |
| - On‑call rotation updated | - Write incident playbook | | - Review incident logs (Tue) |
| - QA regression test run | | | |

---

## runbook  
### Deploy Procedure  
1. **Pull latest code**  
   ```bash
   git checkout master
   git pull origin master
   ```
2. **Run tests**  
   ```bash
   ./run_tests.sh
   ```
   If any fail, abort.
3. **Build Docker image**  
   ```bash
   docker build -t helix-backend:$(git rev-parse --short HEAD) .
   ```
4. **Push to registry**  
   ```bash
   docker push registry.helix.com/helix-backend:$(git rev-parse --short HEAD)
   ```
5. **Deploy to staging**  
   ```bash
   kubectl set image deployment/helix-backend helix-backend=registry.helix.com/helix-backend:$(git rev-parse --short HEAD)
   ```
6. **Verify**  
   - Check pod status: `kubectl get pods`
   - Run smoke test: `./smoke_test.sh`

### On‑call Rotation  
- **Schedule**: 24/7, 4‑person rotation.  
- **Contact**: Slack channel `#ops-oncall`.  
- **Escalation**: If unresolved >30 min → `#ops-senior`.  

### Incident Response  
1. **Detect** – Alert from PagerDuty.  
2. **Triage** – Verify in Slack, ping on‑call.  
3. **Contain** – If service down, scale replicas to 0.  
4. **Root Cause** – Check logs (`kubectl logs`).  
5. **Fix** – Apply hotfix, redeploy.  
6. **Post‑mortem** – Fill template in Confluence, share with team.  

---

## onboarding_doc  
### New Ops Hire Setup  
1. **Account Creation** – HR (Elena Rossi) creates GitHub, Slack, and Ops dashboard accounts.  
2. **Hardware** – Laptop shipped by IT.  
3. **Access** –  
   - GitHub repo: `helix-backend` (read/write).  
   - Kubernetes cluster: `dev` namespace.  
   - PagerDuty: Ops team.  
4. **Training** –  
   - Watch intro videos (Ops 101).  
   - Pair with senior Ops engineer (Trevor Collins).  
5. **First Tasks** –  
   - Review last 3 incidents.  
   - Update `status_page` for next week.  

---

## process_doc  
### Code Review Process  
- **Author**: Trevor Collins (2020-04-21)  
- **Steps**:  
  1. Submit PR on GitHub.  
  2. Assign reviewer (senior dev).  
  3. Review comments must be addressed within 48 h.  
  4. CI must pass (`./run_tests.sh`).  
  5. Merge after approval.  

**Last Updated**: 2020-04-21  
**Changelog**  
- 2020-04-21: Initial draft by Trevor.  
- 2020-04-28: Added CI requirement (Daniel Ortiz).  

---

## okr_page  
**Objective**: Improve Ops reliability.  
| Key Result | Target | Current |
|------------|--------|---------|
| MTTR < 30 min | 30 min | 45 min |
| Deploy frequency | 3 per week | 2 per week |
| Incident post‑mortems | 100% coverage | 80% |

---

## meeting_notes_index  
- **Ops Weekly Sync** – 2020-04-21 – [Link](#)  
- **Incident Review** – 2020-04-14 – [Link](#)  
- **On‑call Rotation Update** – 2020-04-07 – [Link](#)  

---

## how_to / faq  
**Q: How do I reset my Ops dashboard password?**  
A: Use the “Forgot password” link on the dashboard login page.  

**Q: Who do I contact if the API key from Yara Al‑Hassan is delayed?**  
A: Ping Yara on Slack or email her at `yara@vendor.com`.  

**Q: Where are the incident logs stored?**  
A: In the `ops-logs` bucket on S3, accessible via the Ops dashboard.  

---