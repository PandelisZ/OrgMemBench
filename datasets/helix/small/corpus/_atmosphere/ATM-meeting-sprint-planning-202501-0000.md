<!-- atmosphere meeting type=sprint planning scope=Engineering 2025-01 role=noise -->

[MEETING: sprint planning] Engineering — 2025-01-07  

**Attendees**: Sienna Patel, Arjun Mehta, Sophia Liu, Daniel Kim  

**Agenda**  
1. Review of backlog items for Sprint 3 (Jan 8–Jan 22)  
2. Capacity planning and velocity check  
3. Carry‑over from Sprint 2  
4. Definition of Done (DoD) reminders  
5. Sprint goal alignment with Q1 OKRs  

---

### 1. Backlog Review & Ticket Commitment  
| Ticket ID | Title | Story Points | Owner | Sprint 3 Status |
|-----------|-------|--------------|-------|-----------------|
| FL-1123 | Refactor shipment‑status API | 5 | Sienna | **Committed** |
| FL-1150 | Add bulk‑import UI for carriers | 8 | Arjun | **Committed** |
| FL-1178 | Implement rate‑limit middleware | 3 | Sophia | **Committed** |
| FL-1190 | Update docs for new auth flow | 2 | Sophia | **Committed** |
| FL-1205 | Create unit tests for carrier sync | 5 | Sienna | **Committed** |
| FL-1212 | Optimize DB indexes for tracking | 4 | Arjun | **Committed** |

*All tickets were groomed in the previous backlog refinement. No new tickets were added to Sprint 3.*

### 2. Capacity & Velocity  
- **Team Velocity (Sprint 2)**: 28 story points  
- **Available Capacity (Sprint 3)**: 30 story points (2 days of buffer)  
- **Committed Story Points**: 27  
- **Buffer**: 3 points reserved for unforeseen bugs or support tickets.  

**Notes**:  
- Sophia will take on the documentation ticket to free up Sienna for UI work.  
- Arjun will pair with Sienna on the bulk‑import UI to accelerate delivery.  

### 3. Carry‑over from Sprint 2  
| Ticket ID | Title | Reason for Carry‑over | Owner |
|-----------|-------|-----------------------|-------|
| FL-1109 | Fix race condition in shipment queue | Partial regression | Sienna |
| FL-1120 | Update carrier API spec | Awaiting external API changes | Arjun |

*Both tickets are now in the “Ready” column of the board and will be re‑estimated if needed.*

### 4. Definition of Done (DoD) Reminders  
- All code must pass CI (unit, integration, and linting).  
- Unit test coverage ≥ 80% for new modules.  
- Documentation updated in Confluence.  
- Peer review completed by at least one other engineer.  

### 5. Sprint Goal & OKR Alignment  
- **Sprint Goal**: Deliver a fully functional bulk‑import feature with API support and updated authentication flow, ensuring 99.9% uptime for the shipment‑status API.  
- **OKR Alignment**: Supports Q1 OKR “Improve carrier onboarding speed by 30%” (Maya Rojas).  

---

**Action Items**  
1. **Sienna** – Finish API refactor and start bulk‑import UI.  
2. **Arjun** – Lead bulk‑import UI implementation and pair with Sienna.  
3. **Sophia** – Complete documentation and rate‑limit middleware.  
4. **Daniel** – Monitor sprint board, adjust capacity if blockers arise.  

**Next Meeting**: Sprint Planning for Sprint 4 (Jan 25–Feb 8).