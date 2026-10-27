"""
Contradiction Detection Agent (deterministic): extracts the SAME physical quantity from every document and flags disagreement.
Extractors are regex-based on purpose (auditable). Add one per quantity you care about.
"""
from __future__ import annotations
import re

from helioassure.qa import QAResult

_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def _ctx(text: str, m, w: int = 90) -> str:
    return " ".join(text[max(0, m.start() - w): m.end() + w].split())


def ex_dc_kwp(text):
    for m in re.finditer(_NUM + r"\s*(kWp|MWp)\b", text):
        v = _f(m.group(1)) * (1000 if m.group(2) == "MWp" else 1)
        if v >= 20_000:
            yield v, _ctx(text, m)


def ex_degradation(text):
    for m in re.finditer(r"(\d\.\d{1,2})\s*%\s*(?:/|per\s)\s*(?:yr|year)", text):
        if re.search(r"degrad|performance|linear", text[max(0, m.start() - 140): m.start() + 40], re.I):
            yield float(m.group(1)), _ctx(text, m)
    for m in re.finditer(r"degradation[^|\n]{0,30}\|\s*(\d\.\d{1,2})\s*\|", text, re.I):
        yield float(m.group(1)), _ctx(text, m)


def ex_cycles(text):
    for m in re.finditer(r"(\d\.\d+)\s*(?:equivalent full )?cycles?\s*(?:/|per)\s*day", text, re.I):
        yield float(m.group(1)), _ctx(text, m)
    for m in re.finditer(r"cycles per day\s*\|\s*(\d\.\d+)", text, re.I):
        yield float(m.group(1)), _ctx(text, m)


def ex_export(text):
    for m in re.finditer(r"(?:export limit|access capacity)[^\d\n\.]{0,30}(\d{2,3})\s*MW\b", text, re.I):
        yield float(m.group(1)), _ctx(text, m)


def ex_usable_mwh(text):
    for m in re.finditer(r"(\d{2,3}(?:\.\d+)?)\s*MWh\s*usable|usable[^\d\n]{0,40}(\d{2,3}(?:\.\d+)?)\s*MWh", text, re.I):
        yield float(m.group(1) or m.group(2)), _ctx(text, m)


QUANTITIES = {   # name: (extractor, relative tolerance, severity if mismatch, label)
    "PV DC capacity (kWp)": (ex_dc_kwp, 0.003, "fail", "WS3"),
    "Annual module degradation (%/yr)": (ex_degradation, 0.02, "fail", "WS2"),
    "BESS cycles per day": (ex_cycles, 0.02, "warn", "WS7"),
    "Export limit (MW)": (ex_export, 0.001, "fail", "WS4"),
    "BESS usable energy (MWh)": (ex_usable_mwh, 0.005, "fail", "WS7"),
}


def detect(index) -> tuple[list[QAResult], list[dict]]:
    results, detail = [], []
    for name, (fn, tol, sev, ws) in QUANTITIES.items():
        obs = []
        for c in index.chunks:
            for v, ctx in fn(c.text):
                obs.append({"value": v, "source": c.source, "locator": c.locator, "quote": ctx})
        if not obs:
            continue
        vals = sorted({round(o["value"], 4) for o in obs})
        lo, hi = vals[0], vals[-1]
        spread = (hi - lo) / hi if hi else 0
        # group by source so one document repeating a number is not 'disagreement'
        srcs = {}
        for o in obs:
            srcs.setdefault(o["source"], set()).add(round(o["value"], 4))
        status = "pass" if spread <= tol else sev
        detail.append({"quantity": name, "values": vals, "spread_pct": round(spread * 100, 3), "status": status, "observations": obs[:12], "workstream": ws})
        results.append(QAResult(f"CONTRA-{len(results)+1:02d}", "contradiction_detection", status,
                                f"{name}: values {vals} across {len(srcs)} documents (spread {spread*100:.2f}%)" if status != "pass" else f"{name}: consistent ({vals[0]})", ws,
                                sorted(srcs)))
    return results, detail
