"""
Document Generation Engine: template-driven, data-driven. Content comes ONLY from blackboard items (findings, calcs, assumptions, OIRs, QA)
- the renderer never invents text. Missing inputs make a deliverable BLOCKED (with the reason), not fabricated.
"""
from __future__ import annotations
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from helioassure import registry
from helioassure.config import CONFIG_DIR, OUTPUT_DIR
from helioassure.docs import exporters as X
from helioassure.hitl.gates import ROLES, required_gates

SEV = ["Critical", "High", "Medium", "Low", "Info"]
WATERMARK = "DRAFT - AI-assisted engineering output. Requires human engineering review and approval before issue. CONCEPTUAL - NOT FOR CONSTRUCTION."


@lru_cache(maxsize=1)
def catalogue() -> list[dict]:
    return yaml.safe_load((CONFIG_DIR / "deliverables.yaml").read_text(encoding="utf-8"))["deliverables"]


def doc_no(proj: dict, spec: dict, rev="A") -> str:
    return f"HAS-{proj.get('code','PRJ')}-{spec['ws']}-{spec['id']}-Rev{rev}"


# ------------------------------------------------------------------ data helpers
def _findings(bb, spec, include_dups=False):
    fs = [f for f in bb.items("finding") if include_dups or f["_status"] != "duplicate"]
    if spec.get("agents"):
        fs = [f for f in fs if f["agent"] in spec["agents"]]
    elif spec["builder"] == "narrative":
        fs = [f for f in fs if f["workstream"] == spec["ws"]]
    return sorted(fs, key=lambda f: SEV.index(f["severity"]))


def _cites(f):
    return "; ".join(f"{c['source']}{(' | ' + c['locator']) if c.get('locator') else ''}" for c in f.get("citations", [])) or "NO EVIDENCE (gap)"


def _flat(d: dict, n=8):
    return {k: v for k, v in list(d.items())[:n] if not isinstance(v, (list, dict)) or len(str(v)) < 80}


# ------------------------------------------------------------------ docx helpers
def _table(doc, rows, header=True):
    if not rows:
        return
    t = doc.add_table(rows=1, cols=len(rows[0])); t.style = "Light Grid Accent 1"
    for j, h in enumerate(rows[0]):
        t.rows[0].cells[j].text = str(h)
    for r in rows[1:]:
        cells = t.add_row().cells
        for j, v in enumerate(r):
            cells[j].text = str(v)[:600]
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8)
    doc.add_paragraph()


def _header(doc, spec, proj, no, status, bb):
    doc.add_heading(spec["title"], 0)
    p = doc.add_paragraph(WATERMARK); p.runs[0].font.color.rgb = RGBColor(0xC0, 0, 0); p.runs[0].font.size = Pt(8)
    _table(doc, [["Document no.", "Revision", "Date", "Workstream", "Status", "Project"],
                 [no, "A", date.today().isoformat(), f"{spec['ws']} - {registry.workstreams()[spec['ws']]['name']}", status, proj.get("name", "")]])


def _approval_block(doc, bb, spec, doc_id):
    doc.add_heading("Approval record", 2)
    ap = {}
    for a in bb.approvals(doc_id):
        ap[a["gate"]] = a
    rows = [["Gate", "Role", "Decision", "Actor", "Date", "Comment"]]
    for g in required_gates(spec.get("classes")):
        a = ap.get(g)
        rows.append([g, ROLES[g], a["decision"] if a else "PENDING", a["actor"] if a else "", a["ts"][:10] if a else "", a["comment"] if a else ""])
    _table(doc, rows)


def _qa_summary(bb, ws):
    q = [x for x in bb.items("qa") if x["workstream"] in (ws, "ALL")]
    return {s: sum(1 for x in q if x["status"] == s) for s in ("pass", "warn", "fail")}, [x for x in q if x["status"] in ("fail", "warn") and not x["check_id"].startswith("EV-")][:12]


