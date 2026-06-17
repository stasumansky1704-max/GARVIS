"""
Artifact catalog + search over the gitignored artifacts dir.

catalog(dir) -> [{name, path, size, mtime}]   (newest first)
search(dir, query) -> matching artifacts (filename OR content contains query)
"""
from __future__ import annotations

import os
import time


def catalog(dir_path: str) -> list[dict]:
    if not os.path.isdir(dir_path):
        return []
    items = []
    for fn in os.listdir(dir_path):
        fp = os.path.join(dir_path, fn)
        if os.path.isfile(fp):
            st = os.stat(fp)
            items.append({"name": fn, "path": fp, "size": st.st_size,
                          "mtime": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                 time.localtime(st.st_mtime))})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def search(dir_path: str, query: str) -> list[dict]:
    q = (query or "").lower().strip()
    if not q:
        return catalog(dir_path)
    hits = []
    for item in catalog(dir_path):
        if q in item["name"].lower():
            hits.append(item); continue
        try:
            if q in open(item["path"], encoding="utf-8", errors="replace").read().lower():
                hits.append(item)
        except Exception:
            pass
    return hits
