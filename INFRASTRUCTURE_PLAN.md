# Infrastructure Plan

**Project:** Research Data Pipeline Infrastructure  
**Author:** Tucker Paron  
**Last Updated:** 2026-05-03  
**Status:** Pre-implementation (to be built Tuesday May 6)

See DECISIONS.md for the reasoning behind every choice made here.

---

## System Overview

```
[CSV via generate_data.py]
        ↓
[Pipeline Container]  →  [PostgreSQL]  ←  [FastAPI Container]
                                                   ↓
                                            [nginx Container]  ←  [Frontend (static HTML)]
                                                   ↓
                                            Browser / Client
```

**Local:** Docker Compose orchestrates all services.  
**Cloud:** ECS Fargate runs API + pipeline containers; RDS runs PostgreSQL; ALB replaces nginx.

---

## What Each Container Does

It helps to think of each container as a separate process with a single job. They share a network inside Docker Compose but are otherwise isolated.

| Container | Job | Runs how long | Talks to |
|-----------|-----|---------------|----------|
| `db` | Stores all data. Official Postgres image — no custom code written. | Forever | — |
| `pipeline` | Generates CSV → inserts sensor readings into `db` → runs anomaly detection → writes results back to `db`. Runs once at startup. | Runs once, then exits | `db` |
| `api` | Listens for HTTP requests. When `/api/anomalies` is called, queries `db` and returns JSON. Never generates data. | Forever | `db` |
| `nginx` | The front door. Routes all traffic on port 80: `/api/` goes to `api`, `/` serves the static HTML file baked into this container. Never touches the database. | Forever | `api` (proxy), filesystem (static files) |
| frontend | Not its own container — `index.html` is copied into the `nginx` container at build time. The browser downloads it from nginx, then JS inside it makes fetch() calls to `/api/`. | — | Calls `nginx` at runtime |

**Traffic flow:**
```
Browser → nginx:80
    ├── /api/* → FastAPI:8000 → PostgreSQL:5432
    └── /      → static index.html (served directly by nginx)
                    └── JS fetch('/api/anomalies') → [same flow as above]
```

**The frontend is "static HTML" but data is live.** The HTML file has no data baked in. JavaScript inside it calls the API on page load and every 30 seconds. "Static" means no build step or framework — not that the data is frozen.

---

## What Each Terraform File Does

Terraform reads all `.tf` files in a directory together — the split is organizational, not functional.

| File | Purpose |
|------|---------|
| `backend.tf` | Tells Terraform where to store its state file (S3 bucket + DynamoDB lock table). Must be configured before `terraform init`. Without this, state lives only on your laptop and the CI/CD pipeline can't share it. |
| `variables.tf` | Declares what inputs the config accepts — like a function signature. Defines names, types, descriptions, and optional defaults. Does not contain actual values. |
| `terraform.tfvars` | The actual values for declared variables (DB password, AWS region, project name). **Gitignored — never committed.** |
| `main.tf` | The resource definitions — VPC, subnets, security groups, RDS, ECS cluster, ECS task definitions, ALB, ECR repos, IAM roles. The bulk of the Terraform work. |
| `outputs.tf` | What to print after `terraform apply` — the ALB DNS name (your live app URL), RDS endpoint, ECR repository URLs. Like return values from a function. |

**Typical workflow:**
```bash
terraform init          # reads backend.tf, downloads providers
terraform plan          # shows what will be created/changed/destroyed
terraform apply         # actually provisions resources on AWS
terraform destroy       # tears everything down (use with care)
```

---

## Repository Structure

```
hks/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions CI/CD
├── services/
│   ├── api/                    # FastAPI REST API
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py             # App entrypoint
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── database.py         # DB connection
│   │   └── tests/
│   │       └── test_api.py
│   └── pipeline/               # Ingest + anomaly detection
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── run_pipeline.py     # Orchestrates ingest → detect → store
│       └── tests/
│           └── test_pipeline.py
├── frontend/
│   └── index.html              # Single-file UI
├── nginx/
│   └── nginx.conf
├── db/
│   └── init.sql                # Schema creation
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── docker-compose.yml
├── .env.example
├── .gitignore
├── 1_README.md                 # Original exercise spec (do not modify)
├── 2_generate_data.py          # Provided — use as-is
├── 3_anomaly_detector.py       # Provided — use as-is
├── DATA_GENERATOR_GUIDE.md     # Provided
├── DECISIONS.md                # Architecture decision log
└── INFRASTRUCTURE_PLAN.md      # This file
```

---

## Database Schema

Two tables. Schema lives in `db/init.sql` and is run automatically by the PostgreSQL Docker image on first startup.

```sql
CREATE TABLE IF NOT EXISTS sensor_readings (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL,
    sensor_id   VARCHAR(50) NOT NULL,
    temperature FLOAT,
    humidity    FLOAT,
    pressure    FLOAT,
    location    VARCHAR(100),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_id ON sensor_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp);

CREATE TABLE IF NOT EXISTS anomalies (
    id               SERIAL PRIMARY KEY,
    sensor_data_id   INTEGER REFERENCES sensor_readings(id),
    anomaly_type     VARCHAR(100) NOT NULL,
    confidence_score FLOAT NOT NULL,
    detected_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_anomalies_sensor_data_id ON anomalies(sensor_data_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at ON anomalies(detected_at);
```

