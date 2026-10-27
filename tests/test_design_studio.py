import pytest
from helioassure.tools.design_studio import pv_design, bess_design, cable_voltage_drop, transformer_export_check


def test_pv_design_counts_full_strings_and_flags_voltage():
    r = pv_design(target_mwp=10, module_wp=580, inverter_kw=250,
        module_voc_v=52, module_vmp_v=44, module_isc_a=14,
        voc_temp_coeff_pct_c=-0.24, vmp_temp_coeff_pct_c=-0.29,
        min_ambient_c=-5, max_cell_c=70, inverter_max_dc_v=1500,
        inverter_mppt_min_v=500, inverter_mppt_max_v=1500,
        modules_per_string=26, strings_per_inverter=2,
        specific_yield_kwh_kwp=1800, performance_ratio=0.82, target_dc_ac_ratio=1.25)
    assert r['module_count'] == r['total_strings'] * 26
    assert r['actual_dc_mwp'] >= 10
    assert r['estimated_inverter_count'] >= 1
    assert r['annual_energy_mwh_estimate'] > 0


def test_bess_sizing_meets_power_and_energy():
    r = bess_design(target_power_mw=60, delivered_energy_mwh=240, duration_hours=4,
        usable_dod_pct=90, end_of_life_soh_pct=80, discharge_efficiency_pct=95,
        container_energy_mwh=5, container_power_mw=2.5, annual_cycles=300,
        round_trip_efficiency_pct=88)
    assert r['container_count_screening'] >= r['containers_for_energy']
    assert r['installed_power_mw'] >= 60
    assert r['installed_duration_hours_at_target_power'] >= 4


def test_cable_voltage_drop_is_positive():
    r = cable_voltage_drop(current_a=100, one_way_length_m=100, conductor_area_mm2=50,
        system_voltage_v=800, phases=2)
    assert r['voltage_drop_pct'] > 0
    assert r['conductor_loss_w_approx'] > 0


def test_transformer_export_limited():
    r = transformer_export_check(pv_ac_mw=120, bess_discharge_mw=60, export_limit_mw=130,
        transformer_mva_each=80, transformer_count=2, minimum_power_factor=0.95)
    assert r['export_after_assumed_plant_controller_mw'] == 130
    assert r['simultaneous_export_requires_controller_limit'] is True


def test_invalid_efficiency_rejected():
    with pytest.raises(ValueError):
        bess_design(target_power_mw=10, delivered_energy_mwh=20, duration_hours=2,
            usable_dod_pct=0, end_of_life_soh_pct=80, discharge_efficiency_pct=95,
            container_energy_mwh=5, container_power_mw=2.5, annual_cycles=300,
            round_trip_efficiency_pct=88)
