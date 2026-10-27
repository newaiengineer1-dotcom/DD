"""Deterministic preliminary Solar PV + BESS design calculations.

These calculations are screening tools only. They are not a substitute for
manufacturer-specific design, detailed simulation, applicable standards, or
signed engineering review.
"""
from __future__ import annotations
import math
from typing import Any


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite value greater than zero")
    return value


def pv_design(*, target_mwp: float, module_wp: float, inverter_kw: float,
              module_voc_v: float, module_vmp_v: float, module_isc_a: float,
              voc_temp_coeff_pct_c: float, vmp_temp_coeff_pct_c: float,
              min_ambient_c: float, max_cell_c: float, inverter_max_dc_v: float,
              inverter_mppt_min_v: float, inverter_mppt_max_v: float,
              modules_per_string: int, strings_per_inverter: int,
              specific_yield_kwh_kwp: float, performance_ratio: float, target_dc_ac_ratio: float = 1.25) -> dict[str, Any]:
    """Calculate PV array counts, voltage windows, DC/AC ratio and yield estimate."""
    for n, v in [("target_mwp", target_mwp), ("module_wp", module_wp), ("inverter_kw", inverter_kw),
                 ("module_voc_v", module_voc_v), ("module_vmp_v", module_vmp_v),
                 ("module_isc_a", module_isc_a), ("inverter_max_dc_v", inverter_max_dc_v),
                 ("specific_yield_kwh_kwp", specific_yield_kwh_kwp)]:
        _positive(n, v)
    if modules_per_string < 1 or strings_per_inverter < 1:
        raise ValueError("Modules/string and strings/inverter must be at least 1")
    if not 0 < performance_ratio <= 1:
        raise ValueError("Performance ratio must be between 0 and 1")
    if target_dc_ac_ratio <= 0:
        raise ValueError("target_dc_ac_ratio must be greater than zero")
    if not inverter_mppt_min_v < inverter_mppt_max_v <= inverter_max_dc_v:
        raise ValueError("Check inverter voltage limits: MPPT min < MPPT max <= absolute DC max")
    if voc_temp_coeff_pct_c >= 0:
        raise ValueError("Voc temperature coefficient should normally be negative (%/°C)")
    if vmp_temp_coeff_pct_c >= 0:
        raise ValueError("Vmp temperature coefficient should normally be negative (%/°C)")

    target_kwp = target_mwp * 1000
    minimum_module_count = math.ceil(target_kwp * 1000 / module_wp)
    strings = math.ceil(minimum_module_count / modules_per_string)
    module_count = strings * modules_per_string
    actual_kwp = module_count * module_wp / 1000
    # Estimate inverter count from the requested DC/AC ratio and inverter AC rating.
    inverters = max(1, math.ceil(actual_kwp / (inverter_kw * target_dc_ac_ratio)))
    ac_mw = inverters * inverter_kw / 1000
    dc_ac_ratio = actual_kwp / ac_mw
    voc_cold = module_voc_v * (1 + (voc_temp_coeff_pct_c / 100) * (min_ambient_c - 25))
    vmp_hot = module_vmp_v * (1 + (vmp_temp_coeff_pct_c / 100) * (max_cell_c - 25))
    cold_string_v = voc_cold * modules_per_string
    hot_string_v = vmp_hot * modules_per_string
    max_modules_cold = math.floor(inverter_max_dc_v / voc_cold)
    min_modules_mppt_hot = math.ceil(inverter_mppt_min_v / vmp_hot)
    max_modules_mppt_cold = math.floor(inverter_mppt_max_v / (module_vmp_v * (1 + (vmp_temp_coeff_pct_c / 100) * (min_ambient_c - 25))))
    annual_mwh = actual_kwp * specific_yield_kwh_kwp * performance_ratio / 1000
    return {
        "target_dc_mwp": round(target_mwp, 3), "module_count": module_count,
        "actual_dc_mwp": round(actual_kwp / 1000, 4), "module_power_wp": module_wp,
        "total_strings": strings, "modules_per_string": modules_per_string,
        "strings_per_inverter_design_input": strings_per_inverter,
        "estimated_inverter_count": inverters, "inverter_unit_kw": inverter_kw,
        "estimated_ac_mw": round(ac_mw, 3), "dc_ac_ratio": round(dc_ac_ratio, 3),
        "target_dc_ac_ratio_input": target_dc_ac_ratio,
        "cold_voc_module_v": round(voc_cold, 2), "cold_string_voc_v": round(cold_string_v, 1),
        "hot_vmp_module_v": round(vmp_hot, 2), "hot_string_vmp_v": round(hot_string_v, 1),
        "max_modules_string_absolute_dc_limit": max_modules_cold,
        "min_modules_string_mppt_at_hot_cell_temp": min_modules_mppt_hot,
        "max_modules_string_mppt_screening": max_modules_mppt_cold,
        "string_voltage_check": "PASS" if cold_string_v <= inverter_max_dc_v and inverter_mppt_min_v <= hot_string_v <= inverter_mppt_max_v else "REVIEW",
        "string_current_a_at_stc": round(module_isc_a * strings_per_inverter, 2),
        "annual_energy_mwh_estimate": round(annual_mwh, 1),
        "specific_yield_kwh_kwp_input": specific_yield_kwh_kwp,
        "performance_ratio_input": performance_ratio,
        "calculation_note": "Screening estimate; confirm module/inverter datasheets, bifacial gain, clipping, shading, mismatch, soiling, temperature and site-specific yield model."
    }


