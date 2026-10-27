"""
Typed, validated contracts exchanged between agents (Task Assignment Contract, Agent Output Contract).
Stdlib dataclasses + strict validators: no framework dependency, so contracts are testable anywhere.
The LLM boundary uses AgentOutput.from_dict(), which raises ContractError on any schema violation;
the orchestrator then retries once and finally records an Exception item instead of accepting free text.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")
STATUSES = ("complete", "blocked", "failed")


class ContractError(ValueError):
    pass


def _req(d: dict, key: str, typ):
    if key not in d:
        raise ContractError(f"missing field '{key}'")
    if not isinstance(d[key], typ):
        raise ContractError(f"field '{key}' must be {typ.__name__}, got {type(d[key]).__name__}")
    return d[key]


@dataclass
class Citation:
    source: str                  # data-room path or standard id
    locator: str = ""            # page / sheet / clause
    quote: str = ""              # verbatim snippet (<= 200 chars) used by the Evidence Validation Agent

    @classmethod
    def from_any(cls, x) -> "Citation":
        if isinstance(x, Citation):
            return x
        if isinstance(x, str):
            src, _, loc = x.strip("[] ").partition("|")
            return cls(src.strip(), loc.strip())
        if isinstance(x, dict):
            return cls(str(_req(x, "source", str)), str(x.get("locator", "")), str(x.get("quote", ""))[:200])
        raise ContractError("citation must be str or object")


@dataclass
class Finding:
    id: str
    agent: str
    workstream: str
    severity: str
    category: str
    statement: str
    citations: list = field(default_factory=list)
    impact: str = ""
    recommendation: str = ""
    condition_precedent: bool = False
    gap: bool = False
    confidence: str = "medium"       # low = heuristic/needs human confirmation
    status: str = "draft"            # draft | qa_pass | qa_fail | accepted | rejected

    def validate(self):
        if self.severity not in SEVERITIES:
            raise ContractError(f"bad severity {self.severity}")
        if not self.statement.strip():
            raise ContractError("empty finding statement")
        if not self.gap and not self.citations:
            raise ContractError(f"finding {self.id} has no citation and is not a gap")
        return self


@dataclass
class Assumption:
    id: str
    agent: str
    text: str
    basis: str = ""
    status: str = "assumed"          # assumed | confirmed | rejected


@dataclass
class OIR:
    """Outstanding Information Request."""
    id: str
    agent: str
    question: str
    reason: str = ""
    priority: str = "Medium"
    routed_to: str = ""
    status: str = "open"


@dataclass
class CalcRecord:
    id: str
    tool: str
    inputs: dict
    outputs: dict
    agent: str = "tool"


@dataclass
class TaskAssignment:
    task_id: str
    agent_id: str
    workstream: str
    objective: str
    inputs: dict = field(default_factory=dict)
    evidence_queries: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    depends_on: list = field(default_factory=list)
    acceptance_criteria: list = field(default_factory=list)
    deliverables: list = field(default_factory=list)
    approval_required: bool = True

    def to_dict(self):
        return asdict(self)


@dataclass
class AgentOutput:
    task_id: str
    agent_id: str
    status: str
    summary: str
    findings: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    oirs: list = field(default_factory=list)
    calc_requests: list = field(default_factory=list)
    evidence_used: list = field(default_factory=list)
    qa_required: bool = True

    @classmethod
    def from_dict(cls, d: dict, task: TaskAssignment) -> "AgentOutput":
        if not isinstance(d, dict):
            raise ContractError("output must be an object")
        status = d.get("status", "complete")
        if status not in STATUSES:
            raise ContractError(f"bad status {status}")
        out = cls(task.task_id, task.agent_id, status, str(_req(d, "summary", str)))
        for i, f in enumerate(d.get("findings", []) or [], 1):
            if not isinstance(f, dict):
                raise ContractError("finding must be object")
            fid = f"{task.agent_id[:6].upper()}-{task.task_id[-3:]}-{i:02d}"
            fnd = Finding(fid, task.agent_id, task.workstream, str(f.get("severity", "Medium")).title(), str(f.get("category", task.agent_id)),
                          str(f.get("statement") or f.get("finding") or ""), [Citation.from_any(c) for c in (f.get("citations") or f.get("evidence") or [])],
                          str(f.get("impact", "")), str(f.get("recommendation", "")), bool(f.get("condition_precedent", False)), bool(f.get("gap", False)),
                          str(f.get("confidence", "medium")))
            out.findings.append(fnd.validate())
        for i, a in enumerate(d.get("assumptions", []) or [], 1):
            out.assumptions.append(Assumption(f"AS-{task.task_id[-3:]}-{i:02d}", task.agent_id, str(a if isinstance(a, str) else a.get("text", "")), "" if isinstance(a, str) else str(a.get("basis", ""))))
        for i, o in enumerate(d.get("oirs", []) or [], 1):
            q = o if isinstance(o, str) else o.get("question", "")
            out.oirs.append(OIR(f"OIR-{task.task_id[-3:]}-{i:02d}", task.agent_id, str(q), "" if isinstance(o, str) else str(o.get("reason", "")), "Medium" if isinstance(o, str) else str(o.get("priority", "Medium"))))
        out.calc_requests = list(d.get("calc_requests", []) or [])
        out.evidence_used = [Citation.from_any(c) for c in (d.get("evidence_used", []) or [])]
        return out