def _narrative(doc, bb, spec, proj):
    doc.add_heading("1. Purpose and scope", 1)
    doc.add_paragraph(f"This deliverable ('{spec['title']}') is generated from the project blackboard for {proj.get('name')}. It reports evidence-backed findings and deterministic calculation results; it does not contain unreferenced engineering conclusions.")
    _table(doc, [["Parameter", "Value"], ["PV DC / AC", f"{proj.get('pv_mwp')} MWp / {proj.get('pv_mwac')} MWac"], ["BESS", f"{proj.get('bess_mw')} MW / {proj.get('bess_mwh_dc')} MWh DC ({proj.get('bess_usable_mwh_poi')} MWh usable at POI)"],
                 ["Export limit", f"{proj.get('export_limit_mw')} MW"], ["Location", f"{proj.get('lat')}, {proj.get('lon')}"]])
    doc.add_heading("2. Basis and assumptions", 1)
    ass = [a for a in bb.items("assumption") if not spec.get("agents") or a["agent"] in spec["agents"] or a["agent"].endswith("_agent")]
    _table(doc, [["ID", "Agent", "Assumption", "Basis"]] + [[a["id"], a["agent"], a["text"], a["basis"]] for a in ass[:15]]) if ass else doc.add_paragraph("No assumptions recorded for this scope.")
    calcs = [c for c in bb.items("calc") if c["tool"] in spec.get("calcs", [])]
    if calcs:
        doc.add_heading("3. Calculations (deterministic, independently re-run by Calculation Validation Agent)", 1)
        _table(doc, [["Calc ID", "Tool", "Key outputs"]] + [[c["id"], c["tool"], str(_flat(c["outputs"]))] for c in calcs])
    doc.add_heading("4. Findings", 1)
    fs = _findings(bb, spec)
    if fs:
        _table(doc, [["ID", "Severity", "Statement", "Evidence", "Recommendation", "QA"]] + [[f["id"], f["severity"], f["statement"], _cites(f), f["recommendation"], f["_status"]] for f in fs])
    else:
        doc.add_paragraph("No findings recorded for this scope. Absence of findings is not evidence of adequacy: see section 5 for outstanding information.")
    doc.add_heading("5. Outstanding information (OIRs)", 1)
    oirs = [o for o in bb.items("oir") if o["agent"] in (spec.get("agents") or []) or registry.disciplines().get(o.get("routed_to", ""), {}).get("workstream") == spec["ws"]]
    _table(doc, [["ID", "Question", "Reason", "Priority", "Routed to"]] + [[o["id"], o["question"], o["reason"], o["priority"], o["routed_to"]] for o in oirs[:20]]) if oirs else doc.add_paragraph("None.")
    s, bad = _qa_summary(bb, spec["ws"])
    doc.add_heading("6. QA status", 1)
    doc.add_paragraph(f"Independent QA checks for {spec['ws']}: pass {s['pass']}, warn {s['warn']}, fail {s['fail']}.")
    if bad:
        _table(doc, [["Check", "Agent", "Status", "Detail"]] + [[x["check_id"], x["agent"], x["status"], x["detail"]] for x in bad])


