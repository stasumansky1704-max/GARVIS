"""
Research Worker - REAL, READ-ONLY web research (no mock by default, no side effects).

Sources (no API key required):
  - Wikipedia search API (reliable, structured)   -> findings with titles/urls/snippets
  - DuckDuckGo Instant Answer API (best-effort)    -> abstract + related topics

Returns STRUCTURED findings:
  {"query", "findings":[{title,url,snippet,source}], "sources":[url], "summary", "count"}

READ-ONLY: GET requests only. No file writes, no repo changes, no PRs, no mutation.
The HTTP fetcher is injectable (`fetch=`) so tests run fully offline/deterministic.
Real implementation deliberately uses lightweight HTTP (not a headless browser); for
JS-heavy sites the upgrade path is Browser Use/MCP (see GARVIS_REUSE_AUDIT.md).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec

_UA = {"User-Agent": "GARVIS-Research/0.1 (local read-only research worker)"}
_TIMEOUT = 15


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _wikipedia(query: str, limit: int = 5) -> list[dict]:
    url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
           "&srlimit=%d&srsearch=%s" % (limit, urllib.parse.quote(query)))
    data = _http_json(url)
    out = []
    for r in data.get("query", {}).get("search", []):
        snippet = re.sub("<[^>]+>", "", r.get("snippet", "")).strip()
        out.append({"title": r.get("title", ""),
                    "url": "https://en.wikipedia.org/?curid=%s" % r.get("pageid", ""),
                    "snippet": snippet, "source": "wikipedia"})
    return out


def _duckduckgo(query: str) -> list[dict]:
    url = ("https://api.duckduckgo.com/?format=json&no_html=1&skip_disambig=1&q=%s"
           % urllib.parse.quote(query))
    data = _http_json(url)
    out = []
    if data.get("AbstractText"):
        out.append({"title": data.get("Heading", "Abstract"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["AbstractText"], "source": "duckduckgo"})
    for t in data.get("RelatedTopics", [])[:5]:
        if isinstance(t, dict) and t.get("Text"):
            out.append({"title": t.get("Text", "")[:80], "url": t.get("FirstURL", ""),
                        "snippet": t.get("Text", ""), "source": "duckduckgo"})
    return out


def real_fetch(query: str) -> tuple[list[dict], list[str]]:
    """Query real sources read-only. Returns (findings, errors). Never raises."""
    findings, errors = [], []
    for fn in (_wikipedia, _duckduckgo):
        try:
            findings.extend(fn(query))
        except Exception as exc:
            errors.append(f"{fn.__name__}: {type(exc).__name__}")
    return findings, errors


class ResearchWorker(Worker):
    spec = WorkerSpec(
        name="research",
        capabilities=["web_search", "summarize"],
        tool_permissions=["web:read"],          # read-only
        safety_class=SafetyClass.READ,          # reads need no approval
        cost_class="cheap",
        description="Real read-only web research (Wikipedia + DDG) -> structured findings.",
    )

    def __init__(self, fetch=None):
        # fetch(query) -> (findings, errors). Default = real network. Tests inject a fake.
        self._fetch = fetch or real_fetch

    @staticmethod
    def _summarize(query: str, findings: list[dict]) -> str:
        if not findings:
            return f"No results found for: {query}"
        tops = [f["snippet"] for f in findings[:3] if f.get("snippet")]
        return f"Top findings for '{query}': " + " | ".join(tops)

    def run(self, task: TaskSpec) -> Envelope:
        query = str(task.inputs.get("query", "")).strip()
        if not query:
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error="research task missing 'query' input")
        try:
            findings, errors = self._fetch(query)
        except Exception as exc:                 # belt-and-suspenders; fetch should not raise
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"research fetch failed: {type(exc).__name__}: {exc}")
        sources = [f["url"] for f in findings if f.get("url")]
        result = {
            "query": query,
            "findings": findings,
            "sources": sources,
            "summary": self._summarize(query, findings),
            "count": len(findings),
            "source_errors": errors,
        }
        logs = [f"ResearchWorker: {len(findings)} findings"]
        if errors:
            logs.append("source errors: " + ", ".join(errors))
        return Envelope(task_id=task.id, status=Status.DONE, result=result, logs=logs)
