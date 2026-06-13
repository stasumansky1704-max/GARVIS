# GARVIS Operator Guide

Constitutional Governed Cognition Operating System -- Local Deployment

---

## Quick Start

### Prerequisites

- Docker Engine 24.0+
- Docker Compose v2+
- Linux / WSL2 (Windows)

### First-Time Installation

```bash
./scripts/install.sh
```

This checks prerequisites, creates `.env` from the template, and prepares directories.

### Start GARVIS

```bash
./scripts/start_garvis.sh
```

This builds the image, starts all services (PostgreSQL, Ollama, GARVIS API), waits for health checks, and reports status.

### Check Status

```bash
./scripts/status_garvis.sh
```

Shows container status, health checks, governance schema count, and resource usage.

### Stop GARVIS

```bash
./scripts/stop_garvis.sh
```

Graceful shutdown preserving all data in Docker volumes.

### Restart GARVIS

```bash
./scripts/restart_garvis.sh
```

Stops, waits 3 seconds, then starts again.

---

## Daily Operations

### View Logs

```bash
# GARVIS API logs
docker compose logs -f garvis

# Ollama LLM logs
docker compose logs -f ollama

# PostgreSQL logs
docker compose logs -f postgres

# All services
docker compose logs -f
```

### Health Check

```bash
./scripts/health_check.py
```

Validates all required services (API, Ollama, schemas) and optional analytics endpoint.

### Backup

```bash
./scripts/backup_garvis.sh
```

Creates a timestamped backup in `backups/` containing:

- Git state (HEAD, recent commits, status)
- Docker volume dump (PostgreSQL data)
- Configuration files (`.env`, `docker-compose.yml`)
- Governance schemas archive
- Recent Docker logs

Backups are stored in `backups/YYYYMMDD_HHMMSS/`.

### Restore / Rollback

```bash
# List available backups
./scripts/rollback_garvis.sh

# Rollback to a specific backup
./scripts/rollback_garvis.sh 20240115_143022
```

Requires typing `yes` to confirm. Restores configuration and PostgreSQL volume data.

---

## Service Architecture

```
+--------------------+      +--------------------+      +--------------------+
|   GARVIS API       |----->|   PostgreSQL       |      |   Ollama           |
|   :8000            |      |   :5432            |      |   :11434           |
|                    |      |                    |      |                    |
| - 57 API endpoints |      | - Governance data  |      | - Local LLM        |
| - 10 dashboards    |      | - Audit logs       |      |   inference        |
| - 28 schemas       |      | - Memory state     |      | - Model mgmt       |
| - 485 tests        |      | - Snapshots        |      |                    |
+--------------------+      +--------------------+      +--------------------+
         |                            |                          |
         +----------------------------+--------------------------+
                                      |
                           garvis_network (bridge)
```

| Service | Host Port | Internal Hostname | Purpose |
|---------|-----------|-------------------|---------|
| GARVIS API | 8000 | `garvis-api` | REST API + dashboards |
| PostgreSQL | 5432 | `garvis-postgres` | Persistent data storage |
| Ollama | 11434 | `garvis-ollama` | Local LLM inference |

---

## API Endpoints

### Status & Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/status/` | GET | System status and version |
| `/api/v1/status/health` | GET | Health check (used by Docker) |

### Governance

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/governance/schemas` | GET | List all governance schemas |
| `/api/v1/governance/schemas/{id}` | GET | Get specific schema |
| `/api/v1/governance/validate` | POST | Validate against a schema |

### Cognition

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cognition/state` | GET | Current cognition state |
| `/api/v1/cognition/process` | POST | Submit processing request |

### Analytics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/analytics/overview` | GET | System analytics overview |

### Audit

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/audit/logs` | GET | Audit log entries |

---

## Ollama Operations

### Pull a Model

```bash
docker compose exec ollama ollama pull llama3.1
```

### List Available Models

```bash
curl http://localhost:11434/api/tags
```

### Pull Additional Models

```bash
docker compose exec ollama ollama pull mistral
docker compose exec ollama ollama pull codellama
docker compose exec ollama ollama pull phi3
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `garvis` | Database username |
| `POSTGRES_PASSWORD` | `garvis_local` | Database password |
| `POSTGRES_DB` | `garvis` | Database name |
| `OLLAMA_DEFAULT_MODEL` | `llama3.1` | Default LLM model |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `GARVIS_ENV` | `local` | Environment label |

### Change Default Model

Edit `.env`:

```bash
OLLAMA_DEFAULT_MODEL=mistral
```

Then restart:

```bash
./scripts/restart_garvis.sh
```

---

## Troubleshooting

### Service Not Starting

```bash
# Check container status
docker compose ps

# View service logs
docker compose logs <service>

# Check for port conflicts
ss -tlnp | grep -E '8000|5432|11434'
```

### API Not Responding

```bash
# Direct health check
curl http://localhost:8000/api/v1/status/health

# Check GARVIS logs
docker compose logs --tail=50 garvis

# Verify PostgreSQL is accessible
docker compose exec postgres pg_isready -U garvis
```

### Database Issues

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U garvis -d garvis

# Check migrations ran
docker compose exec postgres psql -U garvis -d garvis -c "\dt"

# Reset database (WARNING: destroys all data)
docker compose down -v
docker compose up -d postgres
```

### Ollama Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Pull model manually
docker compose exec ollama ollama pull llama3.1

# View Ollama logs
docker compose logs ollama
```

### Port Already in Use

If ports 8000, 5432, or 11434 are taken:

1. Edit `docker-compose.yml` to change the host port mapping:

```yaml
ports:
  - "8080:8000"  # Map host 8080 to container 8000
```

2. Update `.env` accordingly.

3. Restart:

```bash
./scripts/restart_garvis.sh
```

### Rebuild After Code Changes

```bash
# Rebuild GARVIS image from scratch
docker compose build --no-cache garvis

# Restart with new image
./scripts/start_garvis.sh
```

---

## File Locations

| Path | Purpose |
|------|---------|
| `.env` | Environment configuration |
| `.env.local` | Default environment template |
| `docker-compose.yml` | Service orchestration |
| `Dockerfile` | GARVIS image build |
| `requirements.txt` | Python dependencies |
| `governance/schemas/` | 28 governance schemas |
| `backups/` | Timestamped backups |
| `logs/` | Local log files |
| `snapshots/` | Runtime snapshots |
| `scripts/` | Operational scripts |

---

## Script Reference

| Script | Purpose |
|--------|---------|
| `scripts/install.sh` | First-time setup |
| `scripts/start_garvis.sh` | Start all services |
| `scripts/stop_garvis.sh` | Stop all services |
| `scripts/restart_garvis.sh` | Restart services |
| `scripts/status_garvis.sh` | Show system status |
| `scripts/health_check.py` | Validate service health |
| `scripts/backup_garvis.sh` | Create backup |
| `scripts/rollback_garvis.sh` | Restore from backup |

---

## Emergency Procedures

### Complete Reset (DESTROYS ALL DATA)

```bash
# Stop everything
docker compose down -v

# Remove all GARVIS data
docker volume rm garvis_postgres_data garvis_ollama_data garvis_logs garvis_snapshots

# Restart fresh
./scripts/start_garvis.sh
```

### Recover from Failed Start

```bash
# Check logs for errors
docker compose logs --tail=100 garvis

# Restart individual service
docker compose restart garvis

# Force rebuild
docker compose build --no-cache garvis
docker compose up -d garvis
```

---

*GARVIS -- Constitutional Governed Cognition Operating System*
*Local Deployment Package*
