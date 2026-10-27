"""Cross-Discipline Reconciliation Agent: do PV, BESS, electrical, grid, cable and layout numbers agree with the project basis?"""
from __future__ import annotations
from helioassure.qa import QAResult


def reconcile(state: dict) -> list[QAResult]:
    p, pv, bess, el, cab = state.get("project", {}), state.get("pv_layout"), state.get("bess_layout"), state.get("electrical", {}), state.get("cables")
    out = []

    def add(i, ok, detail, ws, warn=False):
        out.append(QAResult(f"XD-{i:02d}", "cross_discipline", "pass" if ok else ("warn" if warn else "fail"), detail, ws))

    if pv:
        d = (pv["kwp_placed"] - p["pv_mwp"] * 1000) / (p["pv_mwp"] * 1000) * 100
        add(1, abs(d) <= 0.5, f"layout capacity {pv['kwp_placed']:.0f} kWp vs basis {p['pv_mwp']*1000:.0f} kWp ({d:+.2f}%)", "WS3")
        add(2, pv["capacity_shortfall_kwp"] == 0, f"land sufficient for target capacity (shortfall {pv['capacity_shortfall_kwp']} kWp)", "WS3")
    if bess:
        add(3, abs(bess["total_mwh_dc"] - p["bess_mwh_dc"]) < 1e-6, f"BESS layout {bess['total_mwh_dc']} MWh DC vs basis {p['bess_mwh_dc']} MWh", "WS7")
        add(4, bess["spacing_ok"], f"container spacing {bess['spacing_m']} m vs minimum {bess['min_spacing_required_m']} m (to be confirmed by fire-spread evidence)", "WS7", warn=True)
    if el.get("dc_ac"):
        add(5, abs(el["dc_ac"]["ac_kw"] / 1000 - p["pv_mwac"]) < 0.5, f"inverter AC {el['dc_ac']['ac_kw']/1000:.1f} MW vs basis {p['pv_mwac']} MW", "WS3")
        add(6, 1.1 <= el["dc_ac"]["dc_ac_ratio"] <= 1.5, f"DC/AC ratio {el['dc_ac']['dc_ac_ratio']} within 1.1-1.5 typical range", "WS3", warn=True)
    if el.get("string"):
        add(7, el["string"]["voltage_ok"], f"cold string voltage {el['string']['voc_cold_string_v']} V vs limit {el['string']['limit_v']} V", "WS3")
    if el.get("transformer"):
        t = el["transformer"]
        add(8, t["n1_ok"], f"transformer N-1 loading {t['loading_pct_n1']}% (>100% means one unit cannot carry peak export)", "WS3", warn=True)
        add(9, not t["pv_plus_bess_exceeds_export_limit"], "PV+BESS nameplate exceeds export limit - PPC limitation must be implemented and revenue impact assessed" if t["pv_plus_bess_exceeds_export_limit"] else "nameplate within export limit", "WS4", warn=True)
    if el.get("mv_cable"):
        add(10, el["mv_cable"].get("vdrop_ok", False), f"MV cable voltage drop {el['mv_cable'].get('vdrop_pct')}%", "WS3")
    if cab:
        add(11, cab["mv_length_m"] > 0 and len(cab["stations"]) == p["n_mv_stations"], f"{len(cab['stations'])} MV stations routed, {cab['mv_length_m']} m MV cable", "WS3")
    return out