def bess_design(*, target_power_mw: float, delivered_energy_mwh: float, duration_hours: float,
                usable_dod_pct: float, end_of_life_soh_pct: float, discharge_efficiency_pct: float,
                container_energy_mwh: float, container_power_mw: float, annual_cycles: float,
                round_trip_efficiency_pct: float) -> dict[str, Any]:
    for n, v in [("target_power_mw", target_power_mw), ("delivered_energy_mwh", delivered_energy_mwh),
                 ("duration_hours", duration_hours), ("container_energy_mwh", container_energy_mwh),
                 ("container_power_mw", container_power_mw)]:
        _positive(n, v)
    for n, v in [("usable_dod_pct", usable_dod_pct), ("end_of_life_soh_pct", end_of_life_soh_pct),
                 ("discharge_efficiency_pct", discharge_efficiency_pct), ("round_trip_efficiency_pct", round_trip_efficiency_pct)]:
        if not 0 < v <= 100:
            raise ValueError(f"{n} must be between 0 and 100")
    if annual_cycles < 0:
        raise ValueError("annual_cycles cannot be negative")
    usable = usable_dod_pct / 100
    eol = end_of_life_soh_pct / 100
    eta_dis = discharge_efficiency_pct / 100
    rte = round_trip_efficiency_pct / 100
    energy_for_duration = target_power_mw * duration_hours
    requested_delivery = max(delivered_energy_mwh, energy_for_duration)
    required_dc_nameplate = requested_delivery / (usable * eol * eta_dis)
    energy_containers = math.ceil(required_dc_nameplate / container_energy_mwh)
    power_containers = math.ceil(target_power_mw / container_power_mw)
    containers = max(energy_containers, power_containers)
    installed_mwh = containers * container_energy_mwh
    installed_mw = containers * container_power_mw
    throughput_mwh_year = requested_delivery * annual_cycles
    charge_energy_mwh_year = throughput_mwh_year / rte
    return {
        "target_power_mw": round(target_power_mw, 3), "duration_hours": round(duration_hours, 2),
        "energy_from_power_duration_mwh": round(energy_for_duration, 3),
        "requested_delivered_energy_mwh": round(requested_delivery, 3),
        "required_nameplate_energy_mwh_screening": round(required_dc_nameplate, 3),
        "container_energy_mwh": container_energy_mwh, "container_power_mw": container_power_mw,
        "containers_for_energy": energy_containers, "containers_for_power": power_containers,
        "container_count_screening": containers, "installed_energy_mwh": round(installed_mwh, 3),
        "installed_power_mw": round(installed_mw, 3),
        "installed_duration_hours_at_target_power": round(installed_mwh * usable * eol * eta_dis / target_power_mw, 2),
        "estimated_c_rate_at_target_power": round(target_power_mw / installed_mwh, 3),
        "annual_discharge_throughput_mwh_screening": round(throughput_mwh_year, 1),
        "annual_charge_energy_mwh_screening": round(charge_energy_mwh_year, 1),
        "round_trip_efficiency_pct_input": round_trip_efficiency_pct,
        "calculation_note": "Confirm AC/DC energy boundary, auxiliary consumption, temperature derating, warranty throughput, degradation curve, augmentation plan, SOC window and vendor guarantees."
    }