def _lender(doc, bb, spec, proj):
    doc.add_heading("1. Scope and method", 1)
    doc.add_paragraph("Lender-grade technical due diligence synthesis: discipline agents, deterministic tools, evidence retrieval, independent QA. All findings are traceable to a data-room citation or a calculation ID.")
    allf = [f for f in bb.items("finding") if f["_status"] != "duplicate"]
    doc.add_heading("2. Findings summary", 1)
    _table(doc, [["Severity", "Count"]] + [[s, sum(1 for f in allf if f["severity"] == s)] for s in SEV])
    for w in registry.workstream_order():
        fs = sorted([f for f in allf if f["workstream"] == w], key=lambda f: SEV.index(f["severity"]))
        doc.add_heading(f"3.{w[2:]} {w} - {registry.workstreams()[w]['name']}", 2)
        _table(doc, [["ID", "Sev.", "Finding", "Evidence", "Recommendation", "CP"]] + [[f["id"], f["severity"], f["statement"], _cites(f), f["recommendation"], "Y" if f["condition_precedent"] else ""] for f in fs]) if fs else doc.add_paragraph("No findings.")
    doc.add_heading("4. Conditions precedent (proposed)", 1)
    cps = [f for f in allf if f["condition_precedent"]]
    _table(doc, [["Ref", "Condition", "Evidence"]] + [[f["id"], f["recommendation"] or f["statement"], _cites(f)] for f in cps]) if cps else doc.add_paragraph("None proposed by agents - engineer to confirm.")
    doc.add_heading("5. QA verification", 1)
    s, bad = _qa_summary(bb, "ALL"); doc.add_paragraph(f"pass {s['pass']} / warn {s['warn']} / fail {s['fail']}.")
    _table(doc, [["Check", "Agent", "Status", "Detail"]] + [[x["check_id"], x["agent"], x["status"], x["detail"]] for x in bad])


def _exec(doc, bb, spec, proj):
    allf = [f for f in bb.items("finding") if f["_status"] != "duplicate"]
    top = [f for f in sorted(allf, key=lambda f: SEV.index(f["severity"])) if f["severity"] in ("Critical", "High")][:8]
    doc.add_heading("Summary", 1)
    doc.add_paragraph(f"{proj.get('name')}: {proj.get('pv_mwp')} MWp / {proj.get('pv_mwac')} MWac PV and {proj.get('bess_mw')} MW / {proj.get('bess_mwh_dc')} MWh BESS. "
                      f"{len(allf)} findings ({sum(1 for f in allf if f['severity'] in ('Critical','High'))} High/Critical), {len([o for o in bb.items('oir') if o['_status']=='open'])} open information requests.")
    doc.add_heading("Key items for decision makers", 2)
    _table(doc, [["ID", "Severity", "Issue", "Action"]] + [[f["id"], f["severity"], f["statement"], f["recommendation"]] for f in top]) if top else doc.add_paragraph("No High/Critical items recorded.")
    pv, el, fin = bb.get("pv_layout"), bb.get("electrical", {}), bb.get("finance")
    rows = [["Metric", "Value"]]
    if pv: rows.append(["Layout capacity (conceptual)", f"{pv['kwp_placed']:.0f} kWp on {pv['area_used_ha']} ha"])
    if el.get("dc_ac"): rows.append(["DC/AC ratio", el["dc_ac"]["dc_ac_ratio"]])
    if fin: rows.append(["Project IRR / LCOE", f"{fin['project_irr']} / {fin['lcoe']['lcoe_eur_per_mwh']} EUR/MWh"])
    _table(doc, rows)


def _qa_docs(doc, bb, spec, proj):
    pref = {"qa_report": None, "qa_report_xd": "XD-", "qa_report_contra": "CONTRA-"}[spec["builder"]]
    q = [x for x in bb.items("qa") if pref is None or x["check_id"].startswith(pref) or (spec["builder"] == "qa_report_contra" and x["check_id"].startswith("EV-"))]
    doc.add_heading("QA results", 1)
    s = {k: sum(1 for x in q if x["status"] == k) for k in ("pass", "warn", "fail")}
    doc.add_paragraph(f"pass {s['pass']} / warn {s['warn']} / fail {s['fail']}")
    _table(doc, [["Check", "Agent", "Status", "Workstream", "Detail"]] + [[x["check_id"], x["agent"], x["status"], x["workstream"], x["detail"]] for x in sorted(q, key=lambda x: {"fail": 0, "warn": 1, "pass": 2}[x["status"]])])
    if spec["builder"] == "qa_report_contra":
        for d in bb.get("contradictions", []):
            doc.add_heading(f"{d['quantity']} - {d['status'].upper()}", 3)
            _table(doc, [["Value", "Source", "Context"]] + [[o["value"], o["source"], o["quote"][:220]] for o in d["observations"]])


