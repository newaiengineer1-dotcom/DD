"""Provider adapter: Groq by default, any LiteLLM-supported provider via env. Rate-limit aware execution helper."""
from __future__ import annotations
import os, re, time

from helioassure.config import DEFAULT_MODEL, LLM_PROVIDER

PREFIX = {"groq": "groq/", "openai": "openai/", "anthropic": "anthropic/", "ollama": "ollama/"}
KEYS = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "ollama": ""}


def make_llm(model: str | None = None, api_key: str | None = None, provider: str | None = None, temperature: float = 0.1, max_tokens: int = 2200):
    from crewai import LLM
    prov = provider or LLM_PROVIDER
    key = api_key or (os.getenv(KEYS[prov]) if KEYS[prov] else None)
    if KEYS[prov] and not key:
        raise RuntimeError(f"{KEYS[prov]} is not set (Streamlit secrets, .env or sidebar).")
    kw = {"api_key": key} if key else {}
    return LLM(model=f"{PREFIX[prov]}{model or DEFAULT_MODEL}", temperature=temperature, max_tokens=max_tokens, **kw)


_RL = re.compile(r"(rate.?limit|429|tokens per minute|TPM|too many requests|overloaded|503)", re.I)
_WAIT = re.compile(r"try again in\s+((?:\d+m)?\s*[\d\.]+\s*(?:ms|s))", re.I)


def _wait_seconds(msg: str, attempt: int) -> float:
    m = _WAIT.search(msg)
    if not m:
        return min(90.0, 8 * 2 ** attempt)
    t, total = m.group(1).replace(" ", ""), 0.0
    mm, ss = re.search(r"(\d+)m(?!s)", t), re.search(r"([\d\.]+)(ms|s)\b", t)
    if mm: total += 60 * int(mm.group(1))
    if ss: total += float(ss.group(1)) / (1000 if ss.group(2) == "ms" else 1)
    return min(90.0, total + 2)


def with_retries(fn, retries: int = 5, on_wait=None):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:      # noqa: BLE001 - provider exceptions vary by litellm version
            if not _RL.search(str(e)) or attempt == retries:
                raise
            w = _wait_seconds(str(e), attempt)
            if on_wait: on_wait(w, attempt + 1)
            time.sleep(w)
