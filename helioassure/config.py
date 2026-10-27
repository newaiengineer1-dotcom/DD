"""Central configuration. Everything overridable by env vars / Streamlit secrets."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_ROOM = Path(os.getenv("DATA_ROOM_DIR", ROOT / "data_room" / "Solara_Alentejo_DataRoom"))
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", ROOT / "knowledge"))
INDEX_DIR = Path(os.getenv("INDEX_DIR", ROOT / ".index"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "outputs"))
DB_PATH = Path(os.getenv("HELIOASSURE_DB", OUTPUT_DIR / "project_state.db"))

# LLM provider adapter (LiteLLM-style model strings used by CrewAI). Groq is the default provider.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")                 # groq | openai | anthropic | ollama
GROQ_MODELS = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]  # verify at console.groq.com/docs/models
DEFAULT_MODEL = os.getenv("LLM_MODEL", GROQ_MODELS[0])

MAX_TOOL_CHARS = int(os.getenv("MAX_TOOL_CHARS", "3500"))
CHUNK_CHARS, CHUNK_OVERLAP = 1100, 150
EVIDENCE_MIN_SCORE = float(os.getenv("EVIDENCE_MIN_SCORE", "3.5"))   # below this a query counts as 'no evidence'
