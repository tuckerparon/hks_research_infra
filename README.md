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
docker compose down -v                # stop and wipe the database volume
```

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

## Documentation

| Document | Description |
|---|---|
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architectural and process decisions with reasoning and tradeoffs |
| [docs/INFRASTRUCTURE_PLAN.md](docs/INFRASTRUCTURE_PLAN.md) | Component specs, schema, and operational notes |
| [docs/provided/](docs/provided/) | Original exercise files provided by HKS |

---

## Infrastructure Diagram

```
                        ┌─────────────────────────────────────────┐
                        │              Docker / AWS                │
                        │                                          │
  Browser ──── :80 ───► │  ┌─────────┐                           │
                        │  │  nginx  │                            │
                        │  └────┬────┘                            │
                        │       │ /api/*                          │
                        │  ┌────▼────┐        ┌──────────────┐   │
                        │  │   API   │◄───────►│  PostgreSQL  │   │
                        │  │FastAPI  │        └──────┬───────┘   │
                        │  └─────────┘               │            │
                        │                    ┌────────▼───────┐   │
                        │                    │    Pipeline    │   │
                        │                    │  (scheduled)   │   │
                        │                    └────────────────┘   │
                        └─────────────────────────────────────────┘

Local:  nginx container → api container → postgres container ← pipeline container
AWS:    ALB → ECS Fargate (api) → RDS Postgres ← ECS Fargate (pipeline)
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

