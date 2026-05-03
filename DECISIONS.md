# Decision Log

**Project:** Research Data Pipeline Infrastructure (HKS Technical Exercise)  
**Deadline:** EOD Wednesday May 6, 2026  
**Author:** Tucker Paron  
**Last Updated:** 2026-05-03

This document records the considerations and tradeoffs behind every significant decision made in building this project. It is intended to serve as interview preparation for the follow-up call, where the expected question is: *"Walk us through the considerations that shaped your solution."*

---

## Process Decisions

### Decision 1: AI tools are permitted and expected

**Decision:** Use AI coding tools (Claude Code as primary) throughout this project.

**Reasoning:** The exercise email states explicitly: *"There are no other restrictions than doing this work on your own and using tools that are available to you."* The estimated time (5-6 hours) for a stack that includes Docker Compose, PostgreSQL, a REST API, a frontend, nginx, Terraform for AWS, and a GitHub Actions CI/CD pipeline is only achievable with AI assistance. Hand-coding this from scratch would take 15-20 hours. The exercise was designed with AI tools in mind.

**What "on your own" means:** All architecture decisions, tradeoffs, and reviews are human-made. AI generates candidates; the engineer directs, reviews, modifies, and approves.

---

### Decision 2: Claude Code over Cursor as primary tool

**Decision:** Use Claude Code (CLI) as the primary AI tool, with Cursor as a secondary option for tight file-editing loops if needed.

**Reasoning:** This project is approximately 60% infrastructure (Docker Compose YAML, Terraform HCL, nginx config, GitHub Actions YAML, Dockerfiles) and 40% application code (Python API, pipeline script, HTML frontend). Claude Code can execute shell commands directly — running `docker compose up`, checking if an endpoint responds, reading Terraform plan output, and managing git. Cursor can write files but cannot run the infrastructure to verify it. For a project where the hard problems are "does this container network correctly?" and "does Terraform plan show what I expect?", the ability to execute commands is a meaningful advantage.

Cursor would be preferable for a Python-heavy or frontend-heavy project where inline tab completion and file diffing are the primary bottlenecks.

---

### Decision 3: Lightweight V-model for AI-assisted development

**Decision:** Adapt the V-model methodology from prior work for this exercise — but in a lightweight form appropriate to a 5-6 hour exercise, not a regulated health software context.

**What the full V-model is:** A development methodology (documented in a separate personal project) that addresses accountability in AI-assisted development for regulated environments. It includes requirements traceability matrices, regulatory mapping, spec-first testing, and an AI development log analogous to IEC 62304 SOUP analysis. It is overkill here.

**What the lightweight version looks like for this project:**

```
Requirements (1_README.md — provided by HKS)
    ↓
Architecture decisions (this document — human-authored before coding begins)
    ↓
Component specs (INFRASTRUCTURE_PLAN.md — what each service does and why)
    ↓
Build (AI-assisted, human-directed: Tucker makes decisions, Claude Code builds)
    ↓
Verification (docker compose up works, API responds, anomalies visible in UI)
    ↓
Demo readiness (can walk through end-to-end at follow-up interview)
```

**Key principle preserved from the full methodology:** Documentation precedes code. This DECISIONS.md and the INFRASTRUCTURE_PLAN.md are written before any implementation begins on Tuesday.

**Human decisions that AI does not make:**
- Technology choices (Flask vs FastAPI, flat vs modular Terraform, etc.)
- Database schema design
- API contract (what endpoints, what query parameters, what response shape)
- What gets verified before calling the project done
- What tradeoffs are acceptable given the time constraint

---

## Architecture Decisions

### Decision 4: FastAPI over Flask for the REST API

**Decision:** Use FastAPI for the REST API layer.

**Tradeoff considered:** Flask is simpler and more familiar to most engineers. FastAPI adds a dependency but gives automatic OpenAPI/Swagger documentation, request/response validation via Pydantic, and async support.

**Why FastAPI:** The auto-generated `/docs` endpoint is genuinely useful for a demo — the interviewer can see the API contract directly in a browser without any extra work. Type hints on request/response models also make the code self-documenting. For this scale of project the added complexity is minimal.

---

### Decision 5: Vanilla HTML/JS frontend, no framework

**Decision:** Build the frontend as a single static HTML file with vanilla JavaScript. No React, Vue, or other framework.

**Reasoning:** The requirement is "simple web interface displaying recent anomalies in a table." A framework adds build tooling, a node_modules directory, and complexity with no functional benefit for a single-table display. A single HTML file served by nginx is faster to build, easier to demo, and harder to break. The constraint says minimum functional solution; the frontend is not the evaluation focus.

---

