#!/usr/bin/env bash
###############################################################################
# GARVIS Status Script — Full system status
###############################################################################
set -euo pipefail
GARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GARVIS_DIR"

GRN='\033[0;32m'
RED='\033[0;31m'
YLW='\033[1;33m'
BLU='\033[0;34m'
RST='\033[0m'

echo ""
echo "============================================================"
echo "  GARVIS — System Status"
echo "============================================================"
echo ""

# Container status
echo "--- Docker Containers ---"
if docker compose ps 2>/dev/null | grep -q garvis; then
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
else
    echo "  No containers running"
fi

# Service health
echo ""
echo "--- Service Health ---"

# API
if curl -s http://localhost:8000/api/v1/status/health &>/dev/null; then
    echo -e "  ${GRN}●${RST} GARVIS API     http://localhost:8000"
else
    echo -e "  ${RED}●${RST} GARVIS API     Not responding"
fi

# Ollama
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    OLLAMA_MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | head -3 | tr '\n' ' ')
    echo -e "  ${GRN}●${RST} Ollama         http://localhost:11434 $OLLAMA_MODELS"
else
    echo -e "  ${RED}●${RST} Ollama         Not responding"
fi

# PostgreSQL
if docker compose exec -T postgres pg_isready -U garvis &>/dev/null; then
    echo -e "  ${GRN}●${RST} PostgreSQL     localhost:5432"
else
    echo -e "  ${RED}●${RST} PostgreSQL     Not responding"
fi

# Governance
echo ""
echo "--- Governance ---"
if curl -s http://localhost:8000/api/v1/governance/schemas &>/dev/null; then
    SCHEMA_COUNT=$(curl -s http://localhost:8000/api/v1/governance/schemas | grep -o 'schema_id' | wc -l)
    echo -e "  ${GRN}●${RST} Schemas loaded: $SCHEMA_COUNT"
else
    echo -e "  ${YLW}●${RST} Cannot verify schemas"
fi

# Quick state
if curl -s http://localhost:8000/api/v1/cognition/state &>/dev/null; then
    STATE=$(curl -s http://localhost:8000/api/v1/cognition/state | grep -o '"state":"[^"]*"' | head -1)
    echo -e "  ${BLU}●${RST} Cognition state: $STATE"
fi

echo ""
