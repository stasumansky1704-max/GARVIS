#!/usr/bin/env bash
###############################################################################
# GARVIS Restart Script
###############################################################################
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[GARVIS] Restarting..."
"$SCRIPT_DIR/stop_garvis.sh"
sleep 3
"$SCRIPT_DIR/start_garvis.sh"
