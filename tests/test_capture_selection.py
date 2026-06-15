"""
Capture device-selection tests for garvis_conversation.open_capture.

No audio, no network: list_input_devices / _openable / Capture are monkeypatched so the
selection LOGIC is tested in isolation. Proves the fallback prefers the name-matched
(HyperX) device over a louder-at-idle device (the Intel-mic-array bug).

Runs with pytest OR standalone:  python tests/test_capture_selection.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "voice_client"))
import garvis_conversation as gc

HYPERX = (12, "Microphone (HyperX QuadCast 2 S)", 48000, "Windows WASAPI")
INTEL = (11, "Microphone Array (Intel Smart Sound)", 48000, "Windows WASAPI")


class _FakeCap:
    """Stand-in for Capture: idle peaks are scripted by device name via PEAKS."""
    PEAKS: dict[str, float] = {}

    def __init__(self, device, rate, name, backend):
        self.device, self.rate, self.name, self.backend = device, rate, name, backend

    def start(self): pass
    def stop(self): pass
    def drain(self): pass

    def peak(self, seconds: float = 1.0) -> float:
        for key, val in self.PEAKS.items():
            if key.lower() in self.name.lower():
                return val
        return 0.0


def _patch(devices, peaks, hint="HyperX"):
    gc.list_input_devices = lambda: list(devices)
    gc._openable = lambda i, r: True
    _FakeCap.PEAKS = peaks
    gc.Capture = _FakeCap
    gc.MIC_NAME_HINT = hint


def test_idle_fallback_prefers_hyperx_over_louder_intel():
    # HyperX idles silent (0.0); Intel idles louder (0.002). Neither beats USABLE_PEAK.
    _patch([HYPERX, INTEL], {"hyperx": 0.0, "intel": 0.002})
    cap, pk = gc.open_capture()
    assert cap is not None and "hyperx" in cap.name.lower(), \
        f"expected HyperX, got {cap and cap.name}"


def test_speaking_returns_hyperx_immediately():
    # HyperX clears the gate (speaking) -> selected immediately.
    _patch([HYPERX, INTEL], {"hyperx": 0.5, "intel": 0.002})
    cap, pk = gc.open_capture()
    assert "hyperx" in cap.name.lower() and pk >= gc.USABLE_PEAK


def test_name_override_selects_intel_when_hint_is_intel():
    # With hint "Intel", the name-matched fallback should be the Intel array.
    _patch([HYPERX, INTEL], {"hyperx": 0.0, "intel": 0.0}, hint="Intel")
    cap, pk = gc.open_capture()
    assert "intel" in cap.name.lower()


def test_no_devices_returns_none():
    _patch([], {})
    cap, pk = gc.open_capture()
    assert cap is None and pk == 0.0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}"); ok += 1
    print(f"\n{ok}/{len(fns)} tests passed")
    return 0 if ok == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
