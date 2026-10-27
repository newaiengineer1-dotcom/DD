"""Financial Calculation Agent (deterministic): LCOE, project IRR, DSCR via calcs."""
from __future__ import annotations
from helioassure.tools import calcs


def irr(cashflows: list[float], lo: float = -0.9, hi: float = 1.0) -> float | None:
    f = lambda r: sum(c / (1 + r) ** i for i, c in enumerate(cashflows))
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return round((lo + hi) / 2, 5)


def lcoe(capex: float, opex_year1: float, energy_mwh_year1: float, deg_pct: float, years: int, wacc: float, opex_infl: float = 0.02) -> dict:
    pv_c = capex + sum(opex_year1 * (1 + opex_infl) ** (y - 1) / (1 + wacc) ** y for y in range(1, years + 1))
    pv_e = sum(energy_mwh_year1 * (1 - deg_pct / 100) ** (y - 1) / (1 + wacc) ** y for y in range(1, years + 1))
    return {"lcoe_eur_per_mwh": round(pv_c * 1e6 / pv_e, 2), "pv_cost_eur_m": round(pv_c, 2), "pv_energy_gwh": round(pv_e / 1000, 1)}


def project_economics(capex_m: float, opex_m: float, energy_gwh: float, price_eur_mwh: float, deg_pct: float = 0.4, years: int = 30, wacc: float = 0.06,
                      debt_m: float = 0.0, rate_pct: float = 5.4, tenor: int = 16, bess_rev_m: float = 0.0, opex_infl: float = 0.02) -> dict:
    cfads = [energy_gwh * 1000 * (1 - deg_pct / 100) ** (y - 1) * price_eur_mwh / 1e6 + bess_rev_m - opex_m * (1 + opex_infl) ** (y - 1) for y in range(1, years + 1)]
    out = {"cfads_year1_m": round(cfads[0], 2), "project_irr": irr([-capex_m] + cfads), "lcoe": lcoe(capex_m, opex_m, energy_gwh * 1000, deg_pct, years, wacc, opex_infl)}
    if debt_m:
        d = calcs.dscr_analysis(cfads, debt_m, rate_pct, tenor, target_dscr=1.30)
        out["debt"] = {k: d[k] for k in ("annual_debt_service", "min_dscr", "avg_dscr", "llcr")}
        out["gearing_pct"] = round(debt_m / capex_m * 100, 1)
    return out
