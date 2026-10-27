"""Calculation Validation Agent: independently re-executes every recorded deterministic calculation and compares key outputs."""
from __future__ import annotations
from helioassure.qa import QAResult
from helioassure.tools.registry import COMPARE, run_tool


def _same(a, b, tol=1e-6):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= tol * max(1, abs(a), abs(b))
    return a == b


def validate_calcs(calcs: list[dict]) -> list[QAResult]:
    res = []
    for c in calcs:
        try:
            again = run_tool(c["tool"], c["inputs"])
            diffs = [k for k in COMPARE.get(c["tool"], []) if not _same(c["outputs"].get(k), again.get(k))]
            res.append(QAResult(f"CALC-{c['id']}", "calculation_validation", "fail" if diffs else "pass", f"mismatch in {diffs}" if diffs else "re-run reproduces outputs", "ALL"))
        except Exception as e:                      # noqa: BLE001
            res.append(QAResult(f"CALC-{c['id']}", "calculation_validation", "fail", f"re-run failed: {e}", "ALL"))
    return res
