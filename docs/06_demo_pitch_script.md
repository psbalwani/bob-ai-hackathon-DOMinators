# Demo & Pitch Script Outline

Use this during Hour 42–46 (Polish & Demo Prep, see `01_project_planning.md`) to structure the final presentation. Keep the whole thing to **5–7 minutes**: ~90 seconds pitch, ~3 minutes live demo, ~1–2 minutes impact/close.

---

## 1. Hook (15–20 seconds)
Open with the cost of the problem, not the tech:
- "A single rejected clinical trial submission costs $50–100M and delays approval by up to a year. The cause is almost always a protocol deviation nobody caught in time."

## 2. Problem (20–30 seconds)
- 5,000+ visits, 200+ sites, deviations found only at audit time.
- Risk managers have no real-time, explainable view of which sites are actually at risk.

## 3. Solution (20–30 seconds)
- One line: "We built an AI copilot that detects deviations the moment they happen, grades them against ICH GCP, scores every site's risk with a transparent breakdown, and drafts the CAPA report automatically."
- Name-drop IBM Bob explicitly here: how it was used to build the solution (be specific — e.g., "Bob scaffolded our FastAPI integration layer and caught two schema bugs during merge").

## 4. Live Demo (2.5–3 minutes)
Recommended flow — walk the same path a real Risk Manager would:
1. **Trial Overview:** show the ranked site list; point at the top (highest-risk) site.
2. **Site Drill-down:** open that site, show the risk score breakdown (which indicators are driving it) and the trend.
3. **Deviation Detail:** click into one deviation — show the severity classification and the exact protocol clause it cites.
4. **CAPA Report:** generate/open the CAPA report for that site — show root cause, corrective action, preventive action, and the citations back to the evidence.
5. (If time) Show the export/download of the CAPA report.

**Fallback:** have a pre-recorded 60-second screen capture ready in case live demo/network/LLM calls fail.

## 5. Why It's Trustworthy, Not Just a Chatbot (20–30 seconds)
- Every output is explainable and cited — severity has a rationale, risk score has a breakdown, CAPA has evidence links.
- This matters specifically because the audience for this product (QA/Regulatory) will reject anything they can't audit.

## 6. Impact / Close (20–30 seconds)
- Reconnect to the numbers from the opening hook: minutes instead of weeks to find root cause; real-time instead of audit-time detection.
- One sentence on what's next if this were productionized (real EDC integration, 21 CFR Part 11 workflow).

---

## Judging-Criteria Checklist (confirm before presenting)

- [ ] Clearly demonstrates meaningful use of IBM Bob (required — some hackathon rules disqualify submissions that don't show this)
- [ ] Addresses all 4 challenge requirements from the problem statement (detect, classify, score, CAPA)
- [ ] Live or recorded demo works end-to-end without manual data patching
- [ ] Explainability is visibly shown, not just claimed
- [ ] Pitch opens with the business problem, not the tech stack
- [ ] Team can answer "what's synthetic vs. real" honestly if asked