**Column sources:**
- `sensor_readings` columns map 1:1 to `2_generate_data.py`'s `save_to_csv` fieldnames: `['id', 'timestamp', 'sensor_id', 'temperature', 'humidity', 'pressure', 'location']`
- `anomalies` columns map 1:1 to the dict returned by `3_anomaly_detector.py`'s `detect_anomalies()`: `sensor_data_id`, `anomaly_type`, `confidence_score`, `detected_at`
- `ingested_at` is the one addition not in the source scripts — a DB-generated timestamp for when the row was inserted, distinct from `timestamp` (when the sensor reading was taken). Useful if the pipeline is ever run more than once.

**Design notes:**
- `id` is DB-generated (`SERIAL`) — the CSV also has an `id` field but it must be skipped on insert. If the pipeline runs twice, the CSV ids restart at 1 and would conflict with existing rows. Let PostgreSQL own the primary key.
- Indexes on `sensor_id` and `timestamp` support the API query pattern (filter by sensor + date range)
- `confidence_score` stores the raw z-score from `3_anomaly_detector.py` — no normalization
- `detected_at` is when the detector ran, not when the reading was taken; `sensor_readings.timestamp` is when the reading was taken

---

## Services

### 1. PostgreSQL (`db`)

- Image: `postgres:15-alpine`
- Port: 5432 (internal only — not exposed to host in production)
- Volume: `postgres_data` named volume for persistence between restarts
- Init: `db/init.sql` mounted to `/docker-entrypoint-initdb.d/`
- Credentials: via environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`)

---

### 2. Pipeline (`pipeline`)

**What it does:**
1. Runs `2_generate_data.py` to produce a CSV (10,000 observations, 3% anomaly rate)
2. Reads the CSV and bulk-inserts rows into `sensor_readings`
3. Reads all `sensor_readings` from DB, runs `3_anomaly_detector.py`
4. Bulk-inserts anomaly results into `anomalies`
5. Exits cleanly

**Key implementation notes:**
- Use `psycopg2` for direct DB writes (no ORM overhead for bulk insert)
- Use `COPY` or `executemany` for >10k row inserts — do not insert one row at a time
- Import `AnomalyDetector` from `3_anomaly_detector.py` directly (do not rewrite the algorithm)
- Wait for DB to be ready before running (use a retry loop or `depends_on` with healthcheck)

**Trigger:** Runs once on `docker compose up`, then exits. Can be re-run with `docker compose run pipeline`.

---

### 3. API (`api`)

**Framework:** FastAPI + SQLAlchemy + psycopg2

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/api/anomalies` | Query anomalies (see below) |

**`GET /api/anomalies` query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start` | ISO 8601 date | No | Filter anomalies detected after this date |
| `end` | ISO 8601 date | No | Filter anomalies detected before this date |
| `sensor_id` | string | No | Filter by sensor ID (e.g. `TEMP_001`) |
| `limit` | int | No | Max results (default 100) |

**Response shape:**
```json
[
  {
    "id": 1,
    "sensor_data_id": 42,
    "anomaly_type": "temperature_anomaly",
    "confidence_score": 3.74,
    "detected_at": "2026-05-06T10:00:00Z",
    "sensor_id": "TEMP_001",
    "timestamp": "2026-05-05T14:23:00Z",
    "location": "lab_a"
  }
]
```

**Note:** The response joins `anomalies` with `sensor_readings` to include sensor context — the frontend needs `sensor_id` and `timestamp` to display a useful table.

---

### 4. Frontend

Single static HTML file. No build step.

**Displays:**
- Table of recent anomalies (last 100 by default)
- Columns: Detected At, Sensor ID, Location, Anomaly Type, Confidence Score
- Simple filter inputs for Sensor ID and date range (calls the API on change)
- Auto-refreshes every 30 seconds

**Implementation:** Vanilla JS `fetch()` to `GET /api/anomalies`. Renders rows into a `<table>`. Hosted by nginx from the container filesystem.

---

### 5. nginx

Routes all traffic entering on port 80:
- `location /api/` → proxy to `api:8000`
- `location /docs` → proxy to `api:8000/docs` (FastAPI auto-docs)
- `location /` → serve static files from `/usr/share/nginx/html/`

`nginx.conf` key settings:
```nginx
upstream api {
    server api:8000;
}

server {
    listen 80;

    location /api/ {
        proxy_pass http://api/api/;
    }

    location /docs {
        proxy_pass http://api/docs;
    }

    location / {
        root /usr/share/nginx/html;
        index index.html;
    }
}
```

---

## Docker Compose

**Services and startup order:**

```
db (healthcheck: pg_isready)
  └── pipeline (depends_on db healthy, runs once and exits)
  └── api (depends_on db healthy, stays up)
        └── nginx (depends_on api)
