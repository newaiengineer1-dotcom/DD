"""Deterministic tool registry: name -> callable, plus which output keys the Calculation Validation Agent compares on re-run."""
from __future__ import annotations
from helioassure.tools import calcs, cables, electrical, finance, geometry, layout

TOOLS = {
    "site_geometry": geometry.site_geometry,
    "pv_layout": layout.pv_layout,
    "bess_layout": layout.bess_layout,
    "route_cables": cables.route_cables,
    "string_sizing": electrical.string_sizing,
    "dc_ac": electrical.dc_ac,
    "transformer_check": electrical.transformer_check,
    "mv_cable_check": electrical.mv_cable_check,
    "yield_exceedance": calcs.yield_exceedance,
    "dscr_analysis": calcs.dscr_analysis,
    "bess_cycle_warranty_check": calcs.bess_cycle_warranty_check,
    "ld_adequacy": calcs.ld_adequacy,
    "capacity_reconciliation": calcs.capacity_reconciliation,
    "freeboard_check": calcs.freeboard_check,
    "date_and_leadtime_check": calcs.date_and_leadtime_check,
    "degradation_energy_effect": calcs.degradation_energy_effect,
    "project_economics": finance.project_economics,
}
COMPARE = {
    "site_geometry": ["epsg", "area_ha", "site_centre_utm"], "pv_layout": ["modules_placed", "kwp_placed", "pitch_m"], "bess_layout": ["total_mwh_dc", "compound_area_m2"],
    "route_cables": ["mv_length_m", "dc_length_m"], "string_sizing": ["voc_cold_string_v", "voltage_ok"], "dc_ac": ["dc_ac_ratio"], "transformer_check": ["loading_pct_n1", "n1_ok"],
    "mv_cable_check": ["selected_mm2_Al", "vdrop_pct"], "yield_exceedance": ["combined_sigma_pct", "p90_over_p50_pct"], "dscr_analysis": ["min_dscr", "llcr"],
    "bess_cycle_warranty_check": ["excess_fec_per_year"], "ld_adequacy": ["ld_cover_of_debt_service_pct"], "capacity_reconciliation": ["difference_kwp"],
    "freeboard_check": ["freeboard_m"], "date_and_leadtime_check": ["weeks"], "degradation_energy_effect": ["difference_gwh"], "project_economics": ["cfads_year1_m", "project_irr"],
}


def run_tool(name: str, inputs: dict):
    return TOOLS[name](**inputs)