def cable_voltage_drop(*, current_a: float, one_way_length_m: float, conductor_area_mm2: float,
                       system_voltage_v: float, conductor_resistivity_ohm_mm2_m: float = 0.0225,
                       phases: int = 2) -> dict[str, Any]:
    for n, v in [("current_a", current_a), ("one_way_length_m", one_way_length_m),
                 ("conductor_area_mm2", conductor_area_mm2), ("system_voltage_v", system_voltage_v),
                 ("conductor_resistivity_ohm_mm2_m", conductor_resistivity_ohm_mm2_m)]:
        _positive(n, v)
    if phases not in (2, 3):
        raise ValueError("phases must be 2 (DC/single-phase loop) or 3 (three-phase AC)")
    resistance = conductor_resistivity_ohm_mm2_m * one_way_length_m / conductor_area_mm2
    drop_v = (2 if phases == 2 else math.sqrt(3)) * current_a * resistance
    drop_pct = drop_v / system_voltage_v * 100
    loss_w = (2 if phases == 2 else 3) * current_a**2 * resistance
    return {"current_a": current_a, "one_way_length_m": one_way_length_m, "conductor_area_mm2": conductor_area_mm2,
            "loop_or_line_drop_v": round(drop_v, 3), "voltage_drop_pct": round(drop_pct, 3),
            "conductor_loss_w_approx": round(loss_w, 1),
            "screening_status": "REVIEW" if drop_pct > 2 else "WITHIN_2_PERCENT_SCREEN"}


def transformer_export_check(*, pv_ac_mw: float, bess_discharge_mw: float, export_limit_mw: float,
                             transformer_mva_each: float, transformer_count: int, minimum_power_factor: float = 0.95) -> dict[str, Any]:
    for n, v in [("pv_ac_mw", pv_ac_mw), ("bess_discharge_mw", bess_discharge_mw)]:
        if not math.isfinite(float(v)) or float(v) < 0:
            raise ValueError(f"{n} must be a finite value greater than or equal to zero")
    for n, v in [("export_limit_mw", export_limit_mw), ("transformer_mva_each", transformer_mva_each),
                 ("minimum_power_factor", minimum_power_factor)]:
        _positive(n, v)
    if transformer_count < 1 or minimum_power_factor > 1:
        raise ValueError("transformer_count must be >= 1 and power factor <= 1")
    unconstrained = pv_ac_mw + bess_discharge_mw
    export_mw = min(unconstrained, export_limit_mw)
    apparent_mva = export_mw / minimum_power_factor
    installed_mva = transformer_mva_each * transformer_count
    n_minus_one_mva = transformer_mva_each * (transformer_count - 1) if transformer_count > 1 else 0
    return {"uncontrolled_simultaneous_generation_mw": round(unconstrained, 3), "export_limit_mw": export_limit_mw,
            "export_after_assumed_plant_controller_mw": round(export_mw, 3), "apparent_power_at_minimum_pf_mva": round(apparent_mva, 3),
            "installed_transformer_capacity_mva": round(installed_mva, 3),
            "normal_loading_pct": round(apparent_mva / installed_mva * 100, 1),
            "n_minus_one_capacity_mva": round(n_minus_one_mva, 3) if transformer_count > 1 else None,
            "n_minus_one_loading_pct": round(apparent_mva / n_minus_one_mva * 100, 1) if transformer_count > 1 else None,
            "simultaneous_export_requires_controller_limit": unconstrained > export_limit_mw,
            "note": "Verify grid-code reactive capability, transformer impedance/losses, temperature/altitude derating, fault level and protection coordination. N-1 is not available for a single transformer."}
