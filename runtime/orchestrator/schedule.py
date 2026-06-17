"""
Persisted schedules - recurring research goals that SURVIVE RESTART (file-backed JSONL).

A schedule is {id, goal, interval, window, priority, last_run, next_due}. Execution stays
explicit and approval-gated: schedules only ENQUEUE due items into the ResearchQueue; the
already-bounded `run-due` / `loop` commands run them. No daemon, no hidden timer.

- add / list / remove / get
- due(now) : schedules whose next_due has passed AND are inside their time window
- mark_run(id, now) : advances next_due by interval
- enqueue_due(queue, now) : enqueue a queue item per due schedule and advance it

Time math uses epoch seconds; ISO strings are stored for readability. Windows are
"HH:MM-HH:MM" local, with wrap-around support (e.g. "22:00-06:00").
"""
from __future__ import annotations

import json
import os
import time
import uuid

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_runs", "schedules.jsonl")
MIN_INTERVAL = 60                         # never schedule tighter than 1 minute


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


def parse_window(window: str | None):
    """'HH:MM-HH:MM' -> (start_minutes, end_minutes) or None. Raises ValueError if invalid."""
    if not window:
        return None
    try:
        a, b = window.split("-")
        ah, am = (int(x) for x in a.split(":"))
        bh, bm = (int(x) for x in b.split(":"))
    except Exception:
        raise ValueError(f"bad window {window!r} (use HH:MM-HH:MM)")
    return (ah * 60 + am, bh * 60 + bm)


def in_window(window: str | None, now_ts: float | None = None) -> bool:
    """True if `now` falls inside the window. No window => always true."""
    wm = parse_window(window)
    if wm is None:
        return True
    start, end = wm
    lt = time.localtime(now_ts if now_ts is not None else time.time())
    minutes = lt.tm_hour * 60 + lt.tm_min
    if start <= end:
        return start <= minutes <= end
    return minutes >= start or minutes <= end          # wrap-around window


class ScheduleStore:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _append(self, rec):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _events(self):
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

    def add(self, goal: str, interval: int, window: str | None = None,
            priority: int = 3, now_ts: float | None = None) -> str:
        if not isinstance(interval, int) or interval < MIN_INTERVAL:
            raise ValueError(f"interval must be an int >= {MIN_INTERVAL}s")
        parse_window(window)                           # validate early
        now = now_ts if now_ts is not None else time.time()
        sid = uuid.uuid4().hex[:10]
        nxt = now + interval
        self._append({"id": sid, "goal": goal, "interval": int(interval),
                      "window": window, "priority": int(priority),
                      "created": _iso(now), "last_run": None,
                      "next_due_ts": nxt, "next_due": _iso(nxt)})
        return sid

    def list(self) -> list[dict]:
        latest: dict[str, dict] = {}
        for e in self._events():
            latest[e["id"]] = {**latest.get(e["id"], {}), **e}
        return [s for s in latest.values() if not s.get("removed")]

    def get(self, sid: str) -> dict | None:
        return next((s for s in self.list() if s["id"] == sid), None)

    def remove(self, sid: str) -> bool:
        if not self.get(sid):
            return False
        self._append({"id": sid, "removed": True, "ts": _iso(time.time())})
        return True

    def mark_run(self, sid: str, now_ts: float | None = None) -> bool:
        cur = self.get(sid)
        if not cur:
            return False
        now = now_ts if now_ts is not None else time.time()
        nxt = now + int(cur.get("interval", MIN_INTERVAL))
        self._append({"id": sid, "last_run": _iso(now),
                      "next_due_ts": nxt, "next_due": _iso(nxt)})
        return True

    def due(self, now_ts: float | None = None) -> list[dict]:
        now = now_ts if now_ts is not None else time.time()
        out = [s for s in self.list()
               if float(s.get("next_due_ts", 0)) <= now and in_window(s.get("window"), now)]
        return sorted(out, key=lambda s: (s.get("priority", 3), s.get("next_due_ts", 0)))

    def enqueue_due(self, queue, now_ts: float | None = None) -> list[dict]:
        """Enqueue a queue item for each due schedule and advance it. Returns enqueued info.
        Does NOT execute anything - the approved run-due/loop runs the queue."""
        now = now_ts if now_ts is not None else time.time()
        enqueued = []
        for s in self.due(now):
            qid = queue.enqueue(s["goal"], priority=s.get("priority", 3))
            self.mark_run(s["id"], now)
            enqueued.append({"schedule_id": s["id"], "queue_id": qid, "goal": s["goal"]})
        return enqueued
