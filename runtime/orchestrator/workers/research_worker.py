"""
Research Worker - REAL, READ-ONLY web research (no mock by default, no side effects).

Sources (no API key): Wikipedia search API, DuckDuckGo Instant Answer API. Each finding
carries: title, source, url, snippet, confidence, timestamp. Honors max_findings and a
per-run external-request budget; respects source toggles. Failures are structured (never
crash the run; never fabricate data). HTTP fetcher is injectable for offline tests.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from .base import Worker
from ..models import TaskSpec, Envelope, Status, SafetyClass
from ..registry import WorkerSpec
from ..research_quality import (MIN_USEFUL_FINDINGS, broaden_query, completeness_score,
                                dedup_findings, explain_empty, quality_score, rank_findings,
                                score_confidence, source_coverage, source_query)

_UA = {"User-Agent": "GARVIS-Research/0.1 (local read-only research worker)"}
_TIMEOUT = 15


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


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
                    "snippet": snippet, "source": "wikipedia",
                    "confidence": 0.7, "timestamp": _now()})
    return out


def _duckduckgo(query: str, limit: int = 5) -> list[dict]:
    url = ("https://api.duckduckgo.com/?format=json&no_html=1&skip_disambig=1&q=%s"
           % urllib.parse.quote(query))
    data = _http_json(url)
    out = []
    if data.get("AbstractText"):
        out.append({"title": data.get("Heading", "Abstract"),
                    "url": data.get("AbstractURL", ""), "snippet": data["AbstractText"],
                    "source": "duckduckgo", "confidence": 0.65, "timestamp": _now()})
    for t in data.get("RelatedTopics", [])[:limit]:
        if isinstance(t, dict) and t.get("Text"):
            out.append({"title": t.get("Text", "")[:80], "url": t.get("FirstURL", ""),
                        "snippet": t.get("Text", ""), "source": "duckduckgo",
                        "confidence": 0.4, "timestamp": _now()})
    return out


_SOURCE_FNS = {"wikipedia": _wikipedia, "duckduckgo": _duckduckgo}


class ResearchWorker(Worker):
    spec = WorkerSpec(
        name="research",
        capabilities=["web_search", "summarize"],
        tool_permissions=["web:read"],
        safety_class=SafetyClass.READ,
        cost_class="cheap",
        description="Real read-only web research (Wikipedia + DDG) -> attributed findings.",
    )

    def __init__(self, fetch=None, max_findings: int = 5,
                 sources: tuple[str, ...] = ("wikipedia", "duckduckgo")):
        self._fetch = fetch                      # injectable: fetch(query)->(findings,errors)
        self.max_findings = max_findings
        self.sources = sources
        self.request_budget = None               # set per-run by the engine (int|None)

    def _real_fetch(self, query: str) -> tuple[list[dict], list[str]]:
        findings, errors = [], []
        for name in self.sources:
            fn = _SOURCE_FNS.get(name)
            if fn is None:
                continue
            if self.request_budget is not None and self.request_budget <= 0:
                errors.append(f"{name}: skipped (request budget exhausted)")
                continue
            try:
                findings.extend(fn(source_query(query, name), self.max_findings))
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
            finally:
                if self.request_budget is not None:
                    self.request_budget -= 1
        return findings, errors

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
        fetch = self._fetch or self._real_fetch
        retries = 0 if task.inputs.get("no_retry") else 2
        try:
            findings, errors, retries_used = self._fetch_with_broadening(fetch, query, retries)
        except Exception as exc:                 # structured failure; never crash the run
            return Envelope(task_id=task.id, status=Status.FAILED,
                            error=f"research fetch failed: {type(exc).__name__}: {exc}",
                            result={"query": query, "findings": [], "sources": [],
                                    "summary": "research failed", "count": 0,
                                    "source_errors": [str(exc)], "quality": 0.0,
                                    "completeness": 0.0, "coverage": source_coverage([])})
        # Improve confidence, dedup, rank, then trim to the budget.
        for f in findings:
            f["confidence"] = score_confidence(f, query)
        findings = rank_findings(dedup_findings(findings), query)[: self.max_findings]
        logs = [f"ResearchWorker: {len(findings)} findings"]
        if retries_used:
            logs.append(f"broadened query {retries_used}x to improve recall")
        if not findings:
            errors = list(errors) + [explain_empty(query, errors)]
        if errors:
            logs.append("source notes: " + ", ".join(errors))
        result = {"query": query, "findings": findings,
                  "sources": [f["url"] for f in findings if f.get("url")],
                  "summary": self._summarize(query, findings), "count": len(findings),
                  "source_errors": errors, "quality": quality_score(findings),
                  "completeness": completeness_score(query, findings),
                  "coverage": source_coverage(findings), "retries": retries_used,
                  "useful": len(findings) >= MIN_USEFUL_FINDINGS}
        return Envelope(task_id=task.id, status=Status.DONE, result=result, logs=logs)

    def _fetch_with_broadening(self, fetch, query, retries):
        """Fetch; if too few findings, retry with progressively broader queries (capability:
        automatic retry with broader query). Returns (findings, errors, retries_used)."""
        findings, errors = fetch(query)
        used, current = 0, query
        while len(dedup_findings(findings)) < MIN_USEFUL_FINDINGS and used < retries:
            broader = broaden_query(current)
            if not broader or broader == current:
                break
            more, errs = fetch(broader)
            findings = findings + more
            errors = list(errors) + [f"retry '{broader}'"] + list(errs)
            current = broader
            used += 1
        return findings, errors, used
