# Sensor Anomaly Pipeline

A research data pipeline that ingests sensor readings, detects anomalies, and serves results via a REST API and web dashboard. Runs locally with Docker Compose and is deployable to AWS via Terraform.

---

## Table of Contents

- [Overview](#overview)
- [How To Run](#how-to-run)
  - [Prerequisites](#prerequisites)
  - [Mac](#mac)
  - [Windows](#windows)
  - [Deploying to AWS](#deploying-to-aws)
  - [Sanity Checks](#sanity-checks)
  - [Troubleshooting](#troubleshooting)
  - [Teardown](#teardown)
  - [Video Walkthrough](#video-walkthrough)
- [Architecture](#architecture)
  - [API](#api)
  - [Database](#database)
  - [Pipeline](#pipeline)
  - [Docker and nginx](#docker-and-nginx)
- [Requirements Verification](#requirements-verification)
- [Documentation](#documentation)
- [Future Changes](#future-changes)
  - [Scalability](#scalability)
  - [Improvements](#improvements)

---

## Overview

The system continuously generates batches of sensor readings (temperature, humidity, pressure), stores them in PostgreSQL, runs statistical anomaly detection, and exposes the results through a FastAPI endpoint consumed by a vanilla HTML/JS dashboard.

All credentials are environment-variable driven. No secrets are committed to the repository.

---

## How To Run

### Prerequisites

Only two tools are required to run the project locally. Everything else (Python, PostgreSQL, nginx) runs inside Docker.


| Tool           | Mac                                                                                   | Windows                                                                               |
| -------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Git            | Pre-installed, or `brew install git`                                                  | [git-scm.com](https://git-scm.com/download/win)                                       |
| Docker Desktop | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |


### Mac

```bash
git clone https://github.com/tuckerparon/hks_research_infra.git
cd hks_research_infra
cp .env.example .env

# If you have run this project before, wipe the old database volume first:
# docker compose down -v

docker compose up --build
```

Navigate to `http://localhost` — the dashboard loads automatically. The pipeline seeds 10,000 readings on first start, then adds 1,000 more every minute for 30 minutes, then stops automatically. To change the duration, update `MAX_RUNTIME_MINUTES` in `.env`.

### Windows

```powershell
git clone https://github.com/tuckerparon/hks_research_infra.git
cd hks_research_infra
copy .env.example .env        # Command Prompt
# cp .env.example .env        # PowerShell or Git Bash

# If you have run this project before, wipe the old database volume first:
# docker compose down -v

docker compose up --build
```

Navigate to `http://localhost`.

### Deploying to AWS (Production Only)

> **This section is not required to run the project locally.** The Mac and Windows steps above are all you need for local development. This section covers deploying the full stack to AWS for production use.

The Terraform configuration in `terraform/` provisions the full AWS stack (VPC, RDS PostgreSQL 15, ECS Fargate for the API and pipeline, ALB, ECR, and S3 for static frontend hosting). `terraform validate` runs automatically in CI on every push to confirm the configuration is syntactically valid.

To activate a live deployment:

1. Create an S3 bucket for Terraform state and update `terraform/backend.tf` with the bucket name
2. Set up an OIDC IAM role that trusts GitHub Actions ([GitHub OIDC docs](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services))
3. Add `AWS_ROLE_ARN` to GitHub repository secrets
4. Run `terraform apply` from the `terraform/` directory to provision infrastructure

Once `AWS_ROLE_ARN` is set, the CI/CD pipeline automatically builds and pushes Docker images to ECR and triggers an ECS rolling deployment on every push to `main`.

### Sanity Checks

Open a new terminal window — your original window is attached to the running containers.

```bash
cd hks_research_infra

# All 4 containers are running and healthy
docker compose ps

# Watch pipeline ingestion in real time
docker compose logs pipeline -f

# API is responding (any directory)
curl http://localhost/health
curl "http://localhost/api/anomalies?limit=5"

# Database has data
docker compose exec db psql -U pipeline_user -d sensor_data \
  -c "SELECT COUNT(*) FROM sensor_readings; SELECT COUNT(*) FROM anomalies;"
```

### Troubleshooting

**Port 80 or 5432 already in use** — another Docker project (or a local PostgreSQL install) may be holding port 5432, or another process holding port 80. Find the culprit with `docker ps | grep 5432` or `sudo lsof -i :5432`. If it's another Compose project, navigate to that directory and run `docker compose down` before starting this one.

**Docker not running** — open Docker Desktop and wait for the whale icon to stop animating before running `docker compose up`.

**Containers stuck starting** — run `docker compose logs db` to check if PostgreSQL finished initializing. The pipeline and API wait for the DB healthcheck to pass before starting.

**Apple Silicon (M1/M2)** — all base images (`python:3.11-slim`, `postgres:15-alpine`, `nginx:alpine`) are multi-architecture and pull the correct arm64 image automatically. No flags needed.

**Windows line endings** — if files are edited on Windows, Git may convert line endings (CRLF). The project has no shell scripts so this is unlikely to matter, but set `git config core.autocrlf false` if you encounter issues.

### Teardown

**Complete teardown (wipes all data):**

```bash
docker compose down -v          # stop containers AND delete the database volume
```

**Stop containers but keep data:**

```bash
docker compose down             # stops pipeline and all containers, data volume survives
```

Data persists in the `postgres_data` Docker volume. On next `docker compose up --build` the pipeline will detect existing data and skip the seed batch.

**Other useful commands:**

```bash
docker compose restart          # restart containers without stopping, data survives
docker volume ls                # list all Docker volumes on your machine
docker volume prune             # remove all unused volumes
```

The pipeline stops automatically after `MAX_RUNTIME_MINUTES` (default: 30) to prevent unbounded data growth during local demos. At ~1,000 readings/minute the database grows roughly 3–4 MB over a 30-minute run.

### Video Walkthrough

[![](https://youtu.be/kzF4W2ec7W4)]


---

## Architecture

```
                        +------------------------------------------+
                        |             Docker / AWS                 |
                        |                                          |
  Browser --- :80 -->   |  +--------+                              |
                        |  | nginx  |                              |
                        |  +---+----+                              |
                        |      | /api/*                            |
                        |  +---v----+       +--------------+       |
                        |  |  API   +<----->+  PostgreSQL  |       |
                        |  | FastAPI|       +------+-------+       |
                        |  +--------+              |               |
                        |                   +------v---------+     |
                        |                   |    Pipeline    |     |
                        |                   |  (scheduled)   |     |
                        |                   +----------------+     |
                        +------------------------------------------+

Local:  nginx --> api --> postgres <-- pipeline
AWS:    ALB --> ECS Fargate (api) --> RDS Postgres <-- ECS Fargate (pipeline)
        Images stored in ECR. State managed by Terraform in S3.
```


| Component                | Local                             | AWS Equivalent          |
| ------------------------ | --------------------------------- | ----------------------- |
| Reverse proxy / frontend | nginx container                   | ALB + S3 static hosting |
| API                      | FastAPI container                 | ECS Fargate service     |
| Pipeline                 | Python container (scheduled loop) | ECS Fargate service     |
| Database                 | PostgreSQL container              | RDS PostgreSQL 15       |
| Image registry           | Local Docker                      | ECR                     |
| State storage            | —                                 | S3 + DynamoDB           |


### API

The REST API is built with FastAPI and served on port 8000 inside Docker, proxied through nginx at `http://localhost/api/`.

**Key files:**

- `services/api/main.py` — endpoint definitions
- `services/api/models.py` — Pydantic response models
- `services/api/utils.py` — z-score to confidence percentage conversion
- `services/api/database.py` — PostgreSQL connection pool
- `services/api/tests/` — 19 unit tests (run with `pytest`)

**Endpoints:**

```bash
# All anomalies (paginated, newest first)
curl "http://localhost/api/anomalies?limit=5"

# Filter by sensor, type, and minimum confidence
curl "http://localhost/api/anomalies?sensor_id=TEMP_002&anomaly_type=temperature_anomaly&min_confidence_pct=95"

# Filter by date range
curl "http://localhost/api/anomalies?start=2026-05-06T00:00:00Z&end=2026-05-06T23:59:59Z"

# Dropdown data
curl http://localhost/api/sensors
curl http://localhost/api/anomaly-types

# Liveness probe
curl http://localhost/health
```

**Example response from `/api/anomalies`:**

```json
[
  {
    "id": 42,
    "sensor_data_id": 381,
    "sensor_id": "TEMP_002",
    "anomaly_type": "temperature_anomaly",
    "confidence_score": 2.85,
    "confidence_pct": 99.56,
    "detected_at": "2026-05-06T15:24:01.000Z"
  }
]
```

**Useful commands:**

```bash
docker compose logs api -f          # watch live API requests
```

### Database

PostgreSQL 15 running in Docker, initialized from `db/init.sql` on first start. The schema has two tables: `sensor_readings` and `anomalies`, with indexes on the columns most commonly used for filtering.

**Key files:**

- `db/init.sql` — schema definition, tables, and indexes

**Accessing directly:**

```bash
# Terminal
docker compose exec db psql -U pipeline_user -d sensor_data

# Useful psql commands once connected
\dt                                     # list tables
SELECT COUNT(*) FROM sensor_readings;   # total readings ingested
SELECT COUNT(*) FROM anomalies;         # total anomalies detected
SELECT * FROM anomalies ORDER BY detected_at DESC LIMIT 5;
\q                                      # exit psql
```

Docker Desktop alternative: Containers → `hks-db-1` → **Exec** tab → run the `psql` command above.

### Pipeline

A Python process that runs on a configurable interval. On first start it seeds the database with 10,000 readings; subsequent cycles add 1,000. It uses the provided `DataGenerator` to create synthetic sensor readings and `AnomalyDetector` to flag statistical outliers.

**Key files:**

- `services/pipeline/run_pipeline.py` — orchestration loop
- `docs/provided/2_generate_data.py` — provided data generator (copied into container at build time)
- `docs/provided/3_anomaly_detector.py` — provided z-score anomaly detector (copied into container at build time)

**Useful commands:**

```bash
docker compose logs pipeline -f     # watch ingestion cycles in real time
```

### Docker and nginx

Four containers are defined in `docker-compose.yml`: `db`, `pipeline`, `api`, and `nginx`. The `db` and `api` containers have healthchecks; `pipeline` and `api` wait for the DB to be healthy before starting.

nginx serves the static frontend at `/` and proxies all `/api/` traffic to the FastAPI container. The frontend HTML, CSS, and JS are in `frontend/index.html`.

**Key files:**

- `docker-compose.yml` — container definitions, networking, volumes, healthchecks
- `nginx/nginx.conf` — routing rules
- `nginx/Dockerfile` — copies frontend files into the nginx image
- `frontend/index.html` — dashboard (single file, no build step)
- `services/api/Dockerfile` — API image
- `services/pipeline/Dockerfile` — pipeline image

**Useful commands:**

```bash
docker compose up --build           # build all images and start
docker compose ps                   # check container status and health
docker compose down                 # stop (data persists)
docker compose down -v              # stop and wipe database
```

---

## Requirements Verification


| Requirement                              | How it's met                                                                                                    | How to verify                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Ingest CSV sensor data into PostgreSQL   | Pipeline generates batches, bulk-inserts via `execute_values` into `sensor_readings`                            | `docker compose logs pipeline -f` shows cycle output                    |
| Anomaly detection with confidence scores | `3_anomaly_detector.py` (provided) runs z-score detection; scores converted to confidence % via `utils.py`      | Dashboard confidence column; `SELECT * FROM anomalies LIMIT 5;` in psql |
| Store results with anomaly flags         | `anomalies` table stores `anomaly_type`, `confidence_score`, `detected_at`, FK to `sensor_readings`             | `SELECT COUNT(*) FROM anomalies;` in psql                               |
| REST API                                 | FastAPI serves `/api/anomalies`, `/api/sensors`, `/api/anomaly-types`, `/health`                                | `curl http://localhost/api/anomalies?limit=5`                           |
| Simple web dashboard                     | Vanilla HTML/JS at `http://localhost` with filters for sensor, type, confidence, date range                     | Navigate to `http://localhost`                                          |
| Docker Compose orchestration             | `docker-compose.yml` defines db, pipeline, api, nginx with healthchecks and `depends_on`                        | `docker compose ps` shows all 4 services healthy                        |
| >10k records handled efficiently         | Bulk insert via `execute_values`; indexed on `sensor_id`, `timestamp`, `detected_at`; API paginated             | `docker compose logs pipeline -f` — 10k seed runs in seconds            |
| Database persists between restarts       | Named volume `postgres_data` survives `docker compose restart` and `docker compose down`                        | Row count before and after `docker compose restart` stays the same      |
| Basic monitoring / health checks         | `/health` endpoint; Docker healthchecks on `db` and `api`; ALB health check in Terraform                        | `curl http://localhost/health` returns `{"status":"ok"}`                |
| Terraform for AWS                        | `terraform/main.tf` provisions VPC, RDS, ECS, ALB, ECR, S3                                                      | `terraform validate` passes in CI on every push (see Actions tab)       |
| CI/CD pipeline                           | GitHub Actions: tests + `terraform validate` on every push; Docker build or ECR deploy based on AWS credentials | See `.github/workflows/deploy.yml`; Actions tab shows test job green    |


---

## Documentation


| Document                                                   | Description                                                      |
| ---------------------------------------------------------- | ---------------------------------------------------------------- |
| [docs/DECISIONS.md](docs/DECISIONS.md)                     | Architectural and process decisions with reasoning and tradeoffs |
| [docs/INFRASTRUCTURE_PLAN.md](docs/INFRASTRUCTURE_PLAN.md) | Component specs, schema, and operational notes                   |
| [docs/provided/](docs/provided/)                           | Original exercise files provided by HKS                          |


---

## Future Changes

### Scalability

Changes required to move this system from a local demo to a production deployment:

**Infrastructure:**

- **RDS Multi-AZ + read replica** — currently one database instance. If it goes down, the whole system stops. Multi-AZ keeps a live standby in a second data center that takes over automatically on failure. A read replica offloads API query traffic from the primary.
- **HTTPS** — traffic is currently unencrypted HTTP. In production, an ACM certificate on the ALB encrypts all traffic between users and the system.
- **Multiple API instances** — currently one API container runs behind the load balancer. If it crashes, requests fail until it restarts. Setting `desired_count = 2+` in ECS means the ALB routes around unhealthy instances automatically.
- **RDS automated backups** — no backup policy exists today. Enabling point-in-time recovery means a bad migration or accidental delete can be rolled back to any point in the last N days.
- **Secrets Manager for credentials** — DB credentials are currently in environment variables, which can leak via logs or task definitions. AWS Secrets Manager stores them encrypted; ECS tasks fetch them at runtime via IAM permissions instead.

**Pipeline:**

- **Real data source** — the pipeline currently generates synthetic data. In production it would pull from wherever sensor data actually lands: an S3 bucket, a Kafka topic, or an MQTT broker. The processing code doesn't change, only the input source.
- **Dead-letter handling** — if an ingestion cycle fails today (DB briefly unreachable, malformed data), the failure is logged and the cycle is skipped silently. A dead-letter queue would capture failed batches so they can be retried or inspected.
- **Pinned dependency versions** — `requirements.txt` currently uses unpinned versions (`fastapi`, not `fastapi==0.115.0`). A library releasing a breaking change could silently break a build. Pinning to exact versions makes every build reproducible.

**Observability:**

- **Structured (JSON) logging** — current logs are plain text strings. Switching to JSON means CloudWatch Logs Insights can query across services: e.g., "show all pipeline cycles in the last hour where anomaly count exceeded 500."
- **CloudWatch alarms** — no alerting exists. Alarms on API error rate and pipeline cycle lag would page an on-call engineer before users notice a problem.
- **Prometheus `/metrics` endpoint** — for teams running Grafana dashboards, a `/metrics` endpoint would expose API latency histograms and pipeline cycle counters in a format Prometheus can scrape.

**Security:**

- **Private subnets** — ECS tasks currently run in public subnets, meaning each container has a publicly routable IP address. Moving them to private subnets with a NAT Gateway means containers can reach the internet (to pull images, etc.) but cannot be reached directly from it.
- **Least-privilege IAM roles** — the ECS task roles currently have broader permissions than needed. Each service should only be granted what it uses: the pipeline task needs S3 read access, the API task needs RDS access — nothing more.
- **ECR image scanning** — enabling vulnerability scanning on push to ECR means CI fails if a Docker image contains a known critical CVE, preventing insecure images from being deployed.

### Improvements

Changes that would improve the project given more development time:

- **Schema migrations** — `init.sql` runs automatically the first time Docker starts, which works for local dev. In production, the schema will evolve over time (new columns, indexes, constraints) and those changes need to be applied safely to a live database without data loss. A migration tool like Alembic or Flyway manages this as versioned, ordered scripts rather than a one-time initialization file.
- **Pipeline resilience** — the pipeline runs as a `while True` loop inside a container. If it crashes mid-cycle, it restarts from scratch with no record of what it was doing. A proper job scheduler (Celery, AWS Step Functions) would track which cycles succeeded, retry failed ones, and expose that history to an operator.
- **Integration tests** — the current tests mock the database, which means they verify the API logic but not the SQL. A test that spins up a real Postgres container (via Docker in CI) and runs the actual queries would catch bugs that only appear against a live database — wrong column names, constraint violations, query plan issues.
- **Frontend** — the dashboard is intentionally minimal. A research tool in production would likely need time-series charts to visualize anomaly trends, sensor comparison views, and CSV export for researchers who want to work with the data offline.
- **Terraform modules** — all infrastructure is defined in a single flat file. That is easy to read for a small project but hard to maintain as the system grows. A production codebase would split it into reusable modules: one for networking (VPC, subnets), one for compute (ECS, ALB), one for data (RDS, S3).
- **CI/CD staging gate** — the pipeline currently deploys directly to production on every push to `main`. A real deployment pipeline would push to a staging environment first, run smoke tests, and require a manual approval step before promoting to production.

