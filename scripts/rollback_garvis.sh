#!/bin/bash
# rollback_garvis.sh -- Rollback GARVIS to previous state
# Usage: ./scripts/rollback_garvis.sh <backup_timestamp>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/rollback_garvis.sh <backup_timestamp>"
    echo ""
    echo "Available backups:"
    if [ -d backups ] && [ "$(ls -A backups 2>/dev/null)" ]; then
        ls -1t backups/ | head -10
    else
        echo "  No backups found"
    fi
    exit 1
fi

BACKUP_TIMESTAMP=$1
BACKUP_DIR="backups/$BACKUP_TIMESTAMP"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: Backup not found: $BACKUP_DIR"
    exit 1
fi

echo "============================================"
echo "  GARVIS Rollback"
echo "============================================"
echo "  Backup: $BACKUP_TIMESTAMP"
echo ""

# Show git state at backup time
if [ -f "$BACKUP_DIR/git_state.txt" ]; then
    echo "Git state at backup time:"
    cat "$BACKUP_DIR/git_state.txt"
    echo ""
fi

# Require explicit confirmation
echo "WARNING: This will ROLLBACK GARVIS to backup: $BACKUP_TIMESTAMP"
echo "Current services will be stopped and configuration restored."
echo ""
read -r -p "Type 'yes' to proceed: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

echo ""
echo "[1/3] Stopping services..."
docker compose down --volumes=false 2>/dev/null || true

echo "[2/3] Restoring configuration..."
cp "$BACKUP_DIR/env" .env 2>/dev/null || echo "  (no .env in backup)"
if [ -f "$BACKUP_DIR/docker-compose.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.yml" . 2>/dev/null || true
fi

echo "[3/3] Restoring Docker volumes..."
if [ -f "$BACKUP_DIR/postgres.tar.gz" ]; then
    docker run --rm \
        -v garvis_postgres_data:/data \
        -v "$BACKUP_DIR":/backup \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/postgres.tar.gz -C /data" \
        2>/dev/null && echo "  postgres volume restored" \
        || echo "  (postgres volume restore skipped)"
else
    echo "  (no postgres volume backup found)"
fi

echo ""
echo "Rollback complete."
echo "Run ./scripts/start_garvis.sh to restart services."
