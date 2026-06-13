# GARVIS — Local Installation Guide
## Ubuntu WSL2 on Predator

**This guide takes you from the existing `~/GARVIS` directory to a fully running GARVIS system.**

---

## CURRENT STATE (What Exists on Predator)

```
~/GARVIS/
├── audit/                  # Existing audit files
├── docs/                   # Existing docs
├── emergency_governance/   # Emergency governance
├── intercepts/             # Intercepts
├── knowledge_base/         # Knowledge base
├── logs/                   # Existing logs
├── memory/                 # Existing memory
├── runtime/                # Existing runtime
├── sandbox/                # Sandbox
├── telemetry/              # Telemetry
└── windmill/               # Windmill
```

## TARGET STATE (What Will Exist)

```
~/GARVIS/
├── audit/                  # ← Keep existing
├── docs/                   # ← Keep existing
├── knowledge_base/         # ← Keep existing
├── logs/                   # ← Keep existing
├── memory/                 # ← Keep existing
├── runtime/                # ← Keep existing
├── sandbox/                # ← Keep existing
├── telemetry/              # ← Keep existing
├── windmill/               # ← Keep existing
│
├── api/                    # ← NEW: FastAPI backend (81 endpoints)
│   ├── main.py
│   ├── routers/
│   └── static/             # ← Dashboard build
│
├── analytics/              # ← NEW: 5 analytics modules
├── cognition/              # ← NEW: State machine, collaboration, strategy
├── dashboard/              # ← NEW: React dashboard source
│   ├── src/
│   └── dist/               # ← Production build
├── database/               # ← NEW: PostgreSQL schemas
├── demos/                  # ← NEW: 4 demo scripts
├── governance/             # ← NEW: 28 YAML schemas
│   └── schemas/
├── inference/              # ← NEW: Ollama wrapper
├── mission_control/        # ← NEW: Command center, workflow approval
├── models/                 # ← NEW: Pydantic models
├── monitoring/             # ← NEW: Alerts, topology
├── projects/               # ← NEW: 7-project governance
├── scripts/                # ← NEW: 6 operational scripts
├── traceability/           # ← NEW: Lineage, audit, renderer
├── workflows/              # ← NEW: Workflow engine
│
├── tests/                  # ← NEW: ~960 tests
├── docker-compose.yml      # ← Docker orchestration
├── Dockerfile              # ← GARVIS container
├── requirements.txt        # ← Python dependencies
├── .env                    # ← Environment config
├── garvis_cli.py           # ← CLI entry point
├── OPERATOR_GUIDE.md       # ← Operator reference
└── README.md               # ← System documentation
```

---

## PREREQUISITES

### 1. Docker Desktop with WSL2

```bash
# Verify Docker is running
docker info

# Verify Docker Compose v2
docker compose version
# Should show: Docker Compose version v2.x.x

# If not installed:
# Download from: https://docs.docker.com/desktop/install/windows-install/
# Enable WSL2 integration in Docker Desktop settings
```

### 2. Python 3.12+

```bash
python3 --version
# Should show: Python 3.12.x

# If not installed:
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip
```

---

## STEP-BY-STEP INSTALLATION

### Step 1: Extract the GARVIS package

```bash
# The garvis-complete.tar.gz file contains the full project
cd ~
tar -xzf garvis-complete.tar.gz

# This creates or updates the ~/GARVIS directory with all new files
# Your existing directories (audit, docs, knowledge_base, etc.) are preserved
```

### Step 2: Install

```bash
cd ~/GARVIS
./scripts/install.sh
```

This will:
- Check Docker, Docker Compose, Python3
- Create `.env` from `.env.example`
- Make scripts executable
- Create runtime directories (logs/, snapshots/, backups/)

### Step 3: Start GARVIS

```bash
./scripts/start_garvis.sh
```

This will:
1. Build the GARVIS Docker image
2. Start PostgreSQL (waits for healthy)
3. Start Ollama (waits for healthy)
4. Start GARVIS API (waits for healthy)
5. Verify governance schemas loaded

Expected output:
```
[1/7] Building GARVIS image...
[2/7] Starting PostgreSQL + Ollama...
[3/7] Waiting for PostgreSQL... ........ OK
[4/7] Waiting for Ollama... ........ OK
[5/7] Starting GARVIS API...
[6/7] Waiting for GARVIS API... ........ OK
[7/7] Verifying governance schemas... 28 schemas loaded

============================================================
  GARVIS IS RUNNING
============================================================
  API:        http://localhost:8000
  Health:     http://localhost:8000/api/v1/status/health
  Schemas:    http://localhost:8000/api/v1/governance/schemas
  Ollama:     http://localhost:11434
  Postgres:   localhost:5432
```

### Step 4: Verify (Health Check)

```bash
./scripts/health_check.sh
```

Expected output:
```
[GARVIS] Health Check
========================
  PASS GARVIS API
  PASS Ollama
  PASS Governance
  PASS Cognition
  PASS Memory
  PASS Traceability
  PASS Audit
  PASS Analytics
  PASS Command Center
All services healthy
```

### Step 5: Pull Ollama Model (First Time)

```bash
# Pull llama3.1 (~4.7GB) — this enables real inference
docker compose exec ollama ollama pull llama3.1

# Verify
http://localhost:11434/api/tags
# Should show: {"models":[{"name":"llama3.1:latest"}]}
```

### Step 6: Run Tests

```bash
# Install test dependencies
pip3 install pytest pytest-asyncio httpx

# Run tests
cd ~/GARVIS
python3 -m pytest tests/ -q

# Expected: ~960 tests passed
```

