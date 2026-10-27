"""Run all tests without pytest:  python tests/run.py"""
import importlib, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
m = importlib.import_module("tests.test_platform"); ok = bad = 0
for n, f in vars(m).items():
    if n.startswith("test_"):
        try: f(); ok += 1; print("PASS", n)
        except Exception: bad += 1; print("FAIL", n); traceback.print_exc()
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
