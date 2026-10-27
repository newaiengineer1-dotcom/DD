# ☀️ HelioAssure — AI Engineering and Due Diligence Platform for Solar PV + BESS

A **hybrid, hierarchical, evidence-centric, tool-driven multi-agent platform** (CrewAI + Groq + Streamlit) for solar PV + BESS engineering review and lender due diligence.
AI agents interpret evidence; **deterministic tools calculate, locate and draw**; independent QA challenges everything; **humans approve** before anything is issued.

## What you get
- **Master Orchestrator** → 8 **Workstream Leads** → **30 core discipline agents** + 10 **optional specialists** (activated by project flags) → 6 **independent QA agents** (`config/agents.yaml`)
- **Deterministic tool agents:** WGS84↔UTM geometry, PV tracker layout, BESS compound layout, MV/DC cable routing, string/transformer/cable checks, P-values, DSCR/IRR/LCOE (`helioassure/tools`)
- **RAG/evidence layer:** PDF/DOCX/XLSX/CSV/TXT ingestion, BM25 retrieval with `[file | page]` citations, missing-evidence → OIR, negative-evidence scan
- **Independent QA:** citation + quote verification, calculation re-execution, coordinate consistency, cross-discipline reconciliation, cross-document **contradiction detection**
- **Blackboard** (SQLite) with a **hash-chained audit trail**; typed **task/output contracts** with strict validation
- **Document engine:** 61 deliverables (DOCX · XLSX · GeoJSON · DXF · SVG); missing inputs → *BLOCKED*, never fabricated
- **Human approval gates:** Engineering Reviewer → Lead → Director (+ Lender Engineer / QA Manager); issuing is impossible without them
- **Synthetic data room** (46 files) with 24 seeded issues + scorer, to regression-test the agents
- Works **without an API key** (deterministic mode); LLM mode adds CrewAI/Groq interpretation per agent

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # light: deterministic mode
python tests/run.py                          # 11 tests, no pytest needed
python run_platform.py --reset               # full pipeline -> outputs/deliverables (61 files)
streamlit run app.py                         # UI
# LLM agents (CrewAI + Groq):
pip install -r requirements-llm.txt && cp .env.example .env   # set GROQ_API_KEY
python run_platform.py --llm --model llama-3.3-70b-versatile
```
Deploy: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (GitHub, Groq, Streamlit Cloud, Docker). Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Sample outputs: `examples/sample_outputs/`.

## Repository layout
```
app.py  run_platform.py            Streamlit UI / CLI
config/  agents · workstreams · deliverables(61) · checklists
helioassure/    orchestrator · registry · contracts · blackboard · project · llm
         agents/runner.py (CrewAI)   tools/ (deterministic)   rag/   qa/   docs/   hitl/
data_room/  synthetic lender data room + generator      evaluation/  seeded issues + scorer
tests/   docs/   .github/workflows/ci.yml   Dockerfile
```

## Honest status
- **Tested here (offline):** contracts, blackboard + tamper detection, UTM maths, layout, electrical checks, dependency manager, router, validation, approval gates, full pipeline (61 deliverables, valid GeoJSON/SVG/DXF), contradiction detection on the synthetic data room.
- **Not executed in my build environment:** the **Streamlit UI** and the **CrewAI/Groq LLM path** (no network, packages/API key unavailable). They are written against the CrewAI ≥0.100 API and fail soft: LLM errors are recorded as exceptions and the deterministic results stand. Run `streamlit run app.py` and one LLM run before relying on them; pin the working `crewai` version.
- **Measured baseline (deterministic mode, no LLM):** the keyword scorer finds ~50% of the 24 seeded issues (e.g. capacity/degradation/cycling contradictions, gaps flagged in documents). Semantic issues (layout vs exclusion buffer, flood freeboard, permit expiry vs NTP, LD adequacy, DSCR on P90) need the LLM agents or extra rules. Scorer is approximate.
- Layout/cabling is **conceptual**; electrical checks are screening-level; heuristic findings are low-confidence. Output is a **draft for a qualified engineer**, not a signed opinion.
- Spec departures (dataclasses vs Pydantic, state machine vs LangGraph, BM25 vs vectors, SQLite vs Postgres) are listed in `docs/ARCHITECTURE.md`.
- Never upload confidential documents to a public Streamlit app; the free Cloud filesystem is ephemeral.

## Engineering Design Studio (added 27 October 2026)

The `11 Engineering Design` workspace adds deterministic preliminary design screens:

- **PV Array & Yield:** module/string counts, cold-weather string Voc, hot-weather string Vmp, inverter count estimate, DC/AC ratio, MPPT voltage screening and annual energy estimate.
- **BESS Sizing:** required delivered energy and duration, DoD and end-of-life SOH allowance, discharge efficiency, energy/power container counts, installed power/energy and throughput screening.
- **Cables & Grid:** approximate DC/single-phase or three-phase cable voltage drop and conductor losses, plus transformer loading and plant export-limit screening.
- **Design Register:** export calculation results to CSV and JSON.

The calculations are screening-level only. Validate all inputs against approved project design basis, manufacturer datasheets and warranties, site conditions, applicable codes/grid requirements, and detailed engineering studies. The results are not IFC design, protection settings, equipment selection approval, or a substitute for qualified engineer sign-off.
