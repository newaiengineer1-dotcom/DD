"""Streamlit UI - HelioAssure - AI Engineering and Due Diligence Platform for Solar PV + BESS (entry point for Streamlit Community Cloud)."""
import io, json, os, shutil, zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from helioassure import registry
from helioassure.blackboard import Blackboard
from helioassure.config import DATA_ROOM, DB_PATH, GROQ_MODELS, OUTPUT_DIR, ROOT
from helioassure.docs.renderer import catalogue
from helioassure.hitl import gates
from helioassure.orchestrator import MasterOrchestrator
from helioassure.project import FLAGS, ProjectInput, ProjectError

st.set_page_config(page_title="HelioAssure | Engineering Intelligence", layout="wide", page_icon="☀️")

# Visual-only refresh: preserve existing workflow, tabs, controls, callbacks and business logic.
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {
  --ha-bg: #07111f; --ha-panel: #0d1a2b; --ha-panel2: #112238;
  --ha-line: rgba(177, 198, 222, .15); --ha-text: #edf4ff;
  --ha-muted: #9db0c8; --ha-gold: #d8bd83; --ha-teal: #66dfcf;
}
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background:
  radial-gradient(ellipse at 10% -5%, rgba(47, 99, 130, .22), transparent 38%),
  radial-gradient(ellipse at 92% 0%, rgba(173, 140, 76, .10), transparent 28%),
  linear-gradient(180deg, #07111f 0%, #091525 52%, #07111f 100%); color: var(--ha-text); }
[data-testid="stHeader"] { background: rgba(7,17,31,.72); backdrop-filter: blur(14px); }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { max-width: 1720px; padding-top: 1.45rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0b192a 0%, #091321 100%); border-right: 1px solid var(--ha-line); }
[data-testid="stSidebar"] > div:first-child { padding-top: 1.15rem; }
[data-testid="stSidebar"] h1 { font-family: 'Manrope', sans-serif; letter-spacing: -.04em; color: #f5f8ff; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--ha-muted); }
[data-testid="stSidebar"] hr { border-color: var(--ha-line); }
[data-testid="stTabs"] [role="tablist"] { gap: .38rem; border-bottom: 1px solid var(--ha-line); padding: .42rem .3rem .65rem; background: rgba(11,25,42,.72); border-radius: 15px 15px 0 0; }
[data-testid="stTabs"] button[role="tab"] { border: 1px solid transparent; border-radius: 10px; padding: .55rem .85rem; color: #a9bbd1; font-weight: 600; transition: all .18s ease; }
[data-testid="stTabs"] button[role="tab"]:hover { color: #f7fbff; background: rgba(255,255,255,.045); border-color: var(--ha-line); }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #f4dfae; background: linear-gradient(135deg, rgba(216,189,131,.13), rgba(102,223,207,.06)); border-color: rgba(216,189,131,.38); box-shadow: inset 0 -2px 0 var(--ha-gold); }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--ha-line) !important; background: rgba(13,26,43,.68); border-radius: 16px; }
[data-testid="stMetric"] { background: linear-gradient(145deg, rgba(17,34,56,.94), rgba(10,23,39,.94)); border: 1px solid var(--ha-line); padding: 1rem 1.1rem; border-radius: 15px; box-shadow: 0 10px 28px rgba(0,0,0,.12); }
[data-testid="stMetricLabel"] { color: var(--ha-muted) !important; font-weight: 600; }
[data-testid="stMetricValue"] { color: #f5f8ff; font-family: 'Manrope', sans-serif; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border: 1px solid var(--ha-line); border-radius: 12px; overflow: hidden; }
[data-testid="stDataFrame"] [role="grid"] { background: rgba(10,22,37,.8); }
.stTextInput input, .stTextArea textarea, .stNumberInput input, [data-baseweb="select"] > div,
[data-testid="stFileUploaderDropzone"] { background: #0a1727 !important; color: var(--ha-text) !important; border-color: rgba(157,176,200,.24) !important; border-radius: 10px !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: rgba(102,223,207,.72) !important; box-shadow: 0 0 0 1px rgba(102,223,207,.2) !important; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; border: 1px solid rgba(216,189,131,.42); background: linear-gradient(135deg, #d8bd83 0%, #b99b62 100%); color: #101827; font-weight: 800; min-height: 2.55rem; box-shadow: 0 5px 18px rgba(0,0,0,.16); transition: transform .15s ease, filter .15s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { filter: brightness(1.08); transform: translateY(-1px); border-color: #f0dba9; color: #08111f; }
.stButton > button:disabled { background: #263548; color: #788ba2; border-color: #35465a; }
[data-testid="stAlert"] { border-radius: 12px; border: 1px solid var(--ha-line); }
hr { border-color: var(--ha-line) !important; }
h1, h2, h3 { font-family: 'Manrope', sans-serif !important; letter-spacing: -.035em; color: #f3f7ff; }
h2 { margin-top: 1rem; }
[data-testid="stCaptionContainer"] { color: var(--ha-muted); }
[data-testid="stExpander"] { border: 1px solid var(--ha-line); border-radius: 12px; background: rgba(13,26,43,.65); }
.ha-hero { position: relative; overflow: hidden; display:flex; align-items:center; justify-content:space-between; gap:1.5rem; padding:1.55rem 1.8rem; margin:.15rem 0 1.15rem; border:1px solid rgba(216,189,131,.27); border-radius:20px; background:linear-gradient(112deg, rgba(16,35,56,.98), rgba(11,24,41,.96) 58%, rgba(26,37,48,.95)); box-shadow:0 18px 48px rgba(0,0,0,.19); }
.ha-hero:after { content:''; position:absolute; width:260px; height:260px; right:8%; top:-170px; border-radius:50%; border:1px solid rgba(216,189,131,.20); box-shadow:0 0 0 24px rgba(216,189,131,.025), 0 0 0 50px rgba(102,223,207,.025); }
.ha-kicker { text-transform:uppercase; letter-spacing:.19em; color:var(--ha-gold); font-size:.69rem; font-weight:800; margin-bottom:.42rem; }
.ha-title { font-family:'Manrope',sans-serif; font-size:clamp(1.55rem,2.5vw,2.35rem); font-weight:800; line-height:1.12; letter-spacing:-.055em; color:#f4f7fd; }
.ha-subtitle { color:#a8bad0; font-size:.91rem; margin-top:.55rem; max-width:760px; }
.ha-mark { display:flex; align-items:center; justify-content:center; flex:0 0 66px; width:66px; height:66px; border-radius:19px; color:#142033; font-size:1.9rem; background:linear-gradient(145deg,#f0dba9,#b99b62); box-shadow:0 9px 26px rgba(216,189,131,.18); }
.ha-chip { display:inline-block; margin-top:.85rem; padding:.33rem .65rem; border:1px solid rgba(102,223,207,.27); border-radius:999px; color:#9af0e4; background:rgba(102,223,207,.06); font-size:.72rem; font-weight:700; letter-spacing:.03em; }
@media (max-width: 720px) { .block-container { padding:1rem .8rem 2rem; } .ha-hero { padding:1.2rem; } .ha-mark { flex-basis:48px; width:48px; height:48px; font-size:1.35rem; } [data-testid="stTabs"] [role="tablist"] { overflow-x:auto; } }
</style>
<div class="ha-hero">
  <div>
    <div class="ha-kicker">Solar PV · Battery Energy Storage · Lender Engineering</div>
    <div class="ha-title">HelioAssure Engineering Intelligence</div>
    <div class="ha-subtitle">Evidence-led technical due diligence, deterministic engineering tools, independent QA and controlled deliverables — in one workspace.</div>
    <div class="ha-chip">HIERARCHICAL MULTI-AGENT WORKFLOW&nbsp; · &nbsp;HUMAN APPROVAL GATES</div>
  </div>
  <div class="ha-mark">☀</div>
</div>
""", unsafe_allow_html=True)


def secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


ss = st.session_state
if "bb" not in ss:
    ss.bb = Blackboard(DB_PATH); ss.events = []; ss.orch = None
bb: Blackboard = ss.bb

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("☀️ HelioAssure")
    st.caption("ENGINEERING INTELLIGENCE · PREMIUM WORKSPACE")
    st.markdown("<div style='height:3px;border-radius:8px;background:linear-gradient(90deg,#d8bd83,#66dfcf,transparent);margin:.45rem 0 1rem'></div>", unsafe_allow_html=True)
    st.caption("Hierarchical · evidence-centric · tool-driven multi-agent engineering platform")
    use_llm = st.toggle("Enable LLM agents (CrewAI + Groq)", value=False, help="Off = deterministic tools, RAG evidence, QA and documents only (no API key needed).")
    key = st.text_input("GROQ_API_KEY", value=secret("GROQ_API_KEY"), type="password", disabled=not use_llm)
    model = st.selectbox("Model", GROQ_MODELS, disabled=not use_llm)
    st.divider()
    up = st.file_uploader("Upload project data room files", accept_multiple_files=True, help="PDF, DOCX, XLSX, CSV, TXT, JSON")
    room = Path(OUTPUT_DIR / "uploaded_data_room")
    if up and st.button("Use uploaded files as data room"):
        shutil.rmtree(room, ignore_errors=True); room.mkdir(parents=True)
        for f in up:
            (room / f.name).write_bytes(f.getvalue())
        ss.room = str(room); st.success(f"{len(up)} files stored")
    data_room = Path(ss.get("room", DATA_ROOM))
    st.caption(f"Data room: `{data_room.name}`")
    if st.button("🗑 Reset project state"):
        bb.clear(["task", "output", "finding", "assumption", "oir", "calc", "qa", "exception", "document"]); ss.events = []; st.rerun()

tabs = st.tabs(["1 Project", "2 Evidence", "3 Orchestrate", "4 Layout", "5 Findings & registers", "6 QA", "7 Approvals", "8 Deliverables", "9 Audit", "10 Architecture", "11 Engineering Design"])

# ---------------------------------------------------------------- 1 project
with tabs[0]:
    default = json.loads((ROOT / "examples" / "project_solara.json").read_text())
    txt = st.text_area("Project basis (JSON). Only coordinates and capacities are mandatory; everything else has defaults or becomes an OIR.", json.dumps(default, indent=2), height=380)
    c1, c2 = st.columns(2)
    if c1.button("Validate project basis"):
        try:
            p = ProjectInput.from_dict(json.loads(txt)); ss.project = p.to_dict(); st.success(f"Valid. DC/AC {p.pv_mwp/p.pv_mwac:.2f}; BESS {p.bess_containers*p.container_mwh} MWh DC.")
        except (ProjectError, TypeError, json.JSONDecodeError) as e:
            st.error(str(e))
    st.caption("Optional specialist agents activate from `flags`: " + ", ".join(FLAGS))

# ---------------------------------------------------------------- 2 evidence
with tabs[1]:
    from helioassure.rag.ingest import inventory
    inv = pd.DataFrame(inventory(data_room)) if data_room.exists() else pd.DataFrame()
    st.metric("Files in data room", len(inv))
    if not inv.empty:
        st.dataframe(inv, use_container_width=True, hide_index=True)
    q = st.text_input("Search evidence (BM25, cited)")
    if q and ss.get("orch") and ss.orch.index:
        for s, c in ss.orch.index.search(q, 5):
            st.markdown(f"**{c.cite}** · score {s:.1f}"); st.caption(c.text[:600])
    elif q:
        st.info("Run the orchestrator once to build the index.")

# ---------------------------------------------------------------- 3 orchestrate
with tabs[2]:
    hier = [{"Level": "Master Orchestrator", "Agents": 1}, {"Level": "Workstream Leads", "Agents": len(registry.load()[0]["leads"])},
            {"Level": "Discipline agents (core)", "Agents": len(registry.disciplines())}, {"Level": "Optional specialists", "Agents": len(registry.load()[0]["optional_specialists"])},
            {"Level": "Independent QA agents", "Agents": len(registry.load()[0]["qa_agents"])}, {"Level": "Deterministic tool agents", "Agents": 9}]
    st.dataframe(pd.DataFrame(hier), hide_index=True)
    if st.button("▶ Run full orchestration", type="primary"):
        try:
            proj = ProjectInput.from_dict(json.loads(txt))
            llm = None
            if use_llm:
                from helioassure.llm import make_llm
                llm = make_llm(model, key)
            ss.events = []
            log = st.empty()
            def ev(e):
                ss.events.append(e); log.dataframe(pd.DataFrame(ss.events[-12:]), hide_index=True)
            with st.spinner("Orchestrating…"):
                bb.clear(["task", "output", "finding", "assumption", "oir", "calc", "qa", "exception", "document"])
                ss.orch = MasterOrchestrator(bb, proj, data_room, llm=llm, use_llm=use_llm, on_event=ev, reindex=True)
                qa = ss.orch.run_all()
            st.success(f"Done. QA: {qa}")
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
    if ss.events:
        st.dataframe(pd.DataFrame(ss.events), use_container_width=True, hide_index=True)
    ex = bb.items("exception")
    if ex:
        st.warning(f"{len(ex)} exception(s) handled by the Exception Manager"); st.dataframe(pd.DataFrame(ex)[["_id", "where", "error"]], hide_index=True)

# ---------------------------------------------------------------- 4 layout
with tabs[3]:
    svg = next((d for d in bb.items("document") if d["_id"] == "D23" and d["path"]), None)
    if svg and Path(svg["path"]).exists():
        st.components.v1.html(Path(svg["path"]).read_text(), height=720, scrolling=True)
        st.caption("Conceptual layout, deterministic geometry. Orange dashed = exclusion buffer, red = MV cables, yellow = MV stations, green = BESS compound.")
    else:
        st.info("Run orchestration to generate the layout.")

# ---------------------------------------------------------------- 5 findings
with tabs[4]:
    sev = st.multiselect("Severity", ["Critical", "High", "Medium", "Low", "Info"], default=["Critical", "High", "Medium"])
    fs = [f for f in bb.items("finding") if f["_status"] != "duplicate" and f["severity"] in sev]
    if fs:
        st.dataframe(pd.DataFrame([{"ID": f["id"], "WS": f["workstream"], "Agent": f["agent"], "Severity": f["severity"], "Statement": f["statement"],
                                    "Evidence": "; ".join(c["source"] for c in f["citations"]), "Recommendation": f["recommendation"], "CP": f["condition_precedent"], "QA": f["_status"]} for f in fs]), use_container_width=True, hide_index=True)
    for kind, cols in (("oir", ["id", "question", "priority", "routed_to", "_status"]), ("assumption", ["id", "agent", "text", "basis"]), ("calc", ["id", "tool", "agent"])):
        items = bb.items(kind)
        if items:
            st.subheader({"oir": "Outstanding information requests", "assumption": "Assumptions", "calc": "Deterministic calculations"}[kind])
            st.dataframe(pd.DataFrame(items)[cols], use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- 6 QA
with tabs[5]:
    q = bb.items("qa")
    if q:
        st.dataframe(pd.DataFrame(q)[["check_id", "agent", "status", "workstream", "detail"]].sort_values("status", key=lambda s: s.map({"fail": 0, "warn": 1, "pass": 2})), use_container_width=True, hide_index=True)
    else:
        st.info("No QA results yet.")

# ---------------------------------------------------------------- 7 approvals
with tabs[6]:
    docs = bb.items("document")
    if docs:
        did = st.selectbox("Document", [d["_id"] for d in docs], format_func=lambda i: next(f"{d['_id']} - {d['title']} [{d['_status']}]" for d in docs if d["_id"] == i))
        d = next(x for x in docs if x["_id"] == did)
        cls = d.get("classes", [])
        st.write("State:", gates.doc_state(bb, did, cls), "| Required gates:", ", ".join(gates.required_gates(cls)))
        st.dataframe(pd.DataFrame([{"gate": g, **(v or {"decision": "PENDING"})} for g, v in gates.gate_status(bb, did, cls).items()]), hide_index=True)
        c1, c2, c3 = st.columns(3)
        gate = c1.selectbox("Gate", gates.required_gates(cls)); actor = c2.text_input("Your name / role"); dec = c3.radio("Decision", ["approve", "reject"], horizontal=True)
        com = st.text_input("Comment (required for rejection)")
        if st.button("Submit decision"):
            try:
                gates.submit(bb, did, gate, actor or "unknown", dec, com, cls); st.success("Recorded"); st.rerun()
            except Exception as e:
                st.error(str(e))
        qa_ok = ss.orch.qa_ok(d["ws"]) if ss.get("orch") else False
        ok, why = gates.can_issue(bb, did, qa_ok, cls)
        if st.button("Issue document", disabled=not ok):
            gates.issue(bb, did, qa_ok, cls, actor or "unknown"); st.rerun()
        if not ok:
            st.caption("Cannot issue: " + "; ".join(why))
    else:
        st.info("No documents yet.")

# ---------------------------------------------------------------- 8 deliverables
with tabs[7]:
    docs = bb.items("document")
    if docs:
        st.dataframe(pd.DataFrame(docs)[["_id", "doc_no", "title", "ws", "kind", "_status", "blocked_reason"]], use_container_width=True, hide_index=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for d in docs:
                if d["path"] and Path(d["path"]).exists():
                    z.write(d["path"], Path(d["path"]).name)
        st.download_button("⬇ Download all deliverables (zip)", buf.getvalue(), "HelioAssure_deliverables.zip")
    else:
        st.info("Nothing generated yet.")

# ---------------------------------------------------------------- 9 audit
with tabs[8]:
    st.write("Hash chain intact:", "✅" if bb.verify_audit_chain() else "❌ TAMPERED")
    st.dataframe(pd.DataFrame(bb.audit_log(300)), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- 10 architecture
with tabs[9]:
    st.markdown((ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8") if (ROOT / "docs" / "ARCHITECTURE.md").exists() else "See docs/ARCHITECTURE.md")


# ---------------------------------------------------------------- 11 engineering design studio
with tabs[10]:
    from helioassure.tools.design_studio import pv_design, bess_design, cable_voltage_drop, transformer_export_check
    st.subheader("⚡ Preliminary Engineering Design Studio")
    st.caption("Deterministic screening calculators for concept / feasibility design. Outputs are not IFC design or a substitute for vendor data, applicable standards, grid studies, or engineer approval.")
    design_tabs = st.tabs(["☀️ PV Array & Yield", "🔋 BESS Sizing", "🔌 Cables & Grid", "📑 Design Summary"])
    if "design_studio_results" not in ss:
        ss.design_studio_results = {}

    with design_tabs[0]:
        st.markdown("#### PV module, string, inverter and energy-yield screening")
        a, b, c = st.columns(3)
        with a:
            pv_mwp = st.number_input("Target PV DC capacity (MWp)", min_value=0.1, value=150.0, step=1.0, key="ds_pv_mwp")
            module_wp = st.number_input("Module rating (Wp)", min_value=100.0, value=580.0, step=5.0, key="ds_module_wp")
            module_voc = st.number_input("Module Voc at STC (V)", min_value=1.0, value=52.0, step=0.5, key="ds_module_voc")
            module_vmp = st.number_input("Module Vmp at STC (V)", min_value=1.0, value=44.0, step=0.5, key="ds_module_vmp")
            module_isc = st.number_input("Module Isc at STC (A)", min_value=0.1, value=14.0, step=0.1, key="ds_module_isc")
        with b:
            inverter_kw = st.number_input("Inverter AC rating (kW)", min_value=1.0, value=250.0, step=10.0, key="ds_inv_kw")
            dcac_target = st.number_input("Target DC/AC ratio", min_value=0.5, max_value=2.5, value=1.25, step=0.05, key="ds_dcac")
            modules_string = st.number_input("Modules per string", min_value=1, max_value=40, value=26, step=1, key="ds_modules_string")
            strings_inv = st.number_input("Strings per inverter (current screen)", min_value=1, max_value=20, value=2, step=1, key="ds_strings_inv")
            voc_coeff = st.number_input("Voc temperature coefficient (%/°C)", min_value=-1.0, max_value=-0.01, value=-0.24, step=0.01, format="%.2f", key="ds_voc_coeff")
            vmp_coeff = st.number_input("Vmp temperature coefficient (%/°C)", min_value=-1.0, max_value=-0.01, value=-0.29, step=0.01, format="%.2f", key="ds_vmp_coeff")
        with c:
            min_temp = st.number_input("Design minimum ambient temperature (°C)", min_value=-60.0, max_value=35.0, value=-5.0, step=1.0, key="ds_min_temp")
            max_cell_temp = st.number_input("Design maximum cell temperature (°C)", min_value=25.0, max_value=100.0, value=70.0, step=1.0, key="ds_max_cell")
            max_dc_v = st.number_input("Inverter absolute max DC voltage (V)", min_value=100.0, value=1500.0, step=50.0, key="ds_maxdc")
            mppt_min = st.number_input("MPPT minimum voltage (V)", min_value=50.0, value=500.0, step=25.0, key="ds_mpptmin")
            mppt_max = st.number_input("MPPT maximum voltage (V)", min_value=100.0, value=1500.0, step=50.0, key="ds_mpptmax")
            yield_kwh = st.number_input("Gross yield before PR factor (kWh/kWp/year)", min_value=100.0, value=2061.0, step=25.0, key="ds_yield")
            pr = st.number_input("Performance ratio (0–1)", min_value=0.1, max_value=1.0, value=0.82, step=0.01, key="ds_pr")
        if st.button("Calculate PV design screen", key="ds_run_pv", type="primary"):
            try:
                result = pv_design(target_mwp=pv_mwp, module_wp=module_wp, inverter_kw=inverter_kw,
                    module_voc_v=module_voc, module_vmp_v=module_vmp, module_isc_a=module_isc,
                    voc_temp_coeff_pct_c=voc_coeff, vmp_temp_coeff_pct_c=vmp_coeff,
                    min_ambient_c=min_temp, max_cell_c=max_cell_temp, inverter_max_dc_v=max_dc_v,
                    inverter_mppt_min_v=mppt_min, inverter_mppt_max_v=mppt_max,
                    modules_per_string=int(modules_string), strings_per_inverter=int(strings_inv),
                    specific_yield_kwh_kwp=yield_kwh, performance_ratio=pr, target_dc_ac_ratio=dcac_target)
                ss.design_studio_results["PV Array & Yield"] = result
                st.success("PV screening calculation complete")
            except Exception as e:
                st.error(f"Check the design inputs: {e}")
        pv_result = ss.design_studio_results.get("PV Array & Yield")
        if pv_result:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("PV DC capacity", f"{pv_result['actual_dc_mwp']:.2f} MWp")
            m2.metric("Estimated AC capacity", f"{pv_result['estimated_ac_mw']:.2f} MW")
            m3.metric("DC/AC ratio", f"{pv_result['dc_ac_ratio']:.2f}")
            m4.metric("Annual energy screen", f"{pv_result['annual_energy_mwh_estimate']:,.0f} MWh")
            st.dataframe(pd.DataFrame([{"Parameter": k.replace("_", " ").title(), "Result": v} for k, v in pv_result.items()]), hide_index=True, use_container_width=True)

    with design_tabs[1]:
        st.markdown("#### BESS power, energy, duration, degradation and container count")
        a, b, c = st.columns(3)
        with a:
            bess_mw = st.number_input("Required discharge power (MW)", min_value=0.1, value=60.0, step=1.0, key="ds_bess_mw")
            duration_h = st.number_input("Required duration (hours)", min_value=0.25, value=4.0, step=0.25, key="ds_bess_h")
            delivered_mwh = st.number_input("Required delivered energy (MWh)", min_value=0.1, value=240.0, step=5.0, key="ds_delivered")
            container_mwh = st.number_input("Energy per container (MWh DC)", min_value=0.1, value=5.0, step=0.25, key="ds_cont_mwh")
        with b:
            container_mw = st.number_input("Power per container (MW)", min_value=0.1, value=2.5, step=0.1, key="ds_cont_mw")
            dod = st.number_input("Usable depth of discharge (%)", min_value=1.0, max_value=100.0, value=90.0, step=1.0, key="ds_dod")
            eol = st.number_input("End-of-life SOH (%)", min_value=1.0, max_value=100.0, value=80.0, step=1.0, key="ds_eol")
            discharge_eff = st.number_input("Discharge-path efficiency (%)", min_value=1.0, max_value=100.0, value=95.0, step=1.0, key="ds_dis_eff")
        with c:
            rte = st.number_input("Round-trip efficiency (%)", min_value=1.0, max_value=100.0, value=88.0, step=1.0, key="ds_rte")
            cycles = st.number_input("Equivalent full cycles per year", min_value=0.0, value=300.0, step=10.0, key="ds_cycles")
            st.info("The model sizes energy and power separately, then uses the larger container count. Check the supplier's guaranteed usable energy at the point of interconnection.")
        if st.button("Calculate BESS design screen", key="ds_run_bess", type="primary"):
            try:
                result = bess_design(target_power_mw=bess_mw, delivered_energy_mwh=delivered_mwh,
                    duration_hours=duration_h, usable_dod_pct=dod, end_of_life_soh_pct=eol,
                    discharge_efficiency_pct=discharge_eff, container_energy_mwh=container_mwh,
                    container_power_mw=container_mw, annual_cycles=cycles, round_trip_efficiency_pct=rte)
                ss.design_studio_results["BESS Sizing"] = result
                st.success("BESS screening calculation complete")
            except Exception as e:
                st.error(f"Check the BESS inputs: {e}")
        bess_result = ss.design_studio_results.get("BESS Sizing")
        if bess_result:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Container count", str(bess_result["container_count_screening"]))
            m2.metric("Installed energy", f"{bess_result['installed_energy_mwh']:.1f} MWh")
            m3.metric("Installed power", f"{bess_result['installed_power_mw']:.1f} MW")
            m4.metric("Screened duration", f"{bess_result['installed_duration_hours_at_target_power']:.2f} h")
            st.dataframe(pd.DataFrame([{"Parameter": k.replace("_", " ").title(), "Result": v} for k, v in bess_result.items()]), hide_index=True, use_container_width=True)

    with design_tabs[2]:
        st.markdown("#### Cable voltage-drop and transformer / grid export screens")
        cable_col, grid_col = st.columns(2)
        with cable_col:
            st.markdown("**Cable voltage drop**")
            current_a = st.number_input("Load current (A)", min_value=0.1, value=250.0, step=5.0, key="ds_cable_i")
            length_m = st.number_input("One-way route length (m)", min_value=1.0, value=100.0, step=10.0, key="ds_cable_len")
            area_mm2 = st.number_input("Conductor cross-section (mm²)", min_value=1.0, value=150.0, step=10.0, key="ds_cable_area")
            voltage_v = st.number_input("System voltage (V)", min_value=1.0, value=800.0, step=50.0, key="ds_cable_v")
            phase_mode = st.selectbox("Circuit type", ["DC / single-phase loop", "Three-phase AC"], key="ds_cable_phases")
            rho = st.number_input("Resistivity (Ω·mm²/m)", min_value=0.001, value=0.0225, step=0.001, format="%.4f", key="ds_rho", help="Typical approximate copper resistivity at reference temperature; use design-temperature/vendor resistance for final checks.")
            if st.button("Calculate cable drop", key="ds_run_cable"):
                try:
                    res = cable_voltage_drop(current_a=current_a, one_way_length_m=length_m, conductor_area_mm2=area_mm2,
                        system_voltage_v=voltage_v, conductor_resistivity_ohm_mm2_m=rho,
                        phases=3 if phase_mode == "Three-phase AC" else 2)
                    ss.design_studio_results["Cable Voltage Drop"] = res
                except Exception as e:
                    st.error(str(e))
            cable_result = ss.design_studio_results.get("Cable Voltage Drop")
            if cable_result:
                st.metric("Voltage drop", f"{cable_result['voltage_drop_pct']:.3f}%")
                st.json(cable_result)
        with grid_col:
            st.markdown("**Transformer loading and export limit**")
            grid_pv = st.number_input("PV inverter capacity (MW AC)", min_value=0.0, value=120.0, step=5.0, key="ds_grid_pv")
            grid_bess = st.number_input("BESS discharge power (MW)", min_value=0.0, value=60.0, step=5.0, key="ds_grid_bess")
            export_limit = st.number_input("Grid export limit (MW)", min_value=0.1, value=130.0, step=5.0, key="ds_export")
            trafo_mva = st.number_input("Transformer rating each (MVA)", min_value=0.1, value=80.0, step=5.0, key="ds_trafo")
            trafo_count = st.number_input("Number of transformers", min_value=1, max_value=20, value=2, step=1, key="ds_trafo_n")
            pf_min = st.number_input("Minimum operating power factor", min_value=0.5, max_value=1.0, value=0.95, step=0.01, key="ds_pf")
            if st.button("Calculate grid / transformer screen", key="ds_run_grid"):
                try:
                    res = transformer_export_check(pv_ac_mw=grid_pv, bess_discharge_mw=grid_bess,
                        export_limit_mw=export_limit, transformer_mva_each=trafo_mva,
                        transformer_count=int(trafo_count), minimum_power_factor=pf_min)
                    ss.design_studio_results["Transformer & Export"] = res
                except Exception as e:
                    st.error(str(e))
            grid_result = ss.design_studio_results.get("Transformer & Export")
            if grid_result:
                st.metric("Normal transformer loading", f"{grid_result['normal_loading_pct']:.1f}%")
                st.json(grid_result)

    with design_tabs[3]:
        st.markdown("#### Consolidated design calculation register")
        st.caption("Run each calculator to populate the register. Exported values are preliminary and must be checked against approved design basis and manufacturer guarantees.")
        all_results = ss.design_studio_results
        if all_results:
            summary_rows = []
            for section, values in all_results.items():
                for parameter, value in values.items():
                    summary_rows.append({"Design package": section, "Parameter": parameter, "Value": value})
            summary_df = pd.DataFrame(summary_rows)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            st.download_button("⬇ Download design register (CSV)", summary_df.to_csv(index=False).encode("utf-8"), "HelioAssure_engineering_design_register.csv", "text/csv")
            st.download_button("⬇ Download calculation package (JSON)", json.dumps(all_results, indent=2).encode("utf-8"), "HelioAssure_engineering_design_package.json", "application/json")
        else:
            st.info("No engineering calculations have been run in this session yet.")
        st.warning("Engineering limitation: These tools are for preliminary screening only. Final design requires site-specific meteorology, validated energy modelling, vendor datasheets, cable installation/derating calculations, short-circuit and protection studies, grounding/lightning design, harmonics, grid-code compliance, fire strategy, and qualified engineering sign-off.")
