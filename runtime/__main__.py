"""Entry point for GARVIS runtime.

Usage:
    python -m runtime
"""
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from garvis_cli import main

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
