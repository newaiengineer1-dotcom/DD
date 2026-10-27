"""Plain-assert tests: run with `pytest -q` or `python tests/run.py` (no pytest needed)."""
import json, math, sys, tempfile, xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helioassure import registry
from helioassure.blackboard import Blackboard
from helioassure.contracts import AgentOutput, ContractError, TaskAssignment
from helioassure.hitl import gates
from helioassure.orchestrator import MasterOrchestrator
from helioassure.project import ProjectError, ProjectInput
from helioassure.tools import calcs, electrical, geometry as G, layout as L

PROJ = dict(exclusions=[{"id": "AR-07", "lat": 37.6215, "lon": -8.1935, "r": 30}], flags={"heritage_sensitive": True, "land_title_complex": True})


def test_contract_rejects_uncited_finding():
    t = TaskAssignment("T-001", "a", "WS1", "x")
    try:
        AgentOutput.from_dict({"summary": "s", "findings": [{"severity": "High", "statement": "x"}]}, t)
        assert False
    except ContractError:
        pass
    ok = AgentOutput.from_dict({"summary": "s", "findings": [{"severity": "high", "statement": "x", "citations": ["f.pdf | p.1"]}]}, t)
    assert ok.findings[0].severity == "High"


def test_blackboard_audit_chain_detects_tampering():
    bb = Blackboard(); bb.put("a", 1); bb.add("finding", "F1", {"x": 1})
    assert bb.verify_audit_chain()
    bb.db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
    assert not bb.verify_audit_chain()


def test_utm_roundtrip_and_zone():
    e, n, z = G.to_utm(37.62, -8.19)
    assert z == 29 and G.epsg(37.62, -8.19) == 32629
    la, lo = G.from_utm(e, n, z)
    assert abs(la - 37.62) < 1e-8 and abs(lo + 8.19) < 1e-8
    assert abs(G.to_utm(10, -9)[0] - 500000) < 1e-6          # central meridian
    e2, n2, z2 = G.to_utm(-33.9, 18.4)                         # southern hemisphere
    la2, lo2 = G.from_utm(e2, n2, z2, north=False)
    assert abs(la2 + 33.9) < 1e-8 and abs(lo2 - 18.4) < 1e-8


def test_layout_reaches_capacity_and_respects_exclusion():
    g = G.site_geometry(37.62, -8.19, None, 262)
    ex = [{"id": "X", "x": g["site_centre_utm"][0], "y": g["site_centre_utm"][1], "r": 80}]
    pv = L.pv_layout(g["boundary_utm"], 150001.92, exclusions=ex)
    assert pv["capacity_shortfall_kwp"] == 0 and abs(pv["kwp_placed"] - 150001.92) < 60
    assert all(math.hypot(t["x"] - ex[0]["x"], t["y"] - ex[0]["y"]) >= 80 for t in pv["tables"])
    small = G.site_geometry(37.62, -8.19, None, 40)
    assert L.pv_layout(small["boundary_utm"], 150001.92)["capacity_shortfall_kwp"] > 0      # too little land is reported, not hidden


def test_electrical_checks():
    s = electrical.string_sizing(52.7, -0.25, 1500, -5, 24, 14.02)
    assert s["voltage_ok"] and s["max_modules_per_string"] == 26
    assert not electrical.string_sizing(52.7, -0.25, 1500, -5, 28, 14.02)["voltage_ok"]
    assert not electrical.transformer_check(120, 60, 130, 90, 2)["n1_ok"]


def test_dependency_manager_detects_cycles():
    assert registry.workstream_order()[0] == "WS1" and registry.workstream_order()[-1] == "WS8"
    try:
        registry.toposort({"a": ["b"], "b": ["a"]}); assert False
    except ValueError:
        pass


def test_agent_router_and_activation():
    assert registry.route("IEC 62443 vpn security") == "ot_cyber"
    core = registry.active_disciplines({}); opt = registry.active_disciplines({"heritage_sensitive": True})
    assert len(core) == 30 and "archaeology_heritage" in opt and "archaeology_heritage" not in core


def test_project_validation():
    for bad in ({"lat": 120}, {"gcr": 0.9}, {"pv_mwp": 300}, {"bess_containers": 10}, {"flags": {"nope": True}}):
        try:
            ProjectInput(**bad).validate(); assert False, bad
        except ProjectError:
            pass


def test_gates_enforce_order_and_qa():
    bb = Blackboard(); bb.add("document", "D49", {"title": "x"}, status="draft")
    try:
        gates.submit(bb, "D49", "lead_approval", "bob", "approve", classes=["lender"]); assert False
    except PermissionError:
        pass
    for g in ("engineering_review", "lead_approval", "director_approval"):
        gates.submit(bb, "D49", g, "u", "approve", classes=["lender"])
    ok, reasons = gates.can_issue(bb, "D49", True, ["lender"]); assert not ok and "lender_engineer" in reasons[0]
    gates.submit(bb, "D49", "lender_engineer", "l", "approve", classes=["lender"])
    try:
        gates.issue(bb, "D49", qa_ok=False, classes=["lender"]); assert False
    except PermissionError:
        pass
    gates.issue(bb, "D49", qa_ok=True, classes=["lender"])
    assert bb.items("document")[0]["_status"] == "issued"


def test_end_to_end_deterministic_pipeline():
    bb = Blackboard(); o = MasterOrchestrator(bb, ProjectInput(**PROJ))
    qa = o.run_all()
    assert qa["fail"] >= 2                                                       # capacity + degradation contradictions in the synthetic data room
    assert len(bb.items("document")) == 61 and bb.verify_audit_chain()
    docs = {d["_id"]: d for d in bb.items("document")}
    assert docs["D09"]["_status"] == "blocked" and "yield" in docs["D09"]["blocked_reason"]   # no yield input -> blocked, not fabricated
    assert all(Path(d["path"]).exists() for d in docs.values() if d["_status"] == "draft")
    gj = json.loads(Path(docs["D12"]["path"]).read_text()); assert gj["features"]
    xml.dom.minidom.parseString(Path(docs["D13"]["path"]).read_text())            # valid SVG
    assert "ENTITIES" in Path(docs["D11"]["path"]).read_text()
    stmts = " ".join(f["statement"] for f in bb.items("finding"))
    assert "148442.9" in stmts and "0.25" in stmts                                 # contradiction detector found seeded inconsistencies


def test_missing_input_creates_oir_not_fiction():
    bb = Blackboard(); MasterOrchestrator(bb, ProjectInput(**PROJ)).run_all(build_docs=False)
    oirs = " ".join(o["question"] for o in bb.items("oir"))
    assert "P50/P75/P90" in oirs and "CAPEX" in oirs
