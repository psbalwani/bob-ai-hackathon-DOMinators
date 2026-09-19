# 🚀 ClinIQ

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | DOMinators |
| **Track** | AI |
| **Team Lead** | Priyansh Balwani - psbalwani@gmail.com |
| **Members** | Arya Kayastha, Nancy Vaghela, Jay Changani |

---

## 🎯 Problem Statement

Major clinical trials run 5,000+ patient visits across 200+ sites, making it impossible for risk managers to manually catch protocol deviations — missed visits, wrong dosing, banned co-medications — before an FDA audit. A single rejected submission delays drug approval by 6–12 months and costs $50–100M, yet today's calendar-driven monitoring gives no real-time visibility into which sites are highest risk.

---

## 💡 Solution

ClinIQ is a Bob-orchestrated multi-agent pipeline that compares patient records against the protocol specification to detect deviations, classifies each by severity under ICH E6 GCP (major/minor/administrative), scores site-level risk from leading indicators, and generates CAPA-ready mitigation reports for a risk manager to review before they're finalized.

---

## ✨ Key Features

- **Protocol Spec Parser:** Extracts visit windows, dosing rules, and banned co-medications into structured constraints.
- **Deviation Detection Agent:** Diffs patient visit records against those constraints in near real time.
- **ICH E6 GCP Severity Classifier:** Classifies every detected deviation as major, minor, or administrative.
- **Site-Level Risk Scoring Engine:** Combines deviation history with leading indicators (enrollment velocity, deviation trend).
- **CAPA-Ready Report Generator:** Produces recommended corrective/preventive actions with a human-in-the-loop review gate before finalization.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, TypeScript |
| **Frameworks** | FastAPI, React |
| **IBM Technologies** | IBM Bob, watsonx.ai |
| **Databases** | PostgreSQL (Neon) |
| **Other** | SQLAlchemy, Vite, Tailwind CSS |

---

## 📁 Repository Structure

```
├── src/                  # All source code
├── docs/                 # Written documentation
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   └── setup-guide.md
├── demo/                 # Demo artifacts
│   ├── screenshots/      # App screenshots
│   └── demo-video-link.txt  # Link to demo video
├── presentation/         # Slide deck
└── submission.yaml       # Structured submission metadata
```

---

## ⚡ How to Run

> **Full details in [`docs/setup-guide.md`](docs/setup-guide.md)**

```bash
# 1. Clone the repo
git clone https://github.com/psbalwani/bob-ai-hackathon-DOMinators.git
cd bob-ai-hackathon-DOMinators

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install frontend dependencies
cd src/frontend && npm install && cd ../..

# 4. Generate the synthetic dataset
python src/data/generate_synthetic_data.py

# 5. Configure environment (optional — app runs without any keys set)
cp src/.env.example src/.env
# Edit src/.env with your WATSONX_API_KEY / DATABASE_URL if desired

# 6. Start the backend gateway
uvicorn src.backend.app.main:app --reload --port 8000

# 7. Start the frontend (separate terminal)
cd src/frontend && npm run dev
```

App is available at **http://localhost:5173** (frontend) and **http://localhost:8000** (API).  
No Docker or local Postgres required — the gateway falls back to an in-memory store if `DATABASE_URL` is not set.

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚠️ Known Limitations

- Built and tested against a **synthetic** patient/protocol dataset rather than a real EDC feed.
- Severity classification relies on rule-based logic mapped to ICH E6(R2)-era deviation categories rather than a fully validated GCP taxonomy.
- Site risk scoring uses a limited set of leading indicators due to hackathon time constraints.
- Docker Compose was deliberately skipped in favour of a hosted Neon connection string; the app runs directly via `pip`/`npm` with no containerisation.

---

## 🏅 What We're Most Proud Of

The multi-agent handoff — deviation detection, severity classification, risk scoring, and CAPA drafting run as distinct Bob-orchestrated agents with a human review checkpoint before anything is finalized, mirroring how a real GCP compliance workflow would need audit-grade traceability.

---
