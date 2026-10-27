"""
Master Orchestrator. Pipeline:  validate -> plan (WBS + agent activation + dependencies) -> deterministic tool agents ->
RAG evidence per discipline task -> discipline interpretation (deterministic checks always; LLM optional) -> workstream-lead consolidation
-> independent QA -> document generation -> human approval gates. Everything is written to the blackboard + hash-chained audit log.
"""
from __future__ import annotations
import math, re
from pathlib import Path
from typing import Callable, Optional

from helioassure import registry
from helioassure.blackboard import Blackboard
from helioassure.config import DATA_ROOM, EVIDENCE_MIN_SCORE
from helioassure.contracts import AgentOutput, Assumption, CalcRecord, Citation, ContractError, Finding, OIR, TaskAssignment
from helioassure.project import ProjectInput
from helioassure.qa import QAResult, calc_validation, contradictions, coordinates, evidence as qa_evidence, reconciliation
from helioassure.rag.evidence_scan import scan
from helioassure.rag.retriever import build_index
from helioassure.tools import geometry as G, layout as L, cables as C, electrical as E, finance as Fin
from helioassure.tools.registry import run_tool

TRIM = {"tables", "units", "boundary_lonlat", "boundary_utm", "exclusions", "stations", "mv_routes", "compound_utm", "dscr_profile"}


