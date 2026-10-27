#!/usr/bin/env python3
"""CLI: python run_platform.py [--project examples/project_solara.json] [--data-room DIR] [--llm --model llama-3.3-70b-versatile] [--only-docs D49 D50]"""
import argparse, json, shutil, sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from helioassure.blackboard import Blackboard
from helioassure.config import DATA_ROOM, DEFAULT_MODEL, OUTPUT_DIR
from helioassure.orchestrator import MasterOrchestrator
from helioassure.project import ProjectInput


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="examples/project_solara.json")
    ap.add_argument("--data-room", default=str(DATA_ROOM))
    ap.add_argument("--llm", action="store_true", help="enable CrewAI/Groq interpretation (needs GROQ_API_KEY)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--db", default=str(OUTPUT_DIR / "project_state.db"))
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    if a.reset and Path(a.db).exists():
        Path(a.db).unlink()
    bb = Blackboard(a.db)
    proj = ProjectInput.from_dict(json.loads(Path(a.project).read_text()))
    llm = None
    if a.llm:
        from helioassure.llm import make_llm
        llm = make_llm(a.model)
    orch = MasterOrchestrator(bb, proj, Path(a.data_room), llm=llm, use_llm=a.llm, on_event=lambda e: print(e), reindex=True)
    qa = orch.run_all()
    fs = [f for f in bb.items("finding") if f["_status"] != "duplicate"]
    print(f"\nQA: {qa}\nFindings: {len(fs)} | OIRs: {len(bb.items('oir'))} | Documents: {len(bb.items('document'))} -> {OUTPUT_DIR/'deliverables'}")
    print("Audit chain intact:", bb.verify_audit_chain())


if __name__ == "__main__":
    sys.exit(main())
