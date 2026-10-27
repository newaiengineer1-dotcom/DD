"""Human-in-the-loop approval gates. Agents can never issue a document; only a complete, ordered chain of human approvals + QA can."""
from __future__ import annotations

GATES = ["engineering_review", "lead_approval", "director_approval"]
EXTRA = {"lender": ["lender_engineer"], "qa": ["qa_manager"], "owner": ["owners_engineer"]}
ROLES = {"engineering_review": "Engineering Reviewer", "lead_approval": "Lead Engineer", "director_approval": "Project Director",
         "owners_engineer": "Owner's Engineer", "lender_engineer": "Lender Engineer", "qa_manager": "QA Manager"}
STATES = ["DRAFT", "UNDER_REVIEW", "LEAD_APPROVED", "DIRECTOR_APPROVED", "ISSUED", "REJECTED"]


def required_gates(classes: list[str] | None = None) -> list[str]:
    g = list(GATES)
    for c in classes or []:
        g += EXTRA.get(c, [])
    return g


def gate_status(bb, doc_id: str, classes=None) -> dict:
    """Latest decision per gate (a later 'approve' after a 'reject' supersedes it)."""
    latest = {}
    for a in bb.approvals(doc_id):
        latest[a["gate"]] = a
    return {g: latest.get(g) for g in required_gates(classes)}


def doc_state(bb, doc_id: str, classes=None) -> str:
    st = gate_status(bb, doc_id, classes)
    if any(v and v["decision"] == "reject" for v in st.values()):
        return "REJECTED"
    n = sum(1 for v in st.values() if v and v["decision"] == "approve")
    if n == 0: return "DRAFT"
    if n < len(st):
        return ["UNDER_REVIEW", "LEAD_APPROVED"][min(n - 1, 1)] if n < len(GATES) else "DIRECTOR_APPROVED"
    return "DIRECTOR_APPROVED"


def submit(bb, doc_id: str, gate: str, actor: str, decision: str, comment: str = "", classes=None):
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be approve|reject")
    gates = required_gates(classes)
    if gate not in gates:
        raise ValueError(f"gate {gate} not required for this document")
    if decision == "approve":
        st = gate_status(bb, doc_id, classes)
        for g in gates[:gates.index(gate)]:
            if g in GATES and not (st[g] and st[g]["decision"] == "approve"):
                raise PermissionError(f"gate '{g}' must be approved before '{gate}'")
    if decision == "reject" and not comment.strip():
        raise ValueError("a rejection requires a comment")
    bb.approve(doc_id, gate, actor, decision, comment)


def can_issue(bb, doc_id: str, qa_ok: bool, classes=None) -> tuple[bool, list[str]]:
    reasons = []
    st = gate_status(bb, doc_id, classes)
    for g, v in st.items():
        if not v or v["decision"] != "approve":
            reasons.append(f"gate '{g}' ({ROLES[g]}) not approved")
    if not qa_ok:
        reasons.append("QA verification not passed for this document's workstream")
    return not reasons, reasons


def issue(bb, doc_id: str, qa_ok: bool, classes=None, actor="system"):
    ok, reasons = can_issue(bb, doc_id, qa_ok, classes)
    if not ok:
        raise PermissionError("cannot issue: " + "; ".join(reasons))
    bb.set_status("document", doc_id, "issued", actor)
