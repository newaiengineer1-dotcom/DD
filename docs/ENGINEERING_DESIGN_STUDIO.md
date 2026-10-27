# Engineering Design Studio

Added 27 October 2026. The Streamlit workspace is exposed as the final `11 Engineering Design` tab in `app.py`; deterministic functions live in `helioassure/tools/design_studio.py`.

## Included calculations

1. **PV array and yield:** rounds the requested module count up to complete strings; estimates DC nameplate, inverter count from target DC/AC ratio, cold-corrected module Voc, hot-corrected Vmp, voltage-window screening, and annual energy from user-supplied specific yield and PR.
2. **BESS sizing:** calculates nameplate energy required for delivered energy, usable DoD, end-of-life state of health and discharge-path efficiency; separately sizes power and energy container counts; reports installed energy/power, duration and throughput screening.
3. **Cable drop:** approximate resistive voltage drop and conductor losses for a two-conductor DC/single-phase loop or balanced three-phase circuit.
4. **Transformer and export:** screens simultaneous PV+BESS output against export limit and calculates apparent-power loading at the user-specified minimum power factor.
5. **Calculation register:** CSV and JSON export of completed results in the current session.

## Engineering caveats

- This is a preliminary sizing and review aid, not a certified design tool or substitute for PVsyst/validated energy modelling, manufacturer sizing tools, or project-specific engineering.
- Confirm module temperature coefficients, absolute maximum voltage, MPPT window, current limits, string fuse limits, bifacial current, and site minimum design temperature from the actual datasheets and applicable standards.
- Yield estimates depend on the definition of specific yield. If the input is already a net P50 yield, do not apply a second performance-ratio loss factor; adjust the inputs so the convention is consistent.
- BESS energy boundary (cell, DC bus, PCS AC terminals, or point of interconnection), auxiliary loads, thermal derating, SOC window, warranty throughput, degradation and augmentation must be confirmed with the supplier.
- Cable checks do not perform ampacity derating, short-circuit withstand, installation method, harmonic, impedance, touch/step voltage, or protection coordination studies.
- Transformer checks do not perform load flow, fault level, dynamic response, harmonics, reactive power capability, or detailed N-1 contingency studies.
- Outputs require review by a qualified electrical / PV / BESS engineer before procurement, construction, or operation.
