#!/usr/bin/env bash
###############################################################################
# GARVIS Stop Script — Graceful shutdown
###############################################################################
set -euo pipefail
GARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GARVIS_DIR"

echo "[GARVIS] Stopping..."
docker compose down --volumes=false 2>&1 | tail -5
echo "[GARVIS] Stopped."
