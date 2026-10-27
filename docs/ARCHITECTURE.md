# Architecture: Hybrid, Hierarchical, Evidence-Centric, Tool-Driven Multi-Agent Engineering Platform

AI agents **interpret evidence and coordinate**; deterministic tools **calculate and draw**; humans **approve**.

```
                     ┌──────────────────────── Human approval gates (helioassure/hitl) ───────────────────────┐
                     │ Engineering Reviewer → Lead Engineer → Project Director (+ Lender Eng./QA Mgr)  │
                     └───────────────▲──────────────────────────────────────────────────▲──────────────┘
 ProjectInput ─► MASTER ORCHESTRATOR ─► Workstream Leads (8) ─► Discipline agents (30 core + 10 optional)
 (validated)     plan·deps·route·       consolidate/dedupe        interpret EVIDENCE PACK + TOOL RESULTS
                 exceptions·audit            │                        │ (CrewAI + Groq, optional)
                       │                     │                        ▼
                       │                     │               Typed contracts (AgentOutput) ─ reject/retry/escalate
                       ▼                     ▼
  Deterministic tool agents      RAG/Evidence agents          Independent QA agents (6)
  geometry·PV/BESS layout·       ingest·BM25 retrieve·        evidence·calc re-run·coordinates·
  cables·electrical·yield·       citation·missing-evidence    cross-discipline·contradictions
  finance·registers·renderer     ·negative-evidence scan
                       └──────────────► BLACKBOARD (SQLite, hash-chained audit) ◄──────────────┘
                                                 │
                                  Document Generation Engine (61 deliverables:
                                  DOCX · XLSX · GeoJSON · DXF · SVG) — blocked, never fabricated
```

## Mapping of the specification to code
| Specification | Implementation |
|---|---|
| Master Orchestrator, Planning, Dependency Manager, Router, Exception Manager | `helioassure/orchestrator.py`, `helioassure/registry.py` (toposort + cycle detection, keyword router) |
| 8 workstreams + leads | `config/workstreams.yaml`, `config/agents.yaml: leads`, `Orchestrator.consolidate()` |
| 30 core discipline agents | `config/agents.yaml: disciplines` |
| Optional specialists (activated by conditions) | `config/agents.yaml: optional_specialists`, `ProjectInput.flags` |
| Task Assignment / Agent Output contracts | `helioassure/contracts.py` (strict validation; invalid LLM output is retried once then escalated) |
| Shared state / blackboard + audit trail | `helioassure/blackboard.py` (SQLite; SHA-256 hash chain; tamper test) |
| Deterministic tool agents | `helioassure/tools/*` (UTM geometry, PV/BESS layout, cable routing, electrical, yield, finance) |
| RAG / evidence agents | `helioassure/rag/*` (ingest PDF/DOCX/XLSX/CSV/TXT, BM25, citations, negative-evidence scan, missing-evidence → OIR) |
| Independent QA agents | `helioassure/qa/*` (evidence validation, calculation re-run, coordinate consistency, cross-discipline reconciliation, contradiction detection) |
| Document generation (61 deliverables) | `config/deliverables.yaml`, `helioassure/docs/renderer.py`, `helioassure/docs/exporters.py` |
| Human-in-the-loop | `helioassure/hitl/gates.py` (ordered gates, rejection needs comment, `issue()` blocked without all gates + QA) |
| Deployment phase 1 (modular monolith) | single Python app, Streamlit UI, CLI, Docker |

## Deliberate departures from the spec (and why)
- **Dataclasses, not Pydantic**, for contracts: stdlib-only, testable anywhere. Swap to Pydantic v2 at `contracts.py` if you want JSON-schema export.
- **Custom state machine, not LangGraph**: the dependency graph is small and explicit; LangGraph can wrap `MasterOrchestrator` steps later.
- **BM25 retrieval, not vectors**: engineering queries are token-heavy (clause numbers, MWp, dates); deterministic and auditable. Add embeddings/pgvector via `helioassure/rag/retriever.py` for paraphrase recall.
- **SQLite, not PostgreSQL**: same schema ports directly; sufficient for Phase 1.
- **LLM is optional**: all QA, geometry, calculations, registers and documents work without any API key.
- Some "agents" in the specification (Dependency Manager, Router, Register Generator, Document Renderer, QA agents) are **deterministic modules** by design - they must not hallucinate.

## Safety properties (tested)
1. An uncited finding is rejected unless explicitly a gap. 2. Every calculation is re-executed by an independent module. 3. Missing inputs → OIR + BLOCKED deliverable. 4. Layout capacity shortfalls are reported, not hidden. 5. Issue requires all ordered approvals + QA. 6. Audit chain tamper-evident.

## Limits
Layout/cable routes are **conceptual** (no terrain, shading, soil, trench or protection design). Electrical checks are screening-level. Heuristic negative-evidence findings are `confidence: low` and need human confirmation. Not a substitute for a licensed engineer's judgement.
