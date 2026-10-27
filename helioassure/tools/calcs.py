"""
Deterministic engineering / finance calculators.
LLMs are unreliable at arithmetic, so every number a lender will rely on (P-values, DSCR, LD adequacy,
lead-time checks, capacity reconciliation) is computed here and the agent only interprets the result.
"""
from __future__ import annotations
import math
from datetime import date, datetime
from statistics import NormalDist

Z = {"P50": 0.0, "P75": 0.6745, "P90": 1.2816, "P95": 1.6449, "P99": 2.3263}


def yield_exceedance(p50_specific_yield: float, sigma_components_pct: list[float], capacity_kwp: float | None = None) -> dict:
    """Combine independent 1-sigma uncertainties (RSS) and return P50/P75/P90/P95/P99 (normal assumption)."""
    s = math.sqrt(sum(x * x for x in sigma_components_pct))
    out = {"combined_sigma_pct": round(s, 3), "pvalues": {}}
    for k, z in Z.items():
        sy = p50_specific_yield * (1 - z * s / 100)
        out["pvalues"][k] = {"specific_yield_kwh_per_kwp": round(sy, 1)}
        if capacity_kwp:
            out["pvalues"][k]["energy_gwh"] = round(sy * capacity_kwp / 1e6, 2)
    out["p90_over_p50_pct"] = round(out["pvalues"]["P90"]["specific_yield_kwh_per_kwp"] / p50_specific_yield * 100, 2)
    return out


def annuity_payment(debt: float, rate_pct: float, tenor: int) -> float:
    r = rate_pct / 100
    return debt / tenor if r == 0 else debt * r / (1 - (1 + r) ** -tenor)


def dscr_analysis(cfads: list[float], debt: float, rate_pct: float, tenor: int, lockup_dscr: float | None = None,
                  target_dscr: float | None = None) -> dict:
    """Level-annuity debt service vs CFADS (same currency unit, e.g. EUR m). Returns DSCR profile, min/avg, LLCR."""
    ds = annuity_payment(debt, rate_pct, tenor)
    prof = [round(cfads[i] / ds, 3) for i in range(min(tenor, len(cfads)))]
    r = rate_pct / 100
    npv = sum(cfads[i] / (1 + r) ** (i + 1) for i in range(min(tenor, len(cfads))))
    res = {"annual_debt_service": round(ds, 3), "dscr_profile": prof, "min_dscr": min(prof), "avg_dscr": round(sum(prof) / len(prof), 3),
           "llcr": round(npv / debt, 3), "years_below_target": None}
    if target_dscr:
        res["years_below_target"] = [i + 1 for i, d in enumerate(prof) if d < target_dscr]
        res["max_debt_at_target_flat_cfads_min"] = round(min(cfads[:tenor]) / target_dscr * (1 - (1 + r) ** -tenor) / r, 2) if r else None
    if lockup_dscr:
        res["years_below_lockup"] = [i + 1 for i, d in enumerate(prof) if d < lockup_dscr]
    return res


def scale_cfads(base_cfads: list[float], revenue_share_scaled: float, revenue: list[float], factor: float) -> list[float]:
    """Helper for sensitivities: scale the scaled-revenue share of revenue by `factor` (e.g. 0.935 for P90/P50) and keep costs."""
    return [c + rev * revenue_share_scaled * (factor - 1) for c, rev in zip(base_cfads, revenue)]


def bess_cycle_warranty_check(model_cycles_per_day: float, warranty_fec_per_year: float, warranty_years: int,
                              arbitrage_revenue_year1: float | None = None) -> dict:
    model_fec = model_cycles_per_day * 365
    ex = model_fec - warranty_fec_per_year
    res = {"model_fec_per_year": round(model_fec, 1), "warranty_cap_fec_per_year": warranty_fec_per_year,
           "excess_fec_per_year": round(ex, 1), "excess_pct_of_cap": round(ex / warranty_fec_per_year * 100, 1),
           "cumulative_model_fec": round(model_fec * warranty_years), "cumulative_cap_fec": round(warranty_fec_per_year * warranty_years),
           "exceeds_cap": ex > 0, "revenue_overstatement_pct_if_capped": round(max(0, ex) / model_fec * 100, 1)}
    if arbitrage_revenue_year1:
        res["arbitrage_revenue_at_risk"] = round(arbitrage_revenue_year1 * res["revenue_overstatement_pct_if_capped"] / 100, 3)
    return res


