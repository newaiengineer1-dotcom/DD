"""Evidence Validation Agent: every citation must point at a real file and (if a quote is given) the quote must exist in it."""
from __future__ import annotations
import re

from helioassure.qa import QAResult
from helioassure.rag.ingest import inventory


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%\.]+", " ", s.lower()).strip()


def validate_findings(findings: list[dict], index, root, calc_ids=()) -> list[QAResult]:
    files = {r["path"].lower(): r["path"] for r in inventory(root)}
    by_src: dict[str, str] = {}
    for c in index.chunks:
        by_src[c.source] = by_src.get(c.source, "") + " " + _norm(c.text)
    res = []
    for f in findings:
        cites = f.get("citations", [])
        if not cites:
            res.append(QAResult(f"EV-{f['id']}", "evidence_validation", "pass" if f.get("gap") else "fail", "gap finding without citation (acceptable)" if f.get("gap") else "no citation", f.get("workstream", "ALL")))
            continue
        problems = []
        for c in cites:
            src = c["source"] if isinstance(c, dict) else c
            if src.startswith("calc:"):
                if src[5:] not in calc_ids:
                    problems.append(f"unknown calculation {src}")
                continue
            hit = next((orig for low, orig in files.items() if low == src.lower() or low.endswith("/" + src.lower().split("/")[-1])), None)
            if not hit:
                problems.append(f"file not in data room: {src}"); continue
            q = (c.get("quote", "") if isinstance(c, dict) else "").strip()
            if q and _norm(q) not in by_src.get(hit, ""):
                problems.append(f"quote not found in {hit}")
        res.append(QAResult(f"EV-{f['id']}", "evidence_validation", "fail" if problems else "pass", "; ".join(problems) or "citations verified", f.get("workstream", "ALL"), [str(c) for c in cites]))
    return res
