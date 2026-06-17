"""
Lightweight secret scanner for orchestrator artifacts (NOT the whole repo).

Scans a directory's text files for obvious secret patterns so generated artifacts/history
never accidentally contain credentials. Returns a list of (file, pattern) hits.

CLI:  python runtime/orchestrator/secret_scan.py [dir ...]
"""
from __future__ import annotations

import os
import re
import sys

# Obvious credential patterns (kept tight to avoid false positives on URLs/ids).
_PATTERNS = [
    ("openai/sk key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b")),
    ("api_key assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][A-Za-z0-9._\-]{12,}['\"]")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
_TEXT_EXT = (".md", ".json", ".jsonl", ".txt", ".log")


def scan_text(text: str) -> list[str]:
    hits = []
    for name, pat in _PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def scan_dir(path: str) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    if not os.path.isdir(path):
        return findings
    for root, _, files in os.walk(path):
        for fn in files:
            if not fn.lower().endswith(_TEXT_EXT):
                continue
            fp = os.path.join(root, fn)
            try:
                text = open(fp, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for name in scan_text(text):
                findings.append((fp, name))
    return findings


def main(argv: list[str]) -> int:
    _DIR = os.path.dirname(os.path.abspath(__file__))
    dirs = argv or [os.path.join(_DIR, "_artifacts"), os.path.join(_DIR, "_runs")]
    total = 0
    for d in dirs:
        for fp, name in scan_dir(d):
            print(f"  [SECRET?] {name}  in  {fp}")
            total += 1
    if total == 0:
        print("  clean: no obvious secrets in scanned artifact dirs")
        return 0
    print(f"  FOUND {total} potential secret(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
