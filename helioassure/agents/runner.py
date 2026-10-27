"""
LLM interpretation layer (CrewAI). One CrewAI Agent + Task + Crew per TaskAssignment.
The agent receives a pre-retrieved EVIDENCE PACK and deterministic TOOL RESULTS and must return JSON matching AgentOutput.
Output is validated by contracts.AgentOutput.from_dict(); invalid output is retried once, then escalated to the Exception Manager.
"""
from __future__ import annotations
import json, re

from helioassure import registry
from helioassure.contracts import AgentOutput, ContractError, TaskAssignment
from helioassure.llm import with_retries

SCHEMA = """Return ONLY one JSON object (no prose) with this shape:
{"status":"complete|blocked","summary":"<=120 words",
 "findings":[{"severity":"Critical|High|Medium|Low|Info","category":"..","statement":"one precise sentence with key numbers",
   "citations":[{"source":"<data room path>","locator":"<page/sheet>","quote":"<verbatim <=25 words>"}],
   "impact":"..","recommendation":"..","condition_precedent":false,"gap":false,"confidence":"low|medium|high"}],
 "assumptions":[{"text":"..","basis":".."}],"oirs":[{"question":"..","reason":"..","priority":"High|Medium|Low"}],
 "calc_requests":["<tool name + inputs needed>"]}
Use gap=true (no citation needed) only for documents/evidence that SHOULD exist but do not."""


def build_agent(agent_id: str, llm, verbose=False):
    from crewai import Agent
    ag, _ = registry.load()
    spec = {**ag["disciplines"], **ag["optional_specialists"]}.get(agent_id) or ag["leads"].get(agent_id)
    return Agent(role=spec["name"], goal=spec.get("role", spec["name"]), backstory=f"You are the {spec['name']} on a lender-grade solar PV + BESS engineering team.\n{ag['common_rules']}",
                 llm=llm, allow_delegation=False, verbose=verbose, max_iter=3, max_retry_limit=1, respect_context_window=True)


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ContractError("no JSON object in answer")
    raw = m.group(1)
    for cand in (raw, re.sub(r",\s*([\]}])", r"\1", raw)):
        try:
            return json.loads(cand)
        except Exception:
            continue
    raise ContractError("invalid JSON")


def run_llm_task(task: TaskAssignment, evidence_pack: str, tool_results: str, llm, notes: list[str] | None = None, on_wait=None, verbose=False) -> AgentOutput:
    from crewai import Crew, Process, Task
    agent = build_agent(task.agent_id, llm, verbose)
    desc = (f"OBJECTIVE: {task.objective}\nACCEPTANCE CRITERIA: " + "; ".join(task.acceptance_criteria) +
            f"\n\nPROJECT INPUTS (JSON): {json.dumps(task.inputs)[:1800]}\n\nTOOL RESULTS (deterministic, trusted):\n{tool_results[:2200]}\n\nEVIDENCE PACK (cite from this only):\n{evidence_pack[:5200]}\n" +
            ("\nHUMAN REVIEWER NOTES (binding):\n- " + "\n- ".join(notes) + "\n" if notes else "") + f"\n{SCHEMA}")
    last = None
    for attempt in range(2):
        t = Task(description=desc + (f"\nYour previous answer was rejected: {last}. Fix and resend JSON only." if last else ""), expected_output="JSON object", agent=agent)
        res = with_retries(lambda: Crew(agents=[agent], tasks=[t], process=Process.sequential, verbose=verbose, memory=False).kickoff(), on_wait=on_wait)
        try:
            return AgentOutput.from_dict(_extract_json(getattr(res, "raw", None) or str(res)), task)
        except ContractError as e:
            last = str(e)
    raise ContractError(f"agent output rejected twice: {last}")
