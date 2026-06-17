"""
Group A - research quality tests (offline, deterministic). Covers query decomposition,
broadening, cleaning, dedup, ranking, confidence, quality/completeness/coverage scoring,
empty-result explanation, minimum-useful threshold, and the worker's automatic retry.

Runs with pytest OR standalone:  python tests/test_research_quality.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator import research_quality as rq
from orchestrator.decompose import decompose, decompose_smart
from orchestrator.models import TaskSpec, Status
from orchestrator.workers.research_worker import ResearchWorker


# ---- query shaping ----
def test_clean_query_strips_filler_and_project_tokens():
    out = rq.clean_query("best open source AI agent frameworks for GARVIS")
    assert "garvis" not in out and "best" not in out and "for" not in out
    assert "agent" in out and "frameworks" in out


def test_clean_query_wikipedia_tightens_to_head_phrase():
    out = rq.clean_query("best open source AI agent frameworks for GARVIS", source="wikipedia")
    assert len(out.split()) <= 4 and "agent" in out


def test_extract_terms_drops_short_and_filler():
    terms = rq.extract_terms("the best AI tools for GARVIS")
    assert "garvis" not in terms and "best" not in terms and "the" not in terms


def test_expand_query_produces_broader_variants():
    variants = rq.expand_query("best open source AI agent frameworks for GARVIS")
    assert len(variants) >= 3
    # the broadest variant is shorter than the first
    assert len(variants[-1].split()) <= len(variants[0].split())


def test_broaden_query_drops_leading_qualifier():
    assert rq.broaden_query("open source ai agent frameworks") == "source ai agent frameworks"
    assert rq.broaden_query("frameworks") == "frameworks"   # cannot broaden further


def test_source_query_never_empty():
    assert rq.source_query("GARVIS", "wikipedia")            # project-only term -> falls back
    assert rq.source_query("the best of", "duckduckgo")


# ---- result shaping ----
def _f(title, url="", source="wikipedia", conf=0.7, snippet=""):
    return {"title": title, "url": url, "source": source, "confidence": conf, "snippet": snippet}


def test_dedup_findings_by_url_keeps_highest_confidence():
    fs = [_f("A", "http://x/1", conf=0.5), _f("A2", "http://x/1/", conf=0.9), _f("B", "http://x/2")]
    out = rq.dedup_findings(fs)
    assert len(out) == 2
    a = [f for f in out if f["url"].startswith("http://x/1")][0]
    assert a["confidence"] == 0.9


def test_rank_findings_orders_by_relevance():
    fs = [_f("unrelated thing", snippet="nothing"),
          _f("AI agent frameworks compared", snippet="agent frameworks ai")]
    ranked = rq.rank_findings(fs, "ai agent frameworks")
    assert ranked[0]["title"].startswith("AI agent") and "relevance" in ranked[0]


def test_score_confidence_rewards_overlap():
    high = rq.score_confidence(_f("ai agent frameworks", snippet="ai agent frameworks"), "ai agent frameworks")
    low = rq.score_confidence(_f("cooking recipes", snippet="pasta"), "ai agent frameworks")
    assert high > low


# ---- judgement ----
def test_source_coverage_counts_distinct():
    cov = rq.source_coverage([_f("a", source="wikipedia"), _f("b", source="duckduckgo"),
                              _f("c", source="wikipedia")])
    assert cov["distinct_sources"] == 2 and cov["by_source"]["wikipedia"] == 2 and cov["total"] == 3


def test_quality_score_scales_with_volume_and_diversity():
    empty = rq.quality_score([])
    rich = rq.quality_score([_f("a", source="wikipedia", conf=0.9),
                             _f("b", source="duckduckgo", conf=0.8),
                             _f("c", source="wikipedia", conf=0.85)])
    assert empty == 0.0 and rich > 0.5


def test_completeness_score_term_coverage():
    fs = [_f("AI agent frameworks overview", snippet="agent frameworks")]
    score = rq.completeness_score("ai agent frameworks", fs)
    assert 0.0 < score <= 1.0


def test_min_useful_threshold_and_is_useful():
    assert rq.MIN_USEFUL_FINDINGS == 3
    assert not rq.is_useful([_f("a")])
    assert rq.is_useful([_f("a"), _f("b"), _f("c")])


def test_explain_empty_suggests_broader_query():
    msg = rq.explain_empty("best open source AI agent frameworks for GARVIS")
    assert "broader query" in msg.lower() and "garvis" not in msg.split("query:")[-1].lower()


# ---- decomposition ----
def test_decompose_includes_cleaned_query():
    qs = decompose("best open source AI agent frameworks for GARVIS", 6)
    assert any("garvis" not in q.lower() and "agent" in q.lower() for q in qs)


def test_decompose_smart_prioritizes_broad_queries():
    qs = decompose_smart("best open source AI agent frameworks for GARVIS", 5)
    assert qs and all(isinstance(q, str) for q in qs)
    # at least one variant strips the project token
    assert any("garvis" not in q.lower() for q in qs)


# ---- worker: automatic retry with broader query on sparse results ----
def test_worker_retries_broader_when_sparse():
    calls = []

    def fake_fetch(q):
        calls.append(q)
        if len(calls) == 1:
            return ([{"title": "one", "url": "u1", "source": "wikipedia", "confidence": 0.5}], [])
        # broader query returns enough to cross the useful threshold
        return ([{"title": f"r{i}", "url": f"u{i}", "source": "duckduckgo", "confidence": 0.6}
                 for i in range(3)], [])

    w = ResearchWorker(fetch=fake_fetch, max_findings=10)
    env = w.run(TaskSpec(id="r", worker="research", intent="x",
                         inputs={"query": "open source ai agent frameworks"}))
    assert env.status == Status.DONE
    assert env.result["retries"] >= 1 and len(calls) >= 2
    assert env.result["useful"] is True and env.result["quality"] > 0


def test_worker_no_retry_flag_disables_broadening():
    calls = []

    def fake_fetch(q):
        calls.append(q)
        return ([{"title": "one", "url": "u1", "source": "wikipedia", "confidence": 0.5}], [])

    w = ResearchWorker(fetch=fake_fetch, max_findings=10)
    env = w.run(TaskSpec(id="r", worker="research", intent="x",
                         inputs={"query": "niche", "no_retry": True}))
    assert env.result["retries"] == 0 and len(calls) == 1


def test_worker_empty_result_is_explained():
    w = ResearchWorker(fetch=lambda q: ([], []), max_findings=5)
    env = w.run(TaskSpec(id="r", worker="research", intent="x", inputs={"query": "zzz for GARVIS"}))
    assert env.status == Status.DONE and env.result["count"] == 0
    assert any("broader query" in e.lower() for e in env.result["source_errors"])


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