```

**Ports exposed to host:**
- `80` → nginx (main entry point)
- `5432` → postgres (for local DB inspection with psql or TablePlus)

**Named volume:** `postgres_data`

**Environment variables** (all from `.env`, never hardcoded):
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `API_HOST`, `API_PORT`

---

## Terraform (AWS)

**Resources to provision:**

| Resource | Service | Notes |
|----------|---------|-------|
| VPC + subnets | VPC | 2 public, 2 private subnets across 2 AZs |
| Internet Gateway | VPC | Public subnet egress |
| NAT Gateway | VPC | Private subnet egress for ECS tasks |
| Security Groups | EC2 | ALB → ECS, ECS → RDS |
| RDS PostgreSQL | RDS | `db.t3.micro`, single-AZ (cost), private subnet |
| ECS Cluster | ECS | Fargate launch type |
| ECS Task Definitions | ECS | One each for `api` and `pipeline` |
| ECS Service | ECS | `api` service behind ALB; `pipeline` as a one-shot task |
| ALB + Target Group | ELB | Routes `/api/*` to ECS, `/` to static (or ECS) |
| ECR Repositories | ECR | One each for `api`, `pipeline`, `frontend` |
| IAM Roles | IAM | ECS task execution role, ECS task role |
| S3 Bucket | S3 | Terraform remote state |
| DynamoDB Table | DynamoDB | Terraform state lock |

**State management:** Remote state in S3 with DynamoDB locking. `backend.tf` configured before `terraform init`.

**Variable inputs (via `terraform.tfvars`, gitignored):**
- `aws_region`, `db_password`, `db_username`, `project_name`

**Outputs:**
- ALB DNS name (the URL to demo the running system)
- RDS endpoint
- ECR repository URLs

---

## GitHub Actions CI/CD

**Trigger:** Push or PR merge to `main`

**Jobs:**

### `test` (runs on every PR)
1. Checkout code
2. Set up Python
3. Install dependencies
4. Run `pytest services/api/tests/` and `pytest services/pipeline/tests/`

### `build-and-deploy` (runs on merge to `main` only)
1. Configure AWS credentials (from GitHub Secrets)
2. Login to ECR
3. Build Docker images for `api`, `pipeline`, `frontend`
4. Tag and push to ECR
5. Update ECS service to force new deployment (pulls latest image)

**GitHub Secrets required:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REGISTRY`
- `DB_PASSWORD`

---

## Build Order for Tuesday

Work in this sequence to avoid blocked waiting:

1. **Repo structure** — create all directories and empty placeholder files (10 min)
2. **DB schema** — write `db/init.sql` (5 min)
3. **Docker Compose skeleton** — get `db` running and reachable (20 min)
4. **Pipeline service** — ingest CSV → DB → detect → store anomalies (45 min)
5. **API service** — FastAPI with `/health` and `/api/anomalies` (45 min)
6. **Frontend** — single HTML file fetching from API (30 min)
7. **nginx** — wire routing, verify end-to-end in browser (20 min)
8. **Tests** — basic unit tests for pipeline and API (30 min)
9. **Terraform** — AWS infrastructure (60 min)
10. **GitHub Actions** — CI/CD workflow (30 min)
11. **Deploy to AWS** — run `terraform apply`, push images, verify ALB URL (30 min)
12. **README** — architecture diagram, setup instructions, deployment guide (20 min)

**Total estimate: ~5.5 hours** — matches the exercise estimate, assumes no major blockers.

---

## Verification Checklist

Before submitting:

- [ ] `docker compose up` starts all services without errors
- [ ] Pipeline runs and exits cleanly; data is in DB
- [ ] `GET /health` returns 200
- [ ] `GET /api/anomalies` returns a non-empty JSON array
- [ ] `GET /api/anomalies?sensor_id=TEMP_001` filters correctly
- [ ] Frontend loads in browser, table shows anomalies
- [ ] `docker compose down && docker compose up` — data persists (volume test)
- [ ] `terraform plan` runs without errors
- [ ] GitHub Actions workflow file is valid YAML and passes lint
- [ ] README explains how to run locally and how to deploy
- [ ] All generated files have human sign-off blocks filled in

---

## Human Sign-off Standard

Every file generated with AI assistance during the build gets a sign-off block. Fill it in immediately after reviewing each file — takes 2 minutes, becomes your interview notes.

**Python / YAML / HCL / Dockerfile** — comment block at the top:
```
# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer:
# Date:
# Changes from AI draft:
# Notes:
# ──────────────────────────────────────────────────────────
```

**Markdown** — section at the bottom:
```
---
## Human Review
- **Reviewer:**
- **Date reviewed:**
- **Changes from AI draft:**
- **Notes:**
```

Applied to: all files in `services/`, `nginx/`, `db/`, `terraform/`, `.github/workflows/`, `docker-compose.yml`, `frontend/`.  
Not applied to: the four provided files (`2_generate_data.py`, `3_anomaly_detector.py`, `DATA_GENERATOR_GUIDE.md`, `1_README.md`).

---

## Human Review

- **Reviewer:**
- **Date reviewed:**
- **Changes from AI draft:**
- **Notes:**
