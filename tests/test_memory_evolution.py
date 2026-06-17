"""
Group C - memory evolution tests (offline, deterministic, temp-dir backed).

Covers importance scoring, TTL/archival, source attribution, retrieval ranking, review
feedback (reinforce), memory-driven query improvement, duplicate detection, compression
validation, export/import/inspect, delete-requires-approval, and safety-rule protection.

Runs with pytest OR standalone:  python tests/test_memory_evolution.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime"))

from orchestrator.memory import MemoryStore, is_protected


def _m():
    return MemoryStore(os.path.join(tempfile.mkdtemp(), "m.jsonl"))


def test_importance_defaults_by_layer():
    m = _m()
    rid = m.add("rule", "always require approval")
    run = m.add("run", "did a thing")
    assert m.get(rid)["importance"] > m.get(run)["importance"]


def test_safety_rule_is_protected_and_max_importance():
    m = _m()
    sid = m.add("rule", "never use WDM-KS", tags=["safety"])
    rec = m.get(sid)
    assert is_protected(rec) and rec["importance"] == 1.0


def test_source_attribution():
    m = _m()
    mid = m.add("decision", "use ElevenLabs", source="provider-decision")
    assert m.get(mid)["source"] == "provider-decision"


def test_retrieval_ranking_prefers_important():
    m = _m()
    m.add("run", "agent frameworks note", importance=0.2)
    hi = m.add("decision", "agent frameworks chosen", importance=0.95)
    hits = m.search("agent frameworks")
    assert hits[0]["id"] == hi


def test_reinforce_bumps_importance_and_uses():
    m = _m()
    mid = m.add("decision", "x", importance=0.5)
    assert m.reinforce(mid)
    rec = m.get(mid)
    assert rec["importance"] > 0.5 and rec["uses"] == 1


def test_archive_and_search_excludes_archived():
    m = _m()
    mid = m.add("decision", "deprecated approach to agents")
    m.archive(mid)
    assert mid not in [r["id"] for r in m.search("agents")]
    assert mid in [r["id"] for r in m.search("agents", include_archived=True)]


def test_expire_by_ttl_archives_old():
    m = _m()
    mid = m.add("run", "ephemeral", ttl_days=1)
    # pretend "now" is far in the future
    n = m.expire(now_ts=9_999_999_999)
    assert n == 1 and m.get(mid)["archived"] is True


def test_expire_never_touches_protected():
    m = _m()
    sid = m.add("rule", "never merge without approval", tags=["safety"], ttl_days=1)
    m.expire(now_ts=9_999_999_999)
    assert m.get(sid)["archived"] is False


def test_delete_requires_approval_and_protects_safety():
    m = _m()
    did = m.add("decision", "temp")
    assert m.delete(did, approve=False)["deleted"] is False
    assert m.delete(did, approve=True)["deleted"] is True
    sid = m.add("rule", "no secrets", tags=["safety"])
    assert m.delete(sid, approve=True)["deleted"] is False     # protected


def test_find_duplicates_and_compress_validation():
    m = _m()
    m.add("rule", "same", confidence=0.5)
    m.add("rule", "same", confidence=0.9)
    assert len(m.find_duplicates()) == 1
    removed = m.compress()
    assert removed == 1 and m.validate_compression()["valid"] is True
    assert m.list("rule")[0]["confidence"] == 0.9


def test_export_import_roundtrip_dedup():
    m = _m()
    m.add("decision", "alpha")
    m.add("user", "owner is Stas")
    blob = m.export_jsonl()
    m2 = _m()
    assert m2.import_jsonl(blob) == 2
    assert m2.import_jsonl(blob, dedup=True) == 0               # no duplicates re-added
    assert len(m2.all()) == 2


def test_suggest_query_terms_from_memory():
    m = _m()
    m.add("decision", "langgraph autogen crewai are agent frameworks")
    terms = m.suggest_query_terms("agent frameworks")
    assert any(t in ("langgraph", "autogen", "crewai") for t in terms)


def test_inspect_snapshot():
    m = _m()
    m.add("rule", "r", tags=["safety"])
    m.add("decision", "d")
    snap = m.inspect()
    assert snap["total"] == 2 and snap["protected"] == 1 and "by_layer" in snap


def test_planner_context_has_suggested_terms():
    m = _m()
    m.add("rule", "approve writes")
    m.add("decision", "research agent frameworks")
    ctx = m.planner_context("agent frameworks")
    assert "suggested_terms" in ctx and ctx["rules"]


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
