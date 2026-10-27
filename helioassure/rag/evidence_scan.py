"""Missing-Evidence / negative-evidence scanner (deterministic heuristic). Flags sentences that say something is absent, pending or not done."""
from __future__ import annotations
import re

NEG = re.compile(r"(not (?:yet )?(?:been )?(?:commissioned|available|included|defined|submitted|completed|received|secured|supported|performed|issued|uploaded|exercised)|"
                 r"no (?:[\w\-/ ]{0,40})(?:has been|have been|study|assessment|certificate|conformity|pentest|plan|pilot|test|security|lease|easement)|"
                 r"\bpending\b|\bmissing\b|to be confirmed|not applicable|not yet|none provided|unrated|excluded?|without|not in scope|under review|in review|in progress|planned q\d)", re.I)


def sentences(text: str):
    for s in re.split(r"(?<=[\.\n\|])\s+", text):
        s = " ".join(s.split())
        if 25 <= len(s) <= 400:
            yield s


def scan(chunks, max_items: int = 6):
    """chunks: iterable of Chunk. Returns list of dicts {source, locator, quote, phrase}."""
    out, seen = [], set()
    for c in chunks:
        for s in sentences(c.text):
            m = NEG.search(s)
            if m and (c.source, s[:60]) not in seen:
                seen.add((c.source, s[:60]))
                out.append({"source": c.source, "locator": c.locator, "quote": s[:200], "phrase": m.group(0)})
                if len(out) >= max_items:
                    return out
    return out
