# P1 — Clinical Trial Risk Monitor & Protocol Deviation Detector

Planning docs for the IBM Bob Hackathon submission (Pharma & Biotech, Problem P1).

| File | Purpose |
|---|---|
| [01_project_planning.md](01_project_planning.md) | Scope, requirements, personas, timeline, success metrics, deliverables |
| [02_architecture.md](02_architecture.md) | System architecture, components, tech stack, data flow, security |
| [03_team_division.md](03_team_division.md) | 4 parallel tracks for the 3 Data/AI + 1 Developer team, integration plan |
| [04_data_schema.md](04_data_schema.md) | Shared data contract: protocol, visit, deviation, risk score, CAPA objects |
| [05_api_contracts.md](05_api_contracts.md) | REST endpoints between the four tracks |
| [06_demo_pitch_script.md](06_demo_pitch_script.md) | Final demo/pitch structure and judging checklist |
| [07_bob_agent_task_priority.md](07_bob_agent_task_priority.md) | Minimal Bob agent plan — Claude Code builds the bulk, Bob handles 2 targeted repo-aware tasks |

**Suggested reading order for a new team member:** 01 → 02 → 03, then keep 04/05 open as a reference while building, and 06 close to demo day.

**Two documents are frozen contracts — don't change them solo:** `04_data_schema.md` and `05_api_contracts.md`. If your track needs a change, flag it to the team first.
