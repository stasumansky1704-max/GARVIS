"""
Memory system - lightweight, file-backed (JSONL), no database.

Layers: user, project, decision, rule, run. Supports add/get/list/search/compress and
planner_context() which feeds relevant memory into planning (rules + user always; plus
decisions and goal-relevant items). Run memory is derived from completed runs so the
planner learns from history. Gitignored storage.
"""
from __future__ import annotations

import json
import os
import time
import uuid

LAYERS = ("user", "project", "decision", "rule", "run")
_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "memory.jsonl")


def _tokens(s: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(t) > 2}


# Layer base importance (rules/user persist; runs are ephemeral).
_LAYER_IMPORTANCE = {"rule": 0.9, "user": 0.85, "decision": 0.6, "project": 0.7, "run": 0.3}


def _default_importance(layer: str, tags=None) -> float:
    base = _LAYER_IMPORTANCE.get(layer, 0.5)
    if tags and "safety" in tags:
        base = 1.0
    return base


def is_protected(rec: dict) -> bool:
    """Safety rules are protected: never deletable, never archived."""
    return rec.get("layer") == "rule" and "safety" in (rec.get("tags") or [])


class MemoryStore:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT
        self.links_path = self.path + ".links"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def add(self, layer: str, text: str, tags=None, meta=None, confidence: float = 1.0,
            importance: float | None = None, source: str | None = None,
            ttl_days: int | None = None) -> str:
        if layer not in LAYERS:
            raise ValueError(f"unknown memory layer {layer!r} (use {LAYERS})")
        rec = {"id": uuid.uuid4().hex[:12], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "layer": layer, "text": text, "tags": list(tags or []),
               "meta": meta or {}, "confidence": float(confidence),
               "importance": float(importance if importance is not None
                                   else _default_importance(layer, tags)),
               "source": source or (meta or {}).get("source", "manual"),
               "archived": False, "ttl_days": ttl_days, "uses": 0}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec["id"]

    def _rewrite(self, records: list[dict]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        return out

    def list(self, layer: str | None = None) -> list[dict]:
        return [r for r in self.all() if layer is None or r["layer"] == layer]

    def get(self, mid: str) -> dict | None:
        for r in self.all():
            if r["id"] == mid:
                return r
        return None

    def _age_days(self, rec: dict, now_ts: float | None = None) -> float:
        try:
            created = time.mktime(time.strptime(rec["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            return 0.0
        now = now_ts if now_ts is not None else time.time()
        return max(0.0, (now - created) / 86400.0)

    def relevance(self, rec: dict, q: set, now_ts: float | None = None) -> float:
        """Retrieval ranking: term overlap weighted by importance, confidence, use-count, and
        recency (newer memories rank slightly higher; old unused ones fade)."""
        overlap = len(q & _tokens(rec["text"] + " " + " ".join(rec.get("tags", []))))
        if not overlap:
            return 0.0
        imp = float(rec.get("importance", 0.5))
        conf = float(rec.get("confidence", 1.0))
        uses = min(0.3, 0.05 * int(rec.get("uses", 0)))
        recency = max(0.0, 1.0 - self._age_days(rec, now_ts) / 365.0) * 0.15
        return round(overlap * (0.6 + 0.4 * imp) * (0.7 + 0.3 * conf) + uses + recency, 4)

    def search(self, query: str, layer: str | None = None, limit: int = 10,
               include_archived: bool = False) -> list[dict]:
        q = _tokens(query)
        scored = []
        for r in self.list(layer):
            if r.get("archived") and not include_archived:
                continue
            s = self.relevance(r, q)
            if s:
                scored.append((s, r))
        scored.sort(key=lambda x: (-x[0], x[1]["ts"]))
        return [r for _, r in scored[:limit]]

    def reinforce(self, mid: str, by: float = 0.1) -> bool:
        """Feedback loop: bump importance + use-count of a memory (e.g. after a good review)."""
        recs = self.all()
        hit = False
        for r in recs:
            if r["id"] == mid:
                r["importance"] = round(min(1.0, float(r.get("importance", 0.5)) + by), 4)
                r["uses"] = int(r.get("uses", 0)) + 1
                hit = True
        if hit:
            self._rewrite(recs)
        return hit

    def archive(self, mid: str) -> bool:
        """Mark a memory archived (TTL/retention). Protected safety rules cannot be archived."""
        recs = self.all()
        hit = False
        for r in recs:
            if r["id"] == mid and not is_protected(r):
                r["archived"] = True
                hit = True
        if hit:
            self._rewrite(recs)
        return hit

    def expire(self, now_ts: float | None = None) -> int:
        """Archive memories whose ttl_days elapsed. Returns count archived. Never touches
        protected safety rules."""
        now = now_ts if now_ts is not None else time.time()
        recs = self.all()
        n = 0
        for r in recs:
            if r.get("archived") or is_protected(r) or not r.get("ttl_days"):
                continue
            try:
                created = time.mktime(time.strptime(r["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                continue
            if (now - created) > int(r["ttl_days"]) * 86400:
                r["archived"] = True
                n += 1
        if n:
            self._rewrite(recs)
        return n

    def delete(self, mid: str, approve: bool = False) -> dict:
        """Delete requires explicit approval; protected safety rules can never be deleted."""
        rec = self.get(mid)
        if not rec:
            return {"deleted": False, "reason": "not found"}
        if is_protected(rec):
            return {"deleted": False, "reason": "protected safety rule (never deletable)"}
        if not approve:
            return {"deleted": False, "reason": "deletion requires approve=True"}
        self._rewrite([r for r in self.all() if r["id"] != mid])
        return {"deleted": True, "id": mid}

    def consolidate(self, threshold: float = 0.8) -> int:
        """Merge near-duplicate memories in the same layer (token-overlap >= threshold).
        Keeps the highest-importance record, sums use-counts. Returns memories removed.
        Protected safety rules are never merged away."""
        recs = self.all()
        keep: list[dict] = []
        removed = 0
        for r in recs:
            merged = False
            rt = _tokens(r["text"])
            for k in keep:
                if k["layer"] != r["layer"] or is_protected(k) or is_protected(r):
                    continue
                kt = _tokens(k["text"])
                if not rt or not kt:
                    continue
                sim = len(rt & kt) / len(rt | kt)
                if sim >= threshold:
                    if float(r.get("importance", 0.5)) > float(k.get("importance", 0.5)):
                        k["text"] = r["text"]
                        k["importance"] = r["importance"]
                    k["uses"] = int(k.get("uses", 0)) + int(r.get("uses", 0))
                    merged = True
                    removed += 1
                    break
            if not merged:
                keep.append(r)
        if removed:
            self._rewrite(keep)
        return removed

    def promote(self, mid: str) -> bool:
        """Lifecycle: promote a run-layer memory to a decision (durable) once it has proven
        useful. No-op for non-run layers."""
        recs = self.all()
        hit = False
        for r in recs:
            if r["id"] == mid and r["layer"] == "run":
                r["layer"] = "decision"
                r["importance"] = round(min(1.0, float(r.get("importance", 0.3)) + 0.3), 4)
                r.setdefault("tags", []).append("promoted")
                hit = True
        if hit:
            self._rewrite(recs)
        return hit

    def decay(self, rate: float = 0.05, now_ts: float | None = None,
              floor: float = 0.1) -> int:
        """Lifecycle: reduce importance of old, unused, non-protected memories. Returns the
        number decayed. Anything older than 30 days with zero uses loses `rate` importance."""
        recs = self.all()
        n = 0
        for r in recs:
            if is_protected(r) or int(r.get("uses", 0)) > 0:
                continue
            if self._age_days(r, now_ts) > 30:
                new = round(max(floor, float(r.get("importance", 0.5)) - rate), 4)
                if new != r.get("importance"):
                    r["importance"] = new
                    n += 1
        if n:
            self._rewrite(recs)
        return n

    def find_duplicates(self) -> list[list[str]]:
        """Groups of memory ids that share (layer, normalized text)."""
        groups: dict[tuple, list[str]] = {}
        for r in self.all():
            groups.setdefault((r["layer"], r["text"].strip().lower()), []).append(r["id"])
        return [ids for ids in groups.values() if len(ids) > 1]

    def export_jsonl(self) -> str:
        """Serialize all memories to a JSONL string (for backup / transfer)."""
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in self.all())

    def import_jsonl(self, text: str, dedup: bool = True) -> int:
        """Import memories from a JSONL string. Skips exact (layer,text) duplicates when
        dedup=True. Returns number imported."""
        existing = {(r["layer"], r["text"].strip()) for r in self.all()} if dedup else set()
        added = 0
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            key = (r.get("layer"), (r.get("text") or "").strip())
            if dedup and key in existing:
                continue
            r.setdefault("id", uuid.uuid4().hex[:12])
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            existing.add(key)
            added += 1
        return added

    def inspect(self) -> dict:
        """Health snapshot: counts per layer, archived count, duplicate groups, avg importance."""
        recs = self.all()
        by_layer: dict[str, int] = {}
        for r in recs:
            by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + 1
        imps = [float(r.get("importance", 0.5)) for r in recs]
        return {"total": len(recs), "by_layer": by_layer,
                "archived": sum(1 for r in recs if r.get("archived")),
                "protected": sum(1 for r in recs if is_protected(r)),
                "duplicate_groups": len(self.find_duplicates()),
                "avg_importance": round(sum(imps) / len(imps), 3) if imps else 0.0}

    def compress(self) -> int:
        """Dedup identical (layer,text); keep highest confidence. Returns removed count."""
        seen: dict[tuple, dict] = {}
        for r in self.all():
            key = (r["layer"], r["text"].strip())
            if key not in seen or r["confidence"] > seen[key]["confidence"]:
                seen[key] = r
        kept = list(seen.values())
        removed = len(self.all()) - len(kept)
        with open(self.path, "w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return removed

    def validate_compression(self) -> dict:
        """Verify compression invariant: no remaining (layer,text) duplicates."""
        dups = self.find_duplicates()
        return {"valid": len(dups) == 0, "duplicate_groups": len(dups)}

    def suggest_query_terms(self, goal: str, limit: int = 6) -> list[str]:
        """Memory-driven query improvement: surface terms from relevant past decisions/runs
        to enrich a new research query."""
        terms: list[str] = []
        seen = set(_tokens(goal))
        for r in self.search(goal, limit=limit):
            for t in _tokens(r["text"]):
                if t not in seen:
                    seen.add(t)
                    terms.append(t)
        return terms[:limit]

    # ---- graph layer (relationships + clustering): smarter, connected memory ----
    def link(self, a: str, b: str, rel: str = "related") -> bool:
        """Create a typed relationship between two memories (graph edge). Both must exist."""
        ids = {r["id"] for r in self.all()}
        if a not in ids or b not in ids or a == b:
            return False
        with open(self.links_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"a": a, "b": b, "rel": rel,
                                "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
        return True

    def links(self) -> list[dict]:
        if not os.path.exists(self.links_path):
            return []
        out = []
        with open(self.links_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        return out

    def related(self, mid: str) -> list[dict]:
        """Memories directly linked to mid (either direction)."""
        neighbors = set()
        for e in self.links():
            if e["a"] == mid:
                neighbors.add(e["b"])
            elif e["b"] == mid:
                neighbors.add(e["a"])
        return [r for r in self.all() if r["id"] in neighbors]

    def auto_link(self, threshold: float = 0.5) -> int:
        """Automatically connect memories with high token overlap (builds the graph).
        Returns the number of new edges created. Idempotent-ish (skips existing pairs)."""
        recs = self.all()
        existing = {frozenset((e["a"], e["b"])) for e in self.links()}
        created = 0
        for i in range(len(recs)):
            ti = _tokens(recs[i]["text"])
            for j in range(i + 1, len(recs)):
                pair = frozenset((recs[i]["id"], recs[j]["id"]))
                if pair in existing or recs[i]["id"] == recs[j]["id"]:
                    continue
                tj = _tokens(recs[j]["text"])
                if not ti or not tj:
                    continue
                sim = len(ti & tj) / len(ti | tj)
                if sim >= threshold:
                    self.link(recs[i]["id"], recs[j]["id"], rel="auto")
                    existing.add(pair)
                    created += 1
        return created

    def topics(self, min_size: int = 2) -> list[dict]:
        """Cluster memories into topics via connected components over shared significant
        tokens. Returns [{topic: <top terms>, ids: [...], size: n}] for clusters >= min_size."""
        recs = self.all()
        toks = {r["id"]: _tokens(r["text"]) for r in recs}
        parent = {r["id"]: r["id"] for r in recs}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            parent[find(x)] = find(y)

        ids = list(toks)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if toks[ids[i]] & toks[ids[j]]:
                    union(ids[i], ids[j])
        groups: dict[str, list[str]] = {}
        for mid in ids:
            groups.setdefault(find(mid), []).append(mid)
        out = []
        for members in groups.values():
            if len(members) < min_size:
                continue
            counter: dict[str, int] = {}
            for m in members:
                for t in toks[m]:
                    counter[t] = counter.get(t, 0) + 1
            top = sorted(counter, key=lambda t: -counter[t])[:3]
            out.append({"topic": " ".join(top), "ids": members, "size": len(members)})
        return sorted(out, key=lambda g: -g["size"])

    def graph_stats(self) -> dict:
        return {"nodes": len(self.all()), "edges": len(self.links()),
                "topics": len(self.topics())}

    def planner_context(self, goal: str, limit: int = 8) -> dict:
        return {
            "rules": [r["text"] for r in self.list("rule") if not r.get("archived")],
            "user": [r["text"] for r in self.list("user") if not r.get("archived")],
            "decisions": [r["text"] for r in self.list("decision")
                          if not r.get("archived")][:limit],
            "relevant": [r["text"] for r in self.search(goal, limit=limit)],
            "suggested_terms": self.suggest_query_terms(goal),
        }


def record_run(mem: MemoryStore, run) -> str:
    """Write a run-layer memory derived from a completed run (feedback loop)."""
    status = getattr(run.status, "value", str(run.status))
    summary = ""
    for env in run.results.values():
        if isinstance(env.result, dict) and env.result.get("summary"):
            summary = env.result["summary"]
            break
    text = f"run {run.id}: goal='{run.goal}' -> {status}. {summary}"[:500]
    return mem.add("run", text, tags=["run", status], meta={"run_id": run.id, "goal": run.goal})
