"""
Result merger. WORKING MVP: fold worker envelopes into the Run and derive overall status
(FAILED if any failed, else BLOCKED if any blocked/awaiting approval, else DONE).
"""
from __future__ import annotations

from .models import Envelope, Run, Status


class ResultMerger:
    def merge(self, run: Run, results: dict[str, Envelope]) -> Run:
        run.results.update(results)
        statuses = [e.status for e in results.values()]
        if any(s == Status.FAILED for s in statuses):
            run.status = Status.FAILED
        elif any(s == Status.BLOCKED for s in statuses):
            run.status = Status.BLOCKED
        elif statuses and all(s == Status.DONE for s in statuses):
            run.status = Status.DONE
        else:
            run.status = Status.PENDING
        return run
