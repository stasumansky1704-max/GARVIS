"""Result merger (INERT SCAFFOLDING). Normalizes envelopes + resolves dependencies."""
from __future__ import annotations

from .models import Envelope, Run


class ResultMerger:
    def merge(self, run: Run, results: dict[str, Envelope]) -> Run:
        # Real impl (T12): fold envelopes into run.results, resolve dep outputs, surface
        # conflicts explicitly, checkpoint to the RunStore, and hand state back to Planner.
        raise NotImplementedError("ResultMerger.merge: implement per T12")