---

## DAILY OPERATION

### Check Status
```bash
./scripts/status_garvis.sh
```

### View Logs
```bash
docker compose logs -f garvis      # GARVIS logs
docker compose logs -f ollama      # Ollama logs
docker compose logs -f postgres    # PostgreSQL logs
```

### Use the CLI
```bash
# Check status
python3 garvis_cli.py status

# List governance schemas
python3 garvis_cli.py schemas

# Submit a governed cognition request
python3 garvis_cli.py cognize --prompt "Explain governance-first architecture"
```

### Run Demos
```bash
python3 demos/demo_governed_cognition.py    # Full pipeline demo
python3 demos/demo_fail_closed.py           # Fail-closed demo
python3 demos/demo_memory_influence.py      # Memory tracking demo
python3 demos/demo_state_transitions.py     # State machine demo
```

---

## STOPPING

```bash
./scripts/stop_garvis.sh
```

This stops all containers but **preserves data** (PostgreSQL, Ollama models, logs).

To completely remove everything (including data):
```bash
docker compose down -v
```

---

## TROUBLESHOOTING

### Docker not running
```bash
# WSL2: Docker Desktop must be running on Windows
# Or use Docker Engine:
sudo service docker start
```

### PostgreSQL won't start
```bash
# Check logs
docker compose logs postgres --tail=20

# Reset PostgreSQL data (WARNING: deletes all data)
docker compose down -v
docker volume rm garvis_garvis_postgres_data
./scripts/start_garvis.sh
```

### Ollama won't start
```bash
# Check if port 11434 is in use
sudo lsof -i :11434

# Check logs
docker compose logs ollama --tail=20
```

### GARVIS API won't start
```bash
# Check logs
docker compose logs garvis --tail=30

# Verify schema files exist
ls governance/schemas/*.yml | wc -l
# Should show: 28

# Rebuild and restart
docker compose build --no-cache garvis
docker compose up -d garvis
```

### Port conflicts
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Edit .env to change ports if needed
# API_PORT=8001
# Then update docker-compose.yml ports section
```

---

## FILE MANIFEST (What Gets Installed)

### New Directories (14 modules)
| Directory | Files | Purpose |
|-----------|-------|---------|
| `api/` | 17 | FastAPI backend — 81 endpoints |
| `analytics/` | 6 | Cognition analytics engine |
| `cognition/` | 8 | State machine, collaboration, strategy |
| `dashboard/` | 2 | React dashboard (source + build) |
| `database/` | 3 | PostgreSQL migrations |
| `demos/` | 5 | 4 demo scripts + utils |
| `governance/` | 6 | Schema loader, registry, validator, 28 YAML schemas |
| `inference/` | 5 | Ollama client, prompt mediator, executor |
| `mission_control/` | 5 | Command center, workflow approval, ecosystem |
| `models/` | 6 | Pydantic v2 data models |
| `monitoring/` | 3 | Alert engine, system topology |
| `projects/` | 6 | 7-project governance with context isolation |
| `traceability/` | 7 | Lineage, audit, renderer (4 formats) |
| `workflows/` | 5 | Approval-gated workflow engine |

### New Root Files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | 3-service Docker orchestration |
| `Dockerfile` | GARVIS container build |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment template |
| `garvis_cli.py` | CLI entry point (7 commands) |
| `OPERATOR_GUIDE.md` | Daily operator reference |
| `README.md` | System documentation |

### Scripts (`scripts/`)
| Script | Purpose |
|--------|---------|
| `install.sh` | First-time setup |
| `start_garvis.sh` | Start all services |
| `stop_garvis.sh` | Stop all services |
| `restart_garvis.sh` | Restart |
| `status_garvis.sh` | Show full status |
| `health_check.sh` | Validate all 9 services |

---

## SYSTEM CAPABILITIES (Once Running)

### Governance
- 28 YAML schemas, 87 policies, 56 constraints
- 39 hard-stop constraints on inference
- 4 forbidden state patterns (auto-FAIL_CLOSED)
- 10 alert rules with severity levels

### API (81 Endpoints)
- `/api/v1/governance/*` — Schema management
- `/api/v1/cognition/*` — State machine, sessions
- `/api/v1/memory/*` — Episodic memory
- `/api/v1/traceability/*` — Traces, graphs
- `/api/v1/audit/*` — Events, violations, SSE stream
- `/api/v1/analytics/*` — Metrics, trends, pressure
- `/api/v1/command-center/*` — Mission Control
- `/api/v1/collaboration/*` — Governed collaboration
- `/ws` — Real-time updates

### Dashboard (10 Views)
Overview, Governance, Cognition, Memory, Traceability, Audit, Analytics, Ecosystem, Alerts, Topology

### Projects (7)
GARVIS, AlphaFlow, NOVA, TeachFlow, Bella & Friends, YouTube Engine, General Ops

### Tests (~960)
All passing, covering: models, governance, state machine, memory, traceability, inference, workflows, projects, collaboration, analytics, monitoring, production, mission control, ecosystem

---

## WHAT WAS PRESERVED

Your existing directories are **untouched**:
- `audit/`, `docs/`, `knowledge_base/`, `logs/`, `memory/`
- `runtime/`, `sandbox/`, `telemetry/`, `windmill/`
- `emergency_governance/`, `intercepts/`

These remain in place. GARVIS integrates alongside them.

---

**GARVIS — Constitutional Governed Cognition OS**
**~960 Tests | 81 Endpoints | 124 Files | 28 Schemas | 7 Projects**
**Constitutional Doctrine: ABSOLUTELY PRESERVED**
