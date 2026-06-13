#!/bin/bash
# backup_garvis.sh -- Backup GARVIS runtime state
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$PROJECT_DIR/backups/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

echo "============================================"
echo "  GARVIS Backup"
echo "============================================"
echo "  Timestamp: $TIMESTAMP"
echo "  Destination: $BACKUP_DIR"
echo ""

# Git state
if [ -d .git ]; then
    echo "  Saving git state..."
    git log --oneline -5 > "$BACKUP_DIR/git_state.txt" 2>/dev/null || true
    git rev-parse HEAD > "$BACKUP_DIR/git_commit.txt" 2>/dev/null || true
    git status --short > "$BACKUP_DIR/git_status.txt" 2>/dev/null || true
else
    echo "  (no git repo)"
fi

# Docker volumes (if running)
if docker compose ps -q 2>/dev/null | grep -q .; then
    echo "  Exporting Docker volumes..."
    docker run --rm \
        -v garvis_postgres_data:/data \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf /backup/postgres.tar.gz -C /data . 2>/dev/null \
        && echo "    postgres.tar.gz OK" \
        || echo "    postgres backup skipped"
else
    echo "  (services not running -- skipping volume backup)"
fi

# Config
echo "  Saving configuration..."
cp .env "$BACKUP_DIR/env" 2>/dev/null || echo "    (no .env file)"
cp docker-compose.yml "$BACKUP_DIR/" 2>/dev/null || true
cp requirements.txt "$BACKUP_DIR/" 2>/dev/null || true

# Governance schemas
echo "  Saving governance schemas..."
if [ -d governance/schemas ]; then
    tar czf "$BACKUP_DIR/governance_schemas.tar.gz" governance/schemas/
    echo "    governance_schemas.tar.gz OK"
else
    echo "    (no governance/schemas directory)"
fi

# Logs
echo "  Saving recent logs..."
docker compose logs --no-color > "$BACKUP_DIR/docker_logs.txt" 2>/dev/null || echo "    (logs unavailable)"

echo ""
echo "Backup complete: $BACKUP_DIR"
echo ""
echo "  Contents:"
ls -lh "$BACKUP_DIR" | tail -n +2
echo ""
echo "To restore: ./scripts/rollback_garvis.sh $TIMESTAMP"