# ------------------------------------------------------------------ registers (xlsx)
def _xlsx(path: Path, sheets: dict):
    wb = Workbook(); wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name[:31]); [ws.append(list(map(lambda v: v if isinstance(v, (int, float)) or v is None else str(v)[:900], r))) for r in rows]
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="12355B")
        for i in range(1, ws.max_column + 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(70, max(10, max(len(str(ws.cell(r, i).value or "")) for r in range(1, min(ws.max_row, 40) + 1)) + 2))
        ws.freeze_panes = "A2"
    wb.save(path)


def _register(bb, spec, orch):
    b = spec["builder"]
    allf = [f for f in bb.items("finding") if f["_status"] != "duplicate"]
    if b == "register_assumptions":
        return {"Assumptions": [["ID", "Agent", "Assumption", "Basis", "Status"]] + [[a["id"], a["agent"], a["text"], a["basis"], a["_status"]] for a in bb.items("assumption")]}
    if b == "register_oir":
        return {"OIR": [["ID", "Raised by", "Question", "Reason", "Priority", "Routed to", "Status"]] + [[o["id"], o["agent"], o["question"], o["reason"], o["priority"], o["routed_to"], o["_status"]] for o in bb.items("oir")]}
    if b == "register_risk":
        return {"Risks": [["ID", "Workstream", "Agent", "Severity", "Category", "Statement", "Evidence", "Recommendation", "CP", "Gap", "QA"]] + [[f["id"], f["workstream"], f["agent"], f["severity"], f["category"], f["statement"], _cites(f), f["recommendation"], "Y" if f["condition_precedent"] else "", "Y" if f["gap"] else "", f["_status"]] for f in sorted(allf, key=lambda f: SEV.index(f["severity"]))]}
    if b == "register_cp":
        return {"Conditions precedent": [["Ref", "Condition", "Severity", "Evidence", "Owner (assign)", "Status"]] + [[f["id"], f["recommendation"] or f["statement"], f["severity"], _cites(f), "", "Open"] for f in allf if f["condition_precedent"]]}
    if b == "register_gaps":
        return {"Gaps": [["Ref", "Gap", "Evidence", "Action"]] + [[f["id"], f["statement"], _cites(f), f["recommendation"]] for f in allf if f["gap"]] + [[o["id"], o["question"], "-", "Provide document"] for o in bb.items("oir")]}
    if b == "register_documents":
        return {"Documents": [["Doc ID", "Document no.", "Title", "Workstream", "Format", "Status", "Blocked reason"]] + [[d["_id"], d["doc_no"], d["title"], d["ws"], d["kind"], d["_status"], d.get("blocked_reason", "")] for d in bb.items("document")]}
    if b == "register_calcs":
        return {"Calculations": [["ID", "Tool", "Agent", "Inputs (summary)", "Outputs"]] + [[c["id"], c["tool"], c["agent"], str({k: v for k, v in c["inputs"].items() if not isinstance(v, (list, dict))}), str(_flat(c["outputs"], 10))] for c in bb.items("calc")]}
    if b == "register_evidence":
        rows, seen = [["Source", "Locator", "Cited by finding", "Quote"]], set()
        for f in allf:
            for c in f.get("citations", []):
                if (c["source"], c["locator"], f["id"]) not in seen:
                    seen.add((c["source"], c["locator"], f["id"])); rows.append([c["source"], c["locator"], f["id"], c.get("quote", "")])
        return {"Evidence": rows}
    if b == "register_audit":
        return {"Audit": [["Seq", "Timestamp", "Actor", "Action", "Payload", "Hash"]] + [[a["seq"], a["ts"], a["actor"], a["action"], a["payload"], a["hash"][:16]] for a in bb.audit_log(1000)]}
    if b == "register_cables":
        cb = bb.get("cables") or {}
        return {"MV stations": [["ID", "x (UTM)", "y (UTM)", "Tables"]] + [[s["id"], s["x"], s["y"], s["tables"]] for s in cb.get("stations", [])], "MV routes": [["From", "To", "Length (m)"]] + [[r["from"], r["to"], r["length_m"]] for r in cb.get("mv_routes", [])]}
    if b == "register_quantities":
        pv, cb, bl, el = bb.get("pv_layout") or {}, bb.get("cables") or {}, bb.get("bess_layout") or {}, bb.get("electrical", {})
        p = bb.get("project", {})
        return {"Quantities": [["Item", "Quantity", "Unit", "Basis"], ["PV modules", pv.get("modules_placed"), "pcs", "layout"], ["Tracker tables", len(pv.get("tables", [])), "pcs", "layout"], ["Strings", (pv.get("modules_placed") or 0) // p.get("modules_per_string", 24), "pcs", "modules / modules per string"],
                               ["Inverters", (el.get("dc_ac") or {}).get("ac_kw", 0) / p.get("inverter_kva", 1), "pcs", "AC kW / kVA"], ["MV stations", len(cb.get("stations", [])), "pcs", "cable routing"], ["MV cable", cb.get("mv_length_m"), "m", "conceptual routing +5%"],
                               ["DC cable (string)", cb.get("dc_length_m"), "m", "conceptual estimate"], ["BESS containers", len(bl.get("units", [])), "pcs", "layout"], ["Area used", pv.get("area_used_ha"), "ha", "layout"]]}
    if b == "register_finance":
        fin, p = bb.get("finance"), bb.get("project", {})
        return {"Finance": [["Item", "Value"], ["CAPEX (EUR m)", p.get("capex_m")], ["OPEX year 1 (EUR m)", p.get("opex_m")], ["Price (EUR/MWh)", p.get("price_eur_mwh")], ["Debt (EUR m)", p.get("debt_m")]] + ([[k, str(v)] for k, v in fin.items() if k != "_calc_id"] if fin else [["STATUS", "BLOCKED - commercial inputs not supplied (see OIR register)"]])}
    if b == "register_standards":
        pat = re.compile(r"\b(IEC(?: TS)? ?\d{4,5}(?:-\d+)*|UL ?\d{4}A?|NFPA ?\d{2,3}|EN ?\d{4,5}(?:-\d+)?|ISO ?\d{4,5}|IEEE ?\d+|VDE AR ?\d+(?:-\d)?)\b")
        cnt: dict[str, set] = {}
        for c in (orch.index.chunks if orch and orch.index else []):
            for m in pat.findall(c.text):
                cnt.setdefault(re.sub(r"\s+", " ", m.upper()), set()).add(c.source)
        return {"Standards": [["Standard (as cited)", "Documents citing", "Example source"]] + [[k, len(v), sorted(v)[0]] for k, v in sorted(cnt.items())]}
    if b == "register_permits":
        rows = [["Source", "Row"]]
        if orch and orch.index:
            for c in orch.index.chunks:
                if "permit" in c.source.lower() and c.source.endswith(".xlsx"):
                    rows += [[c.source, line] for line in c.text.splitlines()[:40]]
        return {"Permits": rows if len(rows) > 1 else [["STATUS"], ["No permit tracker in data room - see OIR register"]]}
    if b == "register_compliance":
        ck = yaml.safe_load((CONFIG_DIR / "checklists.yaml").read_text(encoding="utf-8"))
        rows = [["Phase", "Section", "Checklist item", "Minimum", "Best practice", "Evidence located", "Status"]]
        for ph, d in ck.items():
            for sec, items in d["sections"].items():
                for it in items:
                    hits = orch.index.search(it["item"], 1) if orch and orch.index else []
                    ok = bool(hits and hits[0][0] >= 3.5)
                    rows.append([ph, sec, it["item"], it["min"], it["best"], hits[0][1].cite if ok else "", "EVIDENCE LOCATED - engineer to assess adequacy" if ok else "NO EVIDENCE FOUND"])
        return {"Compliance matrix": rows}
    raise KeyError(b)


# ------------------------------------------------------------------ drawings
def _drawing(bb, spec, path: Path, proj):
    geo, pv, bl, sub, cb = bb.get("geometry"), bb.get("pv_layout"), bb.get("bess_layout"), bb.get("substation"), bb.get("cables")
    b = spec["builder"]
    if b == "layout_geojson": txt = X.layout_geojson(geo, pv, bl, sub, cb)
    elif b == "bess_geojson": txt = X.layout_geojson(geo, None, bl, sub, None)
    elif b == "layout_dxf": txt = X.layout_dxf(geo, pv, bl, sub, proj.get("name", ""))
    elif b == "bess_dxf": txt = X.layout_dxf(geo, None, bl, sub, proj.get("name", "") + " BESS")
    elif b == "layout_svg": txt = X.layout_svg(geo, pv, bl, sub, None, title=proj.get("name", ""))
    elif b == "cable_svg": txt = X.layout_svg(geo, pv, bl, sub, cb, title=proj.get("name", "") + " - MV routes")
    path.write_text(txt, encoding="utf-8")


# ------------------------------------------------------------------ build
def build_one(bb, spec: dict, orch=None, outdir: Path | None = None) -> dict:
    proj = bb.get("project", {})
    outdir = outdir or OUTPUT_DIR / "deliverables"; outdir.mkdir(parents=True, exist_ok=True)
    no = doc_no(proj, spec)
    missing = [n for n in spec.get("needs", []) if bb.get(n) is None]
    ext = {"docx": "docx", "xlsx": "xlsx", "geojson": "geojson", "dxf": "dxf", "svg": "svg"}[spec["kind"]]
    path = outdir / f"{no}.{ext}"
    status, reason = "draft", ""
    try:
        if missing and spec["kind"] in ("dxf", "geojson", "svg"):
            status, reason = "blocked", f"missing inputs: {missing}"
        elif spec["kind"] == "docx":
            d = Document()
            _header(d, spec, proj, no, "BLOCKED" if missing else "DRAFT", bb)
            if missing:
                status, reason = "blocked", f"missing inputs: {missing}"
                d.add_heading("BLOCKED", 1); d.add_paragraph(f"Required inputs not available: {missing}. See the OIR register. No content has been fabricated.")
            else:
                {"narrative": _narrative, "lender_report": _lender, "exec_summary": _exec, "qa_report": _qa_docs, "qa_report_xd": _qa_docs, "qa_report_contra": _qa_docs}[spec["builder"]](d, bb, spec, proj)
            _approval_block(d, bb, spec, spec["id"]); d.save(path)
        elif spec["kind"] == "xlsx":
            _xlsx(path, _register(bb, spec, orch))
        else:
            _drawing(bb, spec, path, proj)
    except Exception as e:                       # Exception Manager handles; deliverable stays blocked
        status, reason = "blocked", f"render error: {e}"
    meta = {"doc_no": no, "title": spec["title"], "ws": spec["ws"], "kind": spec["kind"], "path": str(path) if path.exists() else "", "classes": spec.get("classes", []), "blocked_reason": reason}
    bb.add("document", spec["id"], meta, spec["ws"], "document_renderer_agent", status)
    return meta


def build_all(bb, orch=None, only: list[str] | None = None) -> list[dict]:
    out = []
    # register documents last so the document register is complete
    specs = sorted(catalogue(), key=lambda s: s["builder"] == "register_documents")
    for spec in specs:
        if only and spec["id"] not in only:
            continue
        out.append(build_one(bb, spec, orch))
    # rebuild document registers now that all documents exist
    for spec in catalogue():
        if spec["builder"] == "register_documents" and (not only or spec["id"] in only):
            build_one(bb, spec, orch)
    return out