### Decision 6: Single nginx container serves both frontend and proxies API

**Decision:** One nginx container: serves the static frontend at `/`, proxies `/api/` to the FastAPI container.

**Alternative considered:** Separate nginx for reverse proxy plus a dedicated container for the frontend. That would more closely mirror a production pattern but adds a service to Docker Compose with no functional benefit at this scale.

**Why single nginx:** Simpler Docker Compose, same external behavior, easier to reason about. In production on AWS, the ALB (Application Load Balancer) replaces nginx entirely — so the nginx config is already conceptually temporary.

---

### Decision 7: Pipeline runs as a one-shot container on startup

**Decision:** The data pipeline (CSV generation → DB ingestion → anomaly detection → write results) runs as a one-shot Docker Compose service that executes on `docker compose up` and exits cleanly.

**Alternative considered:** A scheduled/polling pipeline that runs on an interval. More realistic for production but adds complexity (cron inside a container, or a separate scheduler service) with no demo benefit.

**Why one-shot:** For the demo, we need data in the DB when the interviewer opens the browser. A one-shot pipeline that populates the DB on startup achieves this. We can re-run it manually if needed. The pipeline code is identical regardless — only the trigger mechanism differs.

---

### Decision 8: Flat Terraform structure, no modules

**Decision:** Write Terraform as flat `.tf` files (main.tf, variables.tf, outputs.tf) rather than a nested module structure.

**Reasoning:** A modular Terraform structure (vpc/, ecs/, rds/ subdirectories) is the right pattern for a production codebase that will be maintained by a team. For a single-engineer exercise with a 5-6 hour budget, the overhead of writing module interfaces is not justified. The flat structure is easier to read and audit in a follow-up interview.

**What the Terraform provisions:**
- VPC with public and private subnets
- RDS PostgreSQL instance in a private subnet
- ECS Fargate cluster for the API and pipeline containers
- Application Load Balancer (replaces nginx in cloud — routes `/api/` to ECS, `/` to static frontend)
- ECR repositories for Docker images
- IAM roles for ECS task execution and S3 access

---

### Decision 9: AWS as cloud provider

**Decision:** Use AWS, not another cloud provider.

**Context:** The exercise constraints say "cloud of your choice" but also specify Terraform and GitHub Actions, and the phrasing matches standard AWS-focused infrastructure exercises. AWS is the industry default for this type of role. If asked: the choice was AWS because it is the most widely used cloud for research infrastructure, has mature Terraform support, and ECS Fargate + RDS is a straightforward, well-documented pattern for containerized applications.

---

### Decision 10: PostgreSQL persists via Docker named volume

**Decision:** PostgreSQL data is stored in a named Docker volume (`postgres_data`), not a bind mount to the host filesystem.

**Why:** Named volumes persist between `docker compose down` and `docker compose up` by default, which satisfies the requirement that "database must persist data between container restarts." Bind mounts introduce path portability issues across machines. To fully reset the DB, `docker compose down -v` removes the volume.

---

### Decision 11: Human sign-off block on every generated file

**Decision:** Every file substantially generated by AI includes a sign-off block where the human reviewer records what they changed, verified, and thought.

**Format by file type:**

Python / YAML / HCL (Terraform) — comment block at the top of the file:
```
# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer:
# Date:
# Changes from AI draft:
# Notes:
# ──────────────────────────────────────────────────────────
```

Markdown — section at the bottom of the file:
```
---
## Human Review
- **Reviewer:**
- **Date reviewed:**
- **Changes from AI draft:**
- **Notes:**
```

**Why:** This is the most interview-useful artifact of the AI-assisted workflow. When asked "how did you use AI?", you can point to specific files and say "AI drafted this, I changed X because Y." It also forces a conscious review pass on every file rather than accepting AI output wholesale. The format is deliberately minimal — it should take 2 minutes to fill in, not 20.

**Scope:** All files in `services/`, `nginx/`, `db/`, `terraform/`, `.github/workflows/`, and `docker-compose.yml`. Not applied to provided files (`2_generate_data.py`, `3_anomaly_detector.py`, etc.) since those are not AI-generated.

---

## What I would do with more time

- Add a proper job scheduler (Celery or APScheduler) to run the pipeline on an interval rather than one-shot
- Modularize the Terraform
- Add Prometheus + Grafana for the monitoring requirement (current implementation uses basic `/health` endpoints only)
- Write meaningful integration tests (current tests are unit-level)
- Add authentication to the API (currently open)
- Use AWS Secrets Manager for the DB password in Terraform (current implementation uses environment variables)

---

## Human Review

- **Reviewer:**
- **Date reviewed:**
- **Changes from AI draft:**
- **Notes:**