class MasterOrchestrator:
    def __init__(self, bb: Blackboard, project: ProjectInput, data_room: Path = DATA_ROOM, llm=None, on_event: Optional[Callable] = None, use_llm: bool = False, reindex: bool = False):
        self.bb, self.project, self.root = bb, project.validate(), Path(data_room)
        self.llm, self.use_llm, self.emit = llm, bool(llm and use_llm), on_event or (lambda e: None)
        import hashlib
        self.index_name = "dataroom_" + hashlib.md5(str(self.root.resolve()).encode()).hexdigest()[:8]
        self.index = build_index(self.root, self.index_name, force=reindex) if self.root.exists() else None
        self.notes: list[str] = []
        self.n_calc = len(bb.items("calc"))

    # ------------------------------------------------------------------ helpers
    def _calc(self, tool: str, inputs: dict, agent: str) -> dict:
        out = run_tool(tool, inputs)
        self.n_calc += 1
        cid = f"C{self.n_calc:03d}"
        self.bb.add("calc", cid, CalcRecord(cid, tool, inputs, {k: v for k, v in out.items() if k not in TRIM}, agent).__dict__, agent=agent, status="recorded")
        out["_calc_id"] = cid
        return out

    def _finding(self, agent: str, ws: str, sev: str, cat: str, statement: str, cites: list, rec: str = "", impact: str = "", gap=False, cp=False, conf="high"):
        n = len(self.bb.items("finding")) + 1
        f = Finding(f"F-{n:03d}", agent, ws, sev, cat, statement, [Citation.from_any(c) for c in cites], impact, rec, cp, gap, conf).validate()
        self.bb.add("finding", f.id, f.__dict__ | {"citations": [c.__dict__ for c in f.citations]}, ws, agent, "draft")
        return f

    def _oir(self, agent: str, question: str, reason: str, prio="Medium"):
        n = len(self.bb.items("oir")) + 1
        routed = registry.route(question + " " + reason, self.project.flags)
        o = OIR(f"OIR-{n:03d}", agent, question, reason, prio, routed)
        self.bb.add("oir", o.id, o.__dict__, agent=agent, status="open")

    def _assume(self, agent: str, text: str, basis: str):
        n = len(self.bb.items("assumption")) + 1
        a = Assumption(f"AS-{n:03d}", agent, text, basis)
        self.bb.add("assumption", a.id, a.__dict__, agent=agent, status="assumed")

    def _exception(self, where: str, err: str):
        n = len(self.bb.items("exception")) + 1
        self.bb.add("exception", f"EX-{n:03d}", {"where": where, "error": err, "handled_by": "exception_manager"}, status="open")
        self.emit({"type": "exception", "where": where, "error": err})

    # ------------------------------------------------------------------ 1. plan
    def plan(self) -> list[TaskAssignment]:
        p = self.project
        self.bb.put("project", p.to_dict(), "master_orchestrator")
        agents = registry.active_disciplines(p.flags)
        order = registry.workstream_order()
        ws_tasks: dict[str, list[str]] = {w: [] for w in order}
        tasks, n = [], 0
        for w in order:
            deps = registry.workstreams()[w]["depends_on"]
            for aid, a in agents.items():
                if a["workstream"] != w:
                    continue
                n += 1
                tid = f"T-{n:03d}"
                dep_tasks = [t for d in deps for t in ws_tasks[d]]
                t = TaskAssignment(tid, aid, w, f"As {a['name']}: review the project data room against your scope ({a['role']}). Use deterministic tool results; cite evidence; raise OIRs for gaps.",
                                   {k: v for k, v in p.to_dict().items() if k in ("name", "pv_mwp", "pv_mwac", "bess_mw", "bess_mwh_dc", "bess_usable_mwh_poi", "export_limit_mw", "lat", "lon")},
                                   a["queries"], a.get("tools", []), dep_tasks,
                                   ["every finding cites evidence or a calculation id", "missing evidence is an OIR or gap finding", "no unsupported numbers"], [])
                ws_tasks[w].append(tid); tasks.append(t)
                self.bb.add("task", tid, t.to_dict(), w, aid, "planned", "project_planning_agent")
        self.bb.put("plan", {"order": order, "n_tasks": len(tasks), "optional_activated": [k for k, v in agents.items() if v.get("optional")]}, "project_planning_agent")
        self.emit({"type": "plan", "tasks": len(tasks), "workstreams": order})
        return tasks

    # ------------------------------------------------------------------ 2. deterministic tool agents
    def run_tool_agents(self):
        p, bb = self.project, self.bb
        # --- site geometry
        geo = self._calc("site_geometry", {"lat": p.lat, "lon": p.lon, "boundary_lonlat": p.boundary_lonlat, "stated_area_ha": p.site_area_ha}, "site_geometry_agent")
        geo.pop("_calc_id"); bb.put("geometry", geo, "site_geometry_agent")
        if geo["boundary_assumed"]:
            self._assume("site_geometry_agent", f"Site boundary assumed as a {geo['area_ha']} ha rectangle centred on the stated coordinates.", "No surveyed boundary supplied")
            self._oir("site_geometry_agent", "Provide the surveyed site boundary (KML/GeoJSON/DXF) with CRS.", "Layout, area and constraint checks are indicative until a surveyed boundary is available", "High")
        bnd = geo["boundary_utm"]
        excl = []
        for e in p.exclusions:
            x, y, _ = G.to_utm(e["lat"], e["lon"], geo["utm_zone"])
            excl.append({"id": e["id"], "x": round(x, 2), "y": round(y, 2), "r": e["r"]})
        # --- reserve BESS compound + substation before PV layout
        per_row = 9
        w = per_row * 6.06 + (per_row - 1) * 3.0 + 20; h = math.ceil(p.bess_containers / per_row) * 2.44 + (math.ceil(p.bess_containers / per_row) - 1) * 6.0 + 20
        xs = [q[0] for q in bnd]; ys = [q[1] for q in bnd]
        ox = max(xs) - 12 - w + 10; oy = (min(ys) + max(ys)) / 2 - h / 2
        reserve = [{"id": "BESS_RESERVE", "x": round(ox + w / 2 - 10, 1), "y": round(oy + h / 2 - 10, 1), "r": round(math.hypot(w, h) / 2 + 5, 1)}]
        sub = {"x": round(ox + w / 2 - 10, 2), "y": round(oy + h + 55, 2), "inside_boundary": G.point_in_polygon(ox + w / 2 - 10, oy + h + 55, bnd), "assumed": True}
        reserve.append({"id": "SUBSTATION_RESERVE", "x": sub["x"], "y": sub["y"], "r": 45})
        bb.put("substation", sub, "pv_layout_agent")
        self._assume("pv_layout_agent", "Substation and BESS compound located on the east side of the site; PV layout avoids them.", "No site plan supplied - conceptual placement")
        # --- PV layout
        pv = self._calc("pv_layout", {"boundary_utm": bnd, "target_kwp": p.pv_mwp * 1000, "module_wp": p.module_wp, "modules_per_table": p.modules_per_table, "gcr": p.gcr, "exclusions": excl + reserve}, "pv_layout_agent")
        pv.pop("_calc_id"); bb.put("pv_layout", pv, "pv_layout_agent")
        self._assume("pv_layout_agent", f"Horizontal single-axis tracker, 1P, N-S axis, GCR {p.gcr}, tables of {p.modules_per_table} modules, 10 m perimeter setback.", "Typical utility-scale design; confirm with EPC")
        # --- BESS layout
        bl = self._calc("bess_layout", {"boundary_utm": bnd, "containers": p.bess_containers, "container_mwh": p.container_mwh, "origin": [ox + 10, oy + 10]}, "bess_layout_agent")
        bl.pop("_calc_id"); bb.put("bess_layout", bl, "bess_layout_agent")
        # --- cables
        cb = self._calc("route_cables", {"tables": pv["tables"], "substation": sub, "n_stations": p.n_mv_stations, "bess_units": bl["units"]}, "cable_routing_agent")
        cb.pop("_calc_id"); bb.put("cables", cb, "cable_routing_agent")
        # --- electrical
        n_inv = math.ceil(p.pv_mwac * 1000 / p.inverter_kva)
        el = {"string": self._calc("string_sizing", {"voc_stc": p.module_voc, "tc_voc_pct_per_c": p.module_tc_voc, "vmax_system": 1500, "t_min_c": p.t_min_c, "modules_per_string": p.modules_per_string, "isc": p.module_isc}, "electrical_calc_agent"),
              "dc_ac": self._calc("dc_ac", {"kwp": pv["kwp_placed"], "inverter_n": n_inv, "inverter_kva": p.inverter_kva}, "electrical_calc_agent"),
              "transformer": self._calc("transformer_check", {"pv_mwac": p.pv_mwac, "bess_mw": p.bess_mw, "export_limit_mw": p.export_limit_mw, "trafo_mva": p.trafo_mva, "n_trafo": p.n_trafo}, "electrical_calc_agent"),
              "mv_cable": self._calc("mv_cable_check", {"s_mva": p.pv_mwac / p.n_mv_stations, "v_kv": p.mv_kv, "length_m": max(r["length_m"] for r in cb["mv_routes"])}, "electrical_calc_agent")}
        bb.put("electrical", el, "electrical_calc_agent")
        # --- yield
        if p.p50_specific_yield:
            y = self._calc("yield_exceedance", {"p50_specific_yield": p.p50_specific_yield, "sigma_components_pct": p.sigma_components_pct, "capacity_kwp": pv["kwp_placed"]}, "energy_yield_agent")
            bb.put("yield", y, "energy_yield_agent")
        else:
            self._oir("energy_yield_agent", "Provide the independent P50/P75/P90 yield assessment (specific yield, loss tree, uncertainty).", "Energy yield cannot be calculated without approved yield inputs", "High")
        # --- finance
        if all(v is not None for v in (p.capex_m, p.opex_m, p.price_eur_mwh)) and p.p50_specific_yield:
            f = self._calc("project_economics", {"capex_m": p.capex_m, "opex_m": p.opex_m, "energy_gwh": p.p50_specific_yield * pv["kwp_placed"] / 1e6, "price_eur_mwh": p.price_eur_mwh, "debt_m": p.debt_m or 0.0}, "financial_calc_agent")
            bb.put("finance", f, "financial_calc_agent")
        else:
            self._oir("financial_calc_agent", "Provide CAPEX, OPEX, tariff/PPA price and debt terms for the financial sensitivity module.", "Economics and DSCR need approved commercial inputs", "Medium")
        self.emit({"type": "tools_done", "calcs": self.n_calc})

    # ------------------------------------------------------------------ 3. tool-derived findings
    def _tool_findings(self):
        bb, p = self.bb, self.project
        cid = {c["_id"]: c for c in bb.items("calc")}
        by_tool = {}
        for c in cid.values():
            by_tool.setdefault(c["tool"], []).append(c)
        last = lambda t: by_tool[t][-1]["_id"] if t in by_tool else None
        pv, el, bl, geo = bb.get("pv_layout"), bb.get("electrical", {}), bb.get("bess_layout"), bb.get("geometry")
        if pv and pv["capacity_shortfall_kwp"] > 0:
            self._finding("layout_constructability", "WS3", "High", "Layout", f"Available land fits only {pv['kwp_placed']:.0f} kWp of the {pv['kwp_target']:.0f} kWp target (shortfall {pv['capacity_shortfall_kwp']:.0f} kWp).", [f"calc:{last('pv_layout')}"], "Increase land, raise GCR/DC density or reduce capacity.")
        if geo and geo["boundary_assumed"]:
            self._finding("layout_constructability", "WS3", "Medium", "Layout", "Layout is indicative: no surveyed site boundary was supplied.", [f"calc:{last('site_geometry')}"], "Supply surveyed boundary and constraint layers.", conf="high")
        t = el.get("transformer")
        if t and not t["n1_ok"]:
            self._finding("electrical_design", "WS3", "Medium", "Electrical", f"With {p.n_trafo} x {p.trafo_mva:.0f} MVA transformers, N-1 loading at peak export is {t['loading_pct_n1']}% (>100%): loss of one unit constrains export.", [f"calc:{last('transformer_check')}"], "Confirm N-1 philosophy with TSO or add transformer capacity / curtailment scheme.", "Export availability and revenue.")
        if t and t["pv_plus_bess_exceeds_export_limit"]:
            self._finding("grid_integration", "WS4", "Info", "Grid", f"PV ({p.pv_mwac} MWac) + BESS ({p.bess_mw} MW) exceeds the {p.export_limit_mw} MW export limit; PPC export limiting is required.", [f"calc:{last('transformer_check')}"], "Quantify curtailment and BESS co-optimisation in the yield/revenue model.")
        s = el.get("string")
        if s and not s["voltage_ok"]:
            self._finding("electrical_design", "WS3", "High", "Electrical", f"Cold string voltage {s['voc_cold_string_v']} V exceeds {s['limit_v']} V system limit.", [f"calc:{last('string_sizing')}"], "Reduce modules per string.", cp=True)
        if s and not s["current_ok"]:
            self._finding("electrical_design", "WS3", "Medium", "Electrical", f"MPPT input current check fails ({s['mppt_current_a']} A).", [f"calc:{last('string_sizing')}"], "Verify inverter MPPT current rating.")
        if bl and not bl["spacing_ok"]:
            self._finding("battery_safety", "WS7", "High", "BESS safety", f"Container spacing {bl['spacing_m']} m is below the assumed minimum {bl['min_spacing_required_m']} m.", [f"calc:{last('bess_layout')}"], "Justify by fire-spread analysis / large-scale fire test.")
        fi = bb.get("finance")
        if fi and fi.get("debt") and fi["debt"]["min_dscr"] < 1.30:
            self._finding("project_finance", "WS6", "High", "Finance", f"Minimum DSCR {fi['debt']['min_dscr']} is below the 1.30x sizing criterion at P50 inputs.", [f"calc:{last('project_economics')}"], "Resize debt or revisit revenue assumptions.", cp=True)
        y = bb.get("yield")
        if y:
            self._finding("energy_yield", "WS2", "Info", "Yield", f"P90/P50 = {y['p90_over_p50_pct']}% with combined uncertainty {y['combined_sigma_pct']}% (recomputed).", [f"calc:{last('yield_exceedance')}"], "Compare with the independent yield report.")

    # ------------------------------------------------------------------ 4. discipline tasks
    def evidence_pack(self, task: TaskAssignment):
        if not self.index:
            return "", [], list(task.evidence_queries), []
        pack, missing, chunks = [], [], []
        for q in task.evidence_queries:
            hits = self.index.search(q, 3)
            if not hits or hits[0][0] < EVIDENCE_MIN_SCORE:
                missing.append(q); continue
            for s, c in hits:
                pack.append(f"{c.cite}\n{c.text[:700]}"); chunks.append(c)
        seen, uniq = set(), []
        for c in chunks:
            if (c.source, c.locator) not in seen:
                seen.add((c.source, c.locator)); uniq.append(c)
        return "\n---\n".join(pack), uniq, missing, scan(uniq, 3)

    def run_discipline_task(self, task: TaskAssignment):
        a = registry.active_disciplines(self.project.flags)[task.agent_id]
        pack, chunks, missing, neg = self.evidence_pack(task)
        for q in missing:                                                   # Missing Evidence Agent
            self._oir(task.agent_id, f"No evidence found in the data room for: '{q}'. Provide the relevant document(s).", f"{a['name']} could not verify this topic", "Medium")
        for n in neg:                                                       # heuristic negative-evidence scan
            self._finding(task.agent_id, task.workstream, "Medium", "Potential gap (heuristic)", f"Document indicates an open/absent item: \"{n['quote']}\"", [Citation(n["source"], n["locator"], n["quote"])],
                          "Confirm with the project team; request the missing evidence or close-out.", gap=True, conf="low")
        out_state = "deterministic"
        if self.use_llm:
            try:
                tool_res = "\n".join(f"{k}: {str(v)[:500]}" for k, v in self.bb.get("electrical", {}).items()) if task.agent_id in ("electrical_design", "grid_integration") else ""
                tool_res += f"\ncalcs: {[ (c['_id'], c['tool'], str(c['outputs'])[:200]) for c in self.bb.items('calc') if c['agent'].split('_')[0] in task.agent_id or task.agent_id.split('_')[0] in c['agent']][:4]}"
                from helioassure.agents.runner import run_llm_task
                out = run_llm_task(task, pack, tool_res, self.llm, self.notes, on_wait=lambda w, n: self.emit({"type": "rate_limit_wait", "seconds": w, "task": task.task_id}))
                self._store_output(out)
                out_state = "llm"
            except Exception as e:              # Exception Manager: record, continue with deterministic results
                self._exception(task.task_id, f"{task.agent_id}: {e}")
        self.bb.set_status("task", task.task_id, f"done:{out_state}", task.agent_id)
        self.emit({"type": "task_done", "task": task.task_id, "agent": task.agent_id, "mode": out_state, "missing": len(missing), "heuristic": len(neg)})

    def _store_output(self, out: AgentOutput):
        known = {re.sub(r"\W+", " ", f["statement"].lower())[:80] for f in self.bb.items("finding")}
        for f in out.findings:
            if re.sub(r"\W+", " ", f.statement.lower())[:80] in known:
                continue
            n = len(self.bb.items("finding")) + 1
            f.id = f"F-{n:03d}"
            self.bb.add("finding", f.id, f.__dict__ | {"citations": [c.__dict__ for c in f.citations]}, f.workstream, f.agent, "draft")
        for a in out.assumptions:
            self.bb.add("assumption", f"{a.id}-{out.task_id}", a.__dict__, agent=out.agent_id, status="assumed")
        for o in out.oirs:
            o.routed_to = registry.route(o.question, self.project.flags)
            self.bb.add("oir", f"{o.id}-{out.task_id}", o.__dict__, agent=out.agent_id, status="open")
        self.bb.add("output", out.task_id, {"summary": out.summary, "status": out.status, "calc_requests": out.calc_requests}, agent=out.agent_id, status=out.status)

    def run_workstreams(self, only: list[str] | None = None):
        order = registry.workstream_order()
        tasks = {t["task_id"]: t for t in self.bb.items("task")}
        done: set[str] = set()
        for w in order:
            if only and w not in only:
                continue
            for tid, t in tasks.items():
                if t["workstream"] != w:
                    continue
                if any(d not in done for d in t["depends_on"] if only is None):
                    self._exception(tid, "dependency not complete"); continue
                ta = TaskAssignment(**{k: t[k] for k in TaskAssignment.__dataclass_fields__})
                self.run_discipline_task(ta); done.add(tid)

    # ------------------------------------------------------------------ 5. leads consolidate
    def consolidate(self):
        seen = set()
        for f in sorted(self.bb.items("finding"), key=lambda x: ["Critical", "High", "Medium", "Low", "Info"].index(x["severity"])):
            key = re.sub(r"\W+", " ", f["statement"].lower())[:90]
            if key in seen:
                self.bb.set_status("finding", f["_id"], "duplicate", "workstream_lead"); continue
            seen.add(key)
        for w, spec in registry.workstreams().items():
            fs = [f for f in self.bb.items("finding", workstream=w) if f["_status"] != "duplicate"]
            sev = {s: sum(1 for f in fs if f["severity"] == s) for s in ("Critical", "High", "Medium", "Low", "Info")}
            self.bb.add("output", f"LEAD-{w}", {"workstream": w, "name": spec["name"], "findings": len(fs), "severity": sev, "open_oirs": len([o for o in self.bb.items("oir") if o["_status"] == "open" and registry.disciplines().get(o["routed_to"], {}).get("workstream") == w])}, w, spec["lead"], "consolidated")

    # ------------------------------------------------------------------ 6. independent QA
    def run_qa(self):
        bb = self.bb
        bb.clear(["qa"])
        results: list[QAResult] = []
        findings = [f for f in bb.items("finding") if f["_status"] != "duplicate"]
        results += qa_evidence.validate_findings(findings, self.index, self.root, {c["_id"] for c in bb.items("calc")}) if self.index else []
        results += calc_validation.validate_calcs(bb.items("calc"))
        state = {k: bb.get(k) for k in ("project", "geometry", "pv_layout", "bess_layout", "substation", "electrical", "cables")}
        results += coordinates.check(state) + reconciliation.reconcile(state)
        if self.index:
            cres, cdet = contradictions.detect(self.index)
            results += cres; bb.put("contradictions", cdet, "contradiction_detection_agent")
            for d in cdet:                                                  # contradictions become cited findings
                if d["status"] == "pass":
                    continue
                cites = [Citation(o["source"], o["locator"], o["quote"][:200]) for o in d["observations"][:4]]
                self._finding("contradiction_detection", d["workstream"], "High" if d["status"] == "fail" else "Medium", "Cross-document inconsistency",
                              f"{d['quantity']}: documents disagree - values {d['values']} (spread {d['spread_pct']}%).", cites, "Reconcile and confirm the governing value; update the lower-ranked documents/model.", cp=d["status"] == "fail", conf="high")
            results += qa_evidence.validate_findings([f for f in bb.items("finding") if f["agent"] == "contradiction_detection" and f["_status"] == "draft"], self.index, self.root)
        for r in results:
            bb.add("qa", r.check_id, r.to_dict(), r.workstream, r.agent, r.status)
        for r in results:
            if r.check_id.startswith("EV-"):
                bb.set_status("finding", r.check_id[3:], "qa_pass" if r.status == "pass" else "qa_fail", "evidence_validation_agent")
        summary = {s: sum(1 for r in results if r.status == s) for s in ("pass", "warn", "fail")}
        self.emit({"type": "qa_done", **summary})
        return summary

    def qa_ok(self, ws: str) -> bool:
        return not any(q["status"] == "fail" and q["workstream"] in (ws, "ALL") for q in self.bb.items("qa"))

    # ------------------------------------------------------------------ 7. orchestrated run
    def run_all(self, build_docs: bool = True):
        self.plan()
        self.run_tool_agents()
        self._tool_findings()
        self.run_workstreams()
        self.consolidate()
        qa = self.run_qa()
        self.consolidate()
        if build_docs:
            from helioassure.docs.renderer import build_all
            build_all(self.bb, self)
        self.bb.audit("master_orchestrator", "run_all.complete", qa)
        return qa
