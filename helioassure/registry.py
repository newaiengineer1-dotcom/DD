"""Agent registry, Agent Router and Dependency Manager (workflow ordering)."""
from __future__ import annotations
from functools import lru_cache

import yaml

from helioassure.config import CONFIG_DIR


@lru_cache(maxsize=1)
def load():
    ag = yaml.safe_load((CONFIG_DIR / "agents.yaml").read_text(encoding="utf-8"))
    ws = yaml.safe_load((CONFIG_DIR / "workstreams.yaml").read_text(encoding="utf-8"))["workstreams"]
    return ag, ws


def disciplines() -> dict:
    return load()[0]["disciplines"]


def workstreams() -> dict:
    return load()[1]


def active_disciplines(flags: dict) -> dict:
    """Core agents always; optional specialists only when the matching ProjectInput flag is true."""
    ag = load()[0]
    out = {k: dict(v, optional=False) for k, v in ag["disciplines"].items()}
    for k, v in ag["optional_specialists"].items():
        if flags.get(v["when"]):
            out[k] = dict(v, optional=True)
    return out


def route(text: str, flags: dict | None = None) -> str:
    """Agent Router: pick the agent whose keywords best match the topic (used for OIR routing and exceptions)."""
    t, best, score = text.lower(), "project_director", 0
    for k, v in active_disciplines(flags or {}).items():
        s = sum(1 for kw in v.get("keywords", []) if str(kw).lower() in t)
        if s > score:
            best, score = k, s
    return best


def toposort(graph: dict[str, list[str]]) -> list[str]:
    """Dependency Manager: Kahn's algorithm with explicit cycle detection."""
    indeg = {n: 0 for n in graph}
    for n, deps in graph.items():
        for d in deps:
            if d not in graph:
                raise KeyError(f"unknown dependency {d} for {n}")
            indeg[n] += 1
    ready = sorted(n for n, d in indeg.items() if d == 0)
    order = []
    while ready:
        n = ready.pop(0); order.append(n)
        for m, deps in graph.items():
            if n in deps:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m); ready.sort()
    if len(order) != len(graph):
        raise ValueError("dependency cycle detected among: " + ", ".join(sorted(set(graph) - set(order))))
    return order


def workstream_order() -> list[str]:
    return toposort({k: v["depends_on"] for k, v in workstreams().items()})