def ld_adequacy(delay_ld_per_day: float, annual_debt_service: float, annual_revenue: float, annual_fixed_costs: float,
                contract_price: float, ld_cap_pct: float) -> dict:
    """All money in the same unit (e.g. EUR). Compares daily LD to daily exposure and the time to cap."""
    ds_d, rev_d, fx_d = annual_debt_service / 365, annual_revenue / 365, annual_fixed_costs / 365
    cap = contract_price * ld_cap_pct / 100
    return {"daily_debt_service": round(ds_d), "daily_revenue": round(rev_d), "daily_fixed_costs": round(fx_d),
            "ld_cover_of_debt_service_pct": round(delay_ld_per_day / ds_d * 100, 1),
            "ld_cover_of_lost_revenue_pct": round(delay_ld_per_day / rev_d * 100, 1),
            "ld_cap_amount": round(cap), "days_to_reach_cap": round(cap / delay_ld_per_day, 1),
            "uncovered_daily_exposure": round(max(0, ds_d + fx_d - delay_ld_per_day))}


def _d(x: str) -> date:
    return datetime.strptime(x, "%Y-%m-%d").date()


def date_and_leadtime_check(start_date: str, end_date: str, required_weeks_min: float | None = None,
                            required_weeks_max: float | None = None, deadline: str | None = None) -> dict:
    a, b = _d(start_date), _d(end_date)
    wk = (b - a).days / 7
    res = {"days": (b - a).days, "weeks": round(wk, 1)}
    if required_weeks_min is not None:
        res["shortfall_weeks_vs_min"] = round(max(0, required_weeks_min - wk), 1)
        res["earliest_delivery_at_min_leadtime"] = (a.toordinal() + int(required_weeks_min * 7))
        res["earliest_delivery_at_min_leadtime"] = date.fromordinal(res["earliest_delivery_at_min_leadtime"]).isoformat()
    if required_weeks_max is not None:
        res["latest_delivery_at_max_leadtime"] = date.fromordinal(a.toordinal() + int(required_weeks_max * 7)).isoformat()
    if deadline:
        res["days_from_end_to_deadline"] = (_d(deadline) - b).days
    return res


def capacity_reconciliation(modules: int, module_wp: float, stated_kwp: float) -> dict:
    kwp = modules * module_wp / 1000
    return {"computed_kwp": round(kwp, 2), "stated_kwp": stated_kwp, "difference_kwp": round(kwp - stated_kwp, 2),
            "difference_pct_of_stated": round((kwp - stated_kwp) / stated_kwp * 100, 3)}


def freeboard_check(equipment_level_m: float, flood_level_m: float, required_freeboard_m: float = 0.5) -> dict:
    fb = equipment_level_m - flood_level_m
    return {"freeboard_m": round(fb, 2), "required_m": required_freeboard_m, "compliant": fb >= required_freeboard_m,
            "shortfall_m": round(max(0, required_freeboard_m - fb), 2)}


def degradation_energy_effect(p50_gwh_year1: float, deg_a_pct: float, deg_b_pct: float, years: int = 25) -> dict:
    ea = sum(p50_gwh_year1 * (1 - deg_a_pct / 100) ** y for y in range(years))
    eb = sum(p50_gwh_year1 * (1 - deg_b_pct / 100) ** y for y in range(years))
    return {"lifetime_gwh_a": round(ea, 1), "lifetime_gwh_b": round(eb, 1), "difference_gwh": round(ea - eb, 1),
            "difference_pct": round((ea - eb) / ea * 100, 2)}


def months_between(d1: str, d2: str) -> float:
    a, b = _d(d1), _d(d2)
    return round((b - a).days / 30.4375, 1)
