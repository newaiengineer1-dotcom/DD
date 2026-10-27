# HelioAssure UI Refresh Notes

**Release label:** 14 October 2026

## Scope
This release changes the presentation layer only. The application workflow, orchestrator, agent definitions, RAG pipeline, deterministic engineering tools, QA logic, approval gates, document generation, data room, examples, and test suite are retained.

## Visual changes
- Premium dark navy engineering workspace with champagne-gold and teal accents.
- Refined typography, spacing, tab styling, form controls, tables, alerts, metric cards, and sidebar.
- New responsive hero banner and improved brand treatment.
- Updated Streamlit theme configuration to match the UI palette.

## Validation performed in the available environment
- ZIP integrity check passed.
- Python compileall passed.
- Project's built-in deterministic test runner: 11 passed, 0 failed.
- Pytest: 11 passed.
- CLI deterministic end-to-end smoke run completed: 32 findings, 1 OIR, 61 documents generated in the temporary test run; audit chain verified intact.

## Validation limitation
The environment used to prepare this package did not have Streamlit installed and could not reach the Python package index, so a browser-rendered Streamlit AppTest and clean dependency installation could not be run here. This is not represented as a full live deployment test. Run `pip install -r requirements.txt` and `streamlit run app.py` in the target Python environment before production use.

## Engineering Design Studio update — 27 October 2026

Added a new `11 Engineering Design` tab with four work areas: PV Array & Yield, BESS Sizing, Cables & Grid, and Design Summary. The deterministic calculation functions are isolated in `helioassure/tools/design_studio.py`; five focused tests cover module/string rounding, BESS power-energy sizing, cable drop, export limiting and input validation. The pre-existing due-diligence workflow remains available. All new calculations are explicitly labelled preliminary screening and require vendor/site/code validation and qualified engineering review.
