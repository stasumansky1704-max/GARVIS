#!/usr/bin/env bash
###############################################################################
# GARVIS Installation Script — Ubuntu WSL2 on Predator
# Run once: ./scripts/install.sh
###############################################################################
set -euo pipefail

GARVIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GARVIS_DIR"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
BLU='\033[0;34m'
RST='\033[0m'

info()  { echo -e "${BLU}[GARVIS]${RST} $*"; }
ok()    { echo -e "${GRN}[OK]${RST}   $*"; }
warn()  { echo -e "${YLW}[WARN]${RST} $*"; }
fail()  { echo -e "${RED}[FAIL]${RST}  $*"; }

echo ""
echo "============================================================"
echo "  GARVIS — Constitutional Governed Cognition OS"
echo "  Installation for Ubuntu WSL2"
echo "============================================================"
echo ""

# 1. Check OS
info "Checking operating system..."
if grep -q "microsoft" /proc/version 2>/dev/null; then
    ok "WSL2 detected"
else
    warn "Not running in WSL — continuing anyway"
fi

# 2. Check Docker
info "Checking Docker..."
if ! command -v docker &>/dev/null; then
    fail "Docker not installed"
    echo ""
    echo "Install Docker Desktop with WSL2 integration:"
    echo "  https://docs.docker.com/desktop/install/windows-install/"
    echo "Or install Docker Engine in WSL2:"
    echo "  sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin"
    exit 1
fi
ok "Docker found: $(docker --version)"

# 3. Check Docker Compose
info "Checking Docker Compose..."
if docker compose version &>/dev/null; then
    ok "Docker Compose v2 found"
else
    fail "Docker Compose not found"
    echo "Install: sudo apt-get install -y docker-compose-plugin"
    exit 1
fi

# 4. Check Python3
info "Checking Python3..."
if command -v python3 &>/dev/null; then
    PYTHON_VER=$(python3 --version 2>&1)
    ok "$PYTHON_VER"
else
    fail "Python3 not found — installing..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi

# 5. Create .env
info "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    ok "Created .env from template"
    warn "Review .env and customize if needed"
else
    ok ".env already exists"
fi

# 6. Make scripts executable
chmod +x scripts/*.sh 2>/dev/null || true
ok "Scripts made executable"

# 7. Create runtime directories
mkdir -p logs snapshots backups
ok "Runtime directories created"

# 8. Pull Ollama model (optional, can be done later)
echo ""
info "Pull default Ollama model? (llama3.1 — ~4.7GB) [y/N]"
read -r PULL_MODEL
if [ "$PULL_MODEL" = "y" ] || [ "$PULL_MODEL" = "Y" ]; then
    info "Pulling llama3.1..."
    docker run --rm -v garvis_ollama_data:/root/.ollama --entrypoint ollama ollama/ollama:latest pull llama3.1 || \
        warn "Could not pull model — will be pulled on first start"
else
    warn "Skipping model pull — will be pulled on first use"
fi

# 9. Summary
echo ""
echo "============================================================"
echo "  Installation Complete"
echo "============================================================"
echo ""
echo "  GARVIS directory: $GARVIS_DIR"
echo "  Config:           $GARVIS_DIR/.env"
echo ""
echo "  Next steps:"
echo "    ./scripts/start_garvis.sh   — Start GARVIS"
echo "    ./scripts/status_garvis.sh  — Check status"
echo "    ./scripts/stop_garvis.sh    — Stop GARVIS"
echo ""
echo "  Dashboard: https://bevtspn25lfso.kimi.page (remote)"
echo "  API:       http://localhost:8000 (local)"
echo ""
echo "  Docs:"
echo "    cat OPERATOR_GUIDE.md"
echo "    cat DEPLOYMENT_READY.md"
echo ""
