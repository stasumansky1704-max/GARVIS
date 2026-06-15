"""
DEPRECATED. The old level test used per-chunk sd.rec over WDM-KS, which triggered
kernel BugCheck 0x0000010D. Use the safe persistent-stream test instead:

    python voice_client/safe_mic_test.py

This shim forwards to safe_mic_test so nothing breaks and nothing dangerous runs.
"""
from __future__ import annotations

import sys

try:
    from safe_mic_test import main
except ImportError:
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from safe_mic_test import main

if __name__ == "__main__":
    print("[note] mic_level_test.py is deprecated; running safe_mic_test instead.\n")
    raise SystemExit(main())
