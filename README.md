# Sensor Anomaly Pipeline

A research data pipeline that ingests sensor readings, detects anomalies, and serves results via a REST API and web dashboard. Runs locally with Docker Compose and is deployable to AWS via Terraform.

---

## Overview

The system continuously generates batches of sensor readings (temperature, humidity, pressure), stores them in PostgreSQL, runs statistical anomaly detection, and exposes the results through a FastAPI endpoint consumed by a vanilla HTML/JS dashboard.

All credentials are environment-variable driven. No secrets are committed to the repository.

---

## How to Run Locally

**Prerequisites:** Docker Desktop

```bash
git clone https://github.com/tuckerparon/hks_research_infra.git
cd hks_research_infra

cp .env.example .env          # uses safe placeholder values for local dev
docker compose up --build
```

Navigate to `http://localhost` — the dashboard loads automatically with the most recent anomalies.

The pipeline seeds 10,000 readings on first start, then adds 1,000 more every minute.

**Useful commands:**

```bash
docker compose logs pipeline -f       # watch pipeline ingestion in real time
docker compose logs api -f            # watch API requests
docker compose restart                # restart containers, existing data survives
docker compose down                   # stop containers, data volume survives
docker compose down -v                # stop containers AND wipe the database volume
```

**Data and teardown:**

The pipeline stops automatically after `MAX_RUNTIME_MINUTES` (default: 30 in `.env.example`) to prevent unbounded growth during local demos. At ~1,000 readings/minute the database grows roughly 3–4 MB over a 30-minute run.

`docker compose restart` and `docker compose down` (without `-v`) both preserve the `postgres_data` volume — the database survives and the pipeline skips its initial seed on restart. Only `docker compose down -v` deletes the volume and resets to a clean state.

If teardown is never run, Docker volumes accumulate on your host machine. Check with `docker volume ls` and clean up with `docker volume prune` if needed.

**Accessing the database directly:**

```bash
# Terminal
docker compose exec db psql -U pipeline_user -d sensor_data
\dt                                    # list tables
SELECT COUNT(*) FROM sensor_readings;  # verify row count
SELECT COUNT(*) FROM anomalies;
```

Docker Desktop: Containers → `hks-db-1` → **Exec** tab → run the `psql` command above.

**API:**

```
GET /api/anomalies
  ?sensor_id=TEMP_002          # optional filter
  ?anomaly_type=pressure_anomaly
  ?min_confidence_pct=95       # server-side confidence threshold (0–100)
  ?start=2026-05-06T00:00:00Z  # optional date range
  ?end=2026-05-06T23:59:59Z
  ?limit=100                   # max 1000
  ?offset=0

GET /api/sensors               # distinct sensor IDs for dropdown
GET /api/anomaly-types         # distinct anomaly types for dropdown
GET /health                    # liveness probe
```

---

## Deploying to AWS

The Terraform configuration in `terraform/` provisions the full AWS stack (VPC, RDS PostgreSQL 15, ECS Fargate for the API and pipeline, ALB, ECR, and S3 for static frontend hosting). `terraform validate` runs automatically in CI on every push to confirm the configuration is syntactically valid.

To activate a live deployment:

1. Create an S3 bucket for Terraform state and update `terraform/backend.tf` with the bucket name
2. Set up an OIDC IAM role that trusts GitHub Actions ([GitHub OIDC docs](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services))
3. Add `AWS_ROLE_ARN` to GitHub repository secrets
4. Run `terraform apply` from the `terraform/` directory to provision infrastructure

Once `AWS_ROLE_ARN` is set, the CI/CD pipeline automatically builds and pushes Docker images to ECR and triggers an ECS rolling deployment on every push to `main`.

---

## Documentation


| Document                                                   | Description                                                      |
| ---------------------------------------------------------- | ---------------------------------------------------------------- |
| [docs/DECISIONS.md](docs/DECISIONS.md)                     | Architectural and process decisions with reasoning and tradeoffs |
| [docs/INFRASTRUCTURE_PLAN.md](docs/INFRASTRUCTURE_PLAN.md) | Component specs, schema, and operational notes                   |
| [docs/provided/](docs/provided/)                           | Original exercise files provided by HKS                          |


---

## Infrastructure Diagram

```
                        +------------------------------------------+
                        |             Docker / AWS                 |
                        |                                          |
  Browser --- :80 -->   |  +--------+                             |
                        |  | nginx  |                             |
                        |  +---+----+                             |
                        |      | /api/*                           |
                        |  +---v----+       +--------------+      |
                        |  |  API   +<----->+  PostgreSQL  |      |
                        |  | FastAPI|       +------+-------+      |
                        |  +--------+              |              |
                        |                   +------v---------+    |
                        |                   |    Pipeline    |    |
                        |                   |  (scheduled)   |    |
                        |                   +----------------+    |
                        +------------------------------------------+

Local:  nginx --> api --> postgres <-- pipeline
AWS:    ALB --> ECS Fargate (api) --> RDS Postgres <-- ECS Fargate (pipeline)
        Images stored in ECR. State managed by Terraform in S3.
```

**Component responsibilities:**


| Component                | Local                             | AWS Equivalent                                      |
| ------------------------ | --------------------------------- | --------------------------------------------------- |
| Reverse proxy / frontend | nginx container                   | ALB + nginx not needed (ALB routes directly to API) |
| API                      | FastAPI container                 | ECS Fargate service                                 |
| Pipeline                 | Python container (scheduled loop) | ECS Fargate service                                 |
| Database                 | PostgreSQL container              | RDS PostgreSQL 15                                   |
| Image registry           | Local Docker                      | ECR                                                 |
| State storage            | —                                 | S3 + DynamoDB                                       |


---

## Requirements & Constraints Verification


| Requirement                              | How it's met                                                                                                    | How to verify                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Ingest CSV sensor data into PostgreSQL   | Pipeline generates batches, bulk-inserts via `execute_values` into `sensor_readings`                            | `docker compose logs pipeline -f` shows cycle output                    |
| Anomaly detection with confidence scores | `3_anomaly_detector.py` (provided) runs z-score detection; z-scores converted to confidence % via `utils.py`    | Dashboard confidence column; `SELECT * FROM anomalies LIMIT 5;` in psql |
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

## What Would Change to Scale / Release to Production

**Infrastructure:**

- Enable RDS Multi-AZ for failover; add read replica for API query load
- Add HTTPS: ACM certificate on the ALB, redirect HTTP → HTTPS
- Set ECS `desired_count = 2+` for the API behind the ALB for high availability
- Enable RDS automated backups and set `deletion_protection = true`
- Move DB credentials to AWS Secrets Manager; grant ECS tasks IAM access instead of env vars

**Pipeline:**

- Replace the data generator with a real source (S3 file drop, Kafka topic, or MQTT broker)
- Add dead-letter handling for failed ingestion cycles
- Pin `requirements.txt` to exact versions for reproducible builds

**Observability:**

- Add structured logging (JSON) so CloudWatch Logs Insights can query across services
- Create CloudWatch alarms on API error rate and pipeline cycle lag
- Add `/metrics` endpoint for Prometheus scraping if needed

**Security:**

- Move ECS tasks to private subnets with NAT Gateway (currently in public subnets for demo simplicity)
- Enforce least-privilege IAM roles per service
- Enable ECR image scanning on push

---

## What I Would Change With More Time

- **Schema migrations**: `init.sql` runs once automatically in Docker but needs a proper migration tool (Alembic or Flyway) for production — especially once the schema evolves
- **Pipeline resilience**: the current `while True` loop loses progress silently if it crashes; a proper job scheduler (Celery, AWS Step Functions) would add retry logic and visibility
- **Tests**: API unit tests mock the database. Integration tests against a real Postgres container (via `pytest` + Docker) would catch SQL bugs the mocks miss
- **Frontend**: the dashboard is intentionally minimal — a real research tool would want time-series charts, sensor comparison views, and CSV export
- **Terraform modules**: the flat single-file structure was a deliberate choice for readability in a demo; a production codebase would break networking, compute, and data into reusable modules
- **CI/CD**: the workflow deploys on every push to main with no staging environment; a real pipeline would deploy to staging first and gate production on manual approval

