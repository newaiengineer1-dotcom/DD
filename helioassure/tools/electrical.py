"""Electrical Calculation Agent (deterministic): string sizing, DC/AC ratio, transformer and cable checks."""
from __future__ import annotations
import math

CABLE_TABLE_AL_MV = [  # 18/30 kV XLPE Al, buried, ampacity (A) at typical conditions; R (ohm/km at 90C)
    (95, 205, 0.411), (150, 265, 0.265), (240, 345, 0.164), (400, 440, 0.101), (630, 560, 0.0637), (800, 625, 0.0502), (1000, 690, 0.0420)]


def string_sizing(voc_stc: float, tc_voc_pct_per_c: float, vmax_system: float, t_min_c: float, modules_per_string: int, isc: float, imax_input: float = 40.0, strings_per_mppt: int = 2) -> dict:
    voc_cold = voc_stc * (1 + tc_voc_pct_per_c / 100 * (t_min_c - 25))
    v_str = voc_cold * modules_per_string
    return {"voc_cold_module_v": round(voc_cold, 2), "voc_cold_string_v": round(v_str, 1), "limit_v": vmax_system, "margin_pct": round((vmax_system - v_str) / vmax_system * 100, 2),
            "voltage_ok": v_str <= vmax_system, "max_modules_per_string": int(vmax_system // voc_cold), "mppt_current_a": round(isc * 1.25 * strings_per_mppt, 1),
            "current_ok": isc * 1.25 * strings_per_mppt <= imax_input}


def dc_ac(kwp: float, inverter_n: int, inverter_kva: float, pf: float = 1.0) -> dict:
    kwac = inverter_n * inverter_kva * pf
    return {"dc_kwp": round(kwp, 1), "ac_kw": round(kwac, 1), "dc_ac_ratio": round(kwp / kwac, 3)}


def transformer_check(pv_mwac: float, bess_mw: float, export_limit_mw: float, trafo_mva: float, n_trafo: int, pf_min: float = 0.95, loading_limit: float = 1.0) -> dict:
    peak_mw = min(pv_mwac + bess_mw, export_limit_mw)           # PPC limits simultaneous export
    s_peak = peak_mw / pf_min
    cap_n1 = trafo_mva * (n_trafo - 1) if n_trafo > 1 else trafo_mva
    return {"peak_export_mw": round(peak_mw, 1), "apparent_peak_mva": round(s_peak, 1), "installed_mva": trafo_mva * n_trafo, "loading_pct_normal": round(s_peak / (trafo_mva * n_trafo) * 100, 1),
            "loading_pct_n1": round(s_peak / cap_n1 * 100, 1), "n1_ok": s_peak <= cap_n1 * loading_limit, "pv_plus_bess_exceeds_export_limit": pv_mwac + bess_mw > export_limit_mw}


def mv_cable_check(s_mva: float, v_kv: float, length_m: float, pf: float = 0.95, max_vdrop_pct: float = 2.0, x_ohm_km: float = 0.11) -> dict:
    i = s_mva * 1e3 / (math.sqrt(3) * v_kv)
    for area, amp, r in CABLE_TABLE_AL_MV:
        if amp * 0.85 >= i:                                       # 0.85 grouping/temperature derating
            dv = math.sqrt(3) * i * (r * pf + x_ohm_km * math.sqrt(1 - pf * pf)) * length_m / 1000 / (v_kv * 1000) * 100
            loss_kw = 3 * i * i * r * length_m / 1000 / 1000
            return {"current_a": round(i, 1), "selected_mm2_Al": area, "ampacity_derated_a": round(amp * 0.85), "vdrop_pct": round(dv, 3), "vdrop_ok": dv <= max_vdrop_pct, "loss_kw": round(loss_kw, 1)}
    return {"current_a": round(i, 1), "selected_mm2_Al": None, "note": "exceeds table - use parallel circuits"}


def dc_cable_vdrop(i_a: float, length_m: float, area_mm2: float = 6.0, rho: float = 0.0225, v_v: float = 1100.0) -> dict:
    dv = 2 * rho * length_m * i_a / area_mm2
    return {"vdrop_v": round(dv, 2), "vdrop_pct": round(dv / v_v * 100, 3), "loss_w": round(i_a * dv, 1)}
