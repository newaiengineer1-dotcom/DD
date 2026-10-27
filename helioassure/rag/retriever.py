"""
Dependency-free BM25 retriever with persisted index and citation-ready results.
Why BM25 first: due-diligence queries are full of exact tokens (clause numbers, standards, MWp, dates)
where lexical search beats pure embeddings; it is deterministic, fast, offline, and easy to audit.
Hybrid/embedding upgrade path is described in the README.
"""
from __future__ import annotations
import json, math, re
from collections import Counter, defaultdict
from pathlib import Path

from helioassure.config import INDEX_DIR
from helioassure.rag.ingest import Chunk, iter_chunks

_TOKEN = re.compile(r"[a-z0-9][a-z0-9\.\-/%]*[a-z0-9%]|[a-z0-9]", re.I)
STOP = set("the a an and or of to in for on at by with is are was were be as from that this it its not no shall will may".split())


def tokenize(t: str) -> list[str]:
    return [w.lower().rstrip(".") for w in _TOKEN.findall(t) if w.lower() not in STOP]


class BM25Index:
    def __init__(self, k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.chunks: list[Chunk] = []
        self.tf: list[Counter] = []
        self.df: Counter = Counter()
        self.len: list[int] = []
        self.avg = 0.0
        self.inv: dict[str, list[int]] = defaultdict(list)

    def add(self, chunks):
        for c in chunks:
            toks = tokenize(c.source.replace("_", " ") + " " + c.text)
            self.chunks.append(c)
            tf = Counter(toks)
            self.tf.append(tf)
            self.len.append(len(toks))
            for w in tf:
                self.df[w] += 1
                self.inv[w].append(len(self.chunks) - 1)
        self.avg = sum(self.len) / max(1, len(self.len))

    def search(self, query: str, k: int = 5, folder: str | None = None, source_contains: str | None = None):
        q = tokenize(query)
        n = len(self.chunks)
        scores: dict[int, float] = defaultdict(float)
        for w in set(q):
            if w not in self.inv:
                continue
            idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
            for i in self.inv[w]:
                f = self.tf[i][w]
                scores[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        out = []
        for i, s in sorted(scores.items(), key=lambda x: -x[1]):
            c = self.chunks[i]
            if folder and not c.folder.startswith(folder):
                continue
            if source_contains and source_contains.lower() not in c.source.lower():
                continue
            out.append((s, c))
            if len(out) >= k:
                break
        return out

    # persistence
    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for c in self.chunks:
                f.write(json.dumps({"t": c.text, "s": c.source, "f": c.folder, "l": c.locator, "c": c.collection}) + "\n")

    @classmethod
    def load(cls, path: Path):
        ix = cls()
        chunks = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                chunks.append(Chunk(d["t"], d["s"], d["f"], d["l"], d["c"]))
        ix.add(chunks)
        return ix


_CACHE: dict[str, BM25Index] = {}


def build_index(root: Path, name: str, force: bool = False) -> BM25Index:
    path = INDEX_DIR / f"{name}.jsonl"
    if not force and path.exists():
        ix = BM25Index.load(path)
    else:
        ix = BM25Index()
        ix.add(iter_chunks(root, name))
        ix.save(path)
    _CACHE[name] = ix
    return ix


def get_index(name: str, root: Path | None = None) -> BM25Index | None:
    if name in _CACHE:
        return _CACHE[name]
    path = INDEX_DIR / f"{name}.jsonl"
    if path.exists():
        return build_index(root or Path("."), name)
    if root and root.exists():
        return build_index(root, name)
    return None


def format_hits(hits, max_chars: int) -> str:
    if not hits:
        return "NO RESULTS. Try different keywords, or list the folder to see what exists. Absence of a document is itself a finding."
    out, used = [], 0
    for s, c in hits:
        block = f"{c.cite} (score {s:.1f})\n{c.text}\n"
        if used + len(block) > max_chars:
            block = block[: max(0, max_chars - used)] + " …[truncated]"
        out.append(block)
        used += len(block)
        if used >= max_chars:
            break
    return "\n---\n".join(out)
