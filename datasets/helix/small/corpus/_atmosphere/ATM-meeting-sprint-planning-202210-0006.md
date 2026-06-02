<!-- atmosphere meeting type=sprint planning scope=Engineering 2022-10 role=noise -->

[MEETING: sprint planning] Engineering — 2022-10-01  

**Attendees**: Miguel Torres, Leila Hassan, Victor Chen, Omar Farah, Daniel O'Connor, Mei Lin, Kenji Sato, Nadia Rahman  

**Duration**: 90 min  

---  

### 1. Sprint Goals  
- Deliver API v2.1 for freight cost calculation.  
- Fix critical mobile crash on iOS 15.  
- Improve test coverage for data ingestion pipeline.  

### 2. Capacity  
| Engineer | Available Story Points | Notes |
|----------|------------------------|-------|
| Miguel | 12 | DevOps support for CI/CD, 2 points for Docker image update |
| Leila | 10 | Backend refactor, 3 points for new auth module |
| Victor | 8 | Mobile bug fix, 2 points for UI tweak |
| Omar | 9 | QA automation, 1 point for regression suite |
| Daniel | 6 | Security audit, 2 points for vulnerability patch |
| Mei | 7 | Data pipeline, 3 points for schema migration |
| Kenji | 5 | Documentation, 1 point for API spec update |

**Total Capacity**: 62 SP

### 3. Backlog Review & Ticket Assignment  

| Ticket ID | Title | Owner | Story Points | Sprint Status |
|-----------|-------|-------|--------------|---------------|
| BE-1123 | Refactor cost calculation logic | Leila | 5 | Committed |
| API-204 | Add rate limit headers | Miguel | 3 | Committed |
| M-301 | Crash on iOS 15 launch | Victor | 4 | Committed |
| QA-512 | Automate regression tests | Omar | 3 | Committed |
| SEC-78 | Patch CVE-2022-3456 | Daniel | 2 | Committed |
| DP-88 | Migrate to new DB schema | Mei | 4 | Committed |
| DOC-27 | Update API docs for v2.1 | Kenji | 1 | Committed |

**Carry‑over**:  
- BE-1150 (Add webhook support) – 3 SP, moved to next sprint due to dependencies on external API.  
- M-302 (UI polish for Android) – 2 SP, pending design approval.

### 4. Blockers & Dependencies  

- **Leila**: Waiting on API key provisioning from Ops; Miguel to confirm by EOD.  
- **Victor**: Requires updated test harness from QA; Omar to share script.  
- **Mei**: Schema migration needs approval from DBA; Daniel to coordinate.  

### 5. Sprint Planning Decisions  

- **CI/CD**: Miguel will push Docker image update to staging; will run smoke tests.  
- **Security**: Daniel will run static analysis on all new code before merge.  
- **Documentation**: Kenji will sync docs with API team; will use Confluence template.  

### 6. Next Steps  

- All owners to update JIRA tickets with acceptance criteria by 2022-10-03.  
- Nadia to review feature list and confirm priority alignment.  
- Miguel to schedule a quick sync with Ops for API key provisioning.  

---  

**Action Items**  

| Owner | Item | Due |
|-------|------|-----|
| Miguel | Confirm API key provisioning | 2022-10-02 |
| Leila | Update cost calculation logic | 2022-10-04 |
| Victor | Fix iOS crash | 2022-10-05 |
| Omar | Share regression script | 2022-10-02 |
| Daniel | Coordinate DB schema migration | 2022-10-03 |
| Mei | Draft migration plan | 2022-10-04 |
| Kenji | Sync docs with API team | 2022-10-03 |

---  

**Next Sprint Planning**: 2022-10-15 (same format).