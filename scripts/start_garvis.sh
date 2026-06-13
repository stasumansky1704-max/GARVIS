#!/usr/bin/env bash
###############################################################################
# GARVIS Start Script — Ubuntu WSL2 on Predator
# Starts: PostgreSQL, Ollama, GARVIS API
###############################################################################
set -euo pipefail

GARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GARVIS_DIR"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
BLU='\033[0;34m'
MAG='\033[0;35m'
RST='\033[0m'

info()  { echo -e "${BLU}[GARVIS]${RST} $*"; }
ok()    { echo -e "${GRN}[ OK ]${RST} $*"; }
warn()  { echo -e "${YLW}[WARN]${RST} $*"; }
fail()  { echo -e "${RED}[FAIL]${RST} $*"; }
header() { echo -e "${MAG}$*${RST}"; }

echo ""
header "============================================================"
header "  GARVIS — Starting Constitutional Cognition OS"
header "============================================================"
echo ""

# Check prerequisites
if ! docker info &>/dev/null; then
    fail "Docker is not running"
    echo "  Start Docker Desktop (Windows) or: sudo service docker start"
    exit 1
fi

if [ ! -f .env ]; then
    warn "No .env file — creating from template"
    cp .env.example .env
fi

STEP=0
step() { ((STEP++)); info "[$STEP/7] $*"; }

# Step 1: Build
step "Building GARVIS image..."
docker compose build garvis 2>&1 | tail -5
ok "Build complete"

# Step 2: Start infrastructure
step "Starting PostgreSQL + Ollama..."
docker compose up -d postgres ollama 2>&1 | tail -3

# Step 3: Wait for PostgreSQL
step "Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker compose exec -T postgres pg_isready -U garvis -d garvis &>/dev/null; then
        ok "PostgreSQL ready"
        break
    fi
    echo -n "."
    sleep 2
done
if ! docker compose exec -T postgres pg_isready -U garvis -d garvis &>/dev/null; then
    fail "PostgreSQL failed to start"
    docker compose logs postgres --tail=20
    exit 1
fi

# Step 4: Wait for Ollama
step "Waiting for Ollama..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        ok "Ollama ready"
        break
    fi
    echo -n "."
    sleep 2
done
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    fail "Ollama failed to start"
    docker compose logs ollama --tail=20
    exit 1
fi

# Step 5: Start GARVIS API
step "Starting GARVIS API..."
docker compose up -d garvis 2>&1 | tail -3

# Step 6: Wait for API
step "Waiting for GARVIS API..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/v1/status/health &>/dev/null; then
        ok "GARVIS API ready"
        break
    fi
    echo -n "."
    sleep 2
done
if ! curl -s http://localhost:8000/api/v1/status/health &>/dev/null; then
    fail "GARVIS API failed to start"
    docker compose logs garvis --tail=20
    exit 1
fi

# Step 7: Verify governance
step "Verifying governance schemas..."
SCHEMA_COUNT=$(curl -s http://localhost:8000/api/v1/governance/schemas | grep -o 'schema_id' | wc -l)
if [ "$SCHEMA_COUNT" -gt 0 ]; then
    ok "$SCHEMA_COUNT governance schemas loaded"
else
    warn "Could not verify schema count"
fi

# Summary
echo ""
header "============================================================"
header "  GARVIS IS RUNNING"
header "============================================================"
echo ""
echo -e "  ${GRN}API${RST}        http://localhost:8000"
echo -e "  ${GRN}Health${RST}     http://localhost:8000/api/v1/status/health"
echo -e "  ${GRN}Schemas${RST}    http://localhost:8000/api/v1/governance/schemas"
echo -e "  ${GRN}Ollama${RST}     http://localhost:11434"
echo -e "  ${GRN}Postgres${RST}   localhost:5432"
echo ""
echo -e "  ${YLW}Commands:${RST}"
echo -e "    ${BLU}./scripts/status_garvis.sh${RST}  — Check status"
echo -e "    ${BLU}./scripts/stop_garvis.sh${RST}    — Stop"
echo -e "    ${BLU}docker compose logs -f garvis${RST} — View logs"
echo ""
