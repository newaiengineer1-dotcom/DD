"""
Shared Project State ("blackboard"). Agents never chat with each other: they read/write typed items here.
SQLite (stdlib) -> zero-ops locally and on Streamlit Cloud; the same schema ports to PostgreSQL.
Every mutation is appended to a hash-chained audit log (tamper-evident).
"""
from __future__ import annotations
import hashlib, json, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

KINDS = ("task", "output", "finding", "assumption", "oir", "calc", "qa", "exception", "artifact", "document")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Blackboard:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.RLock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS items(kind TEXT, id TEXT, workstream TEXT, agent TEXT, status TEXT, data TEXT, created TEXT, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS approvals(doc_id TEXT, gate TEXT, actor TEXT, decision TEXT, comment TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, payload TEXT, prev TEXT, hash TEXT);
        """)

    # ------------------------------------------------------------ state
    def put(self, key: str, value: Any, actor: str = "system"):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (key, json.dumps(value, default=str), _now()))
            self.db.commit()
        self.audit(actor, "state.put", {"key": key})

    def get(self, key: str, default=None):
        r = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def keys(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT key FROM state ORDER BY key")]

    # ------------------------------------------------------------ items
    def add(self, kind: str, id_: str, data: dict, workstream: str = "", agent: str = "", status: str = "draft", actor: str = "system"):
        assert kind in KINDS, kind
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO items VALUES(?,?,?,?,?,?,?)", (kind, id_, workstream, agent, status, json.dumps(data, default=str), _now()))
            self.db.commit()
        self.audit(actor or agent, f"{kind}.add", {"id": id_, "status": status})

    def items(self, kind: str, workstream: str | None = None, agent: str | None = None, status: str | None = None) -> list[dict]:
        q, a = "SELECT id,workstream,agent,status,data,created FROM items WHERE kind=?", [kind]
        for col, v in (("workstream", workstream), ("agent", agent), ("status", status)):
            if v:
                q += f" AND {col}=?"; a.append(v)
        out = []
        for id_, ws, ag, st, data, cr in self.db.execute(q + " ORDER BY created, id", a):
            d = json.loads(data); d.update({"_id": id_, "_workstream": ws, "_agent": ag, "_status": st, "_created": cr}); out.append(d)
        return out

    def set_status(self, kind: str, id_: str, status: str, actor: str = "system"):
        with self.lock:
            self.db.execute("UPDATE items SET status=? WHERE kind=? AND id=?", (status, kind, id_)); self.db.commit()
        self.audit(actor, f"{kind}.status", {"id": id_, "status": status})

    def clear(self, kinds: Iterable[str]):
        with self.lock:
            for k in kinds:
                self.db.execute("DELETE FROM items WHERE kind=?", (k,))
            self.db.commit()

    # ------------------------------------------------------------ approvals
    def approve(self, doc_id: str, gate: str, actor: str, decision: str, comment: str = ""):
        with self.lock:
            self.db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?)", (doc_id, gate, actor, decision, comment, _now())); self.db.commit()
        self.audit(actor, "approval", {"doc": doc_id, "gate": gate, "decision": decision})

    def approvals(self, doc_id: str | None = None) -> list[dict]:
        q = "SELECT doc_id,gate,actor,decision,comment,ts FROM approvals" + (" WHERE doc_id=?" if doc_id else "") + " ORDER BY ts"
        rows = self.db.execute(q, [doc_id] if doc_id else []).fetchall()
        return [dict(zip(("doc_id", "gate", "actor", "decision", "comment", "ts"), r)) for r in rows]

    # ------------------------------------------------------------ audit trail
    def audit(self, actor: str, action: str, payload: dict | None = None):
        with self.lock:
            prev = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            prev = prev[0] if prev else "GENESIS"
            ts, pl = _now(), json.dumps(payload or {}, sort_keys=True, default=str)
            h = hashlib.sha256(f"{prev}|{ts}|{actor}|{action}|{pl}".encode()).hexdigest()
            self.db.execute("INSERT INTO audit(ts,actor,action,payload,prev,hash) VALUES(?,?,?,?,?,?)", (ts, actor, action, pl, prev, h)); self.db.commit()

    def audit_log(self, limit: int = 500) -> list[dict]:
        rows = self.db.execute("SELECT seq,ts,actor,action,payload,hash FROM audit ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [dict(zip(("seq", "ts", "actor", "action", "payload", "hash"), r)) for r in rows]

    def verify_audit_chain(self) -> bool:
        prev = "GENESIS"
        for ts, actor, action, pl, p, h in self.db.execute("SELECT ts,actor,action,payload,prev,hash FROM audit ORDER BY seq"):
            if p != prev or hashlib.sha256(f"{prev}|{ts}|{actor}|{action}|{pl}".encode()).hexdigest() != h:
                return False
            prev = h
        return True
