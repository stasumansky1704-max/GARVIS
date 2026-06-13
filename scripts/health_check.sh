#!/usr/bin/env bash
###############################################################################
# GARVIS Health Check — Validates all services
# Usage: ./scripts/health_check.sh
###############################################################################
set -euo pipefail

GRN='\033[0;32m'
RED='\033[0;31m'
RST='\033[0m'

echo "[GARVIS] Health Check"
echo "========================"

ALL_OK=true

check() {
    local name="$1" url="$2"
    if curl -s "$url" &>/dev/null; then
        echo -e "  ${GRN}PASS${RST} $name"
    else
        echo -e "  ${RED}FAIL${RST} $name"
        ALL_OK=false
    fi
}

check "GARVIS API"     "http://localhost:8000/api/v1/status/health"
check "Ollama"         "http://localhost:11434/api/tags"
check "Governance"     "http://localhost:8000/api/v1/governance/schemas"
check "Cognition"      "http://localhost:8000/api/v1/cognition/state"
check "Memory"         "http://localhost:8000/api/v1/memory/memories"
check "Traceability"   "http://localhost:8000/api/v1/traceability/traces"
check "Audit"          "http://localhost:8000/api/v1/audit/events"
check "Analytics"      "http://localhost:8000/api/v1/analytics/overview"
check "Command Center" "http://localhost:8000/api/v1/command-center/overview"

echo ""
if $ALL_OK; then
    echo -e "${GRN}All services healthy${RST}"
    exit 0
else
    echo -e "${RED}Some services unhealthy${RST}"
    exit 1
fi
