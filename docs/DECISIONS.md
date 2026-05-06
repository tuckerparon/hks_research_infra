# Decision Log

**Project:** Research Data Pipeline Infrastructure (HKS Technical Exercise)  
**Deadline:** EOD Wednesday May 6, 2026  
**Author:** Tucker Paron  
**Last Updated:** 2026-05-06

This document records the considerations and tradeoffs behind every significant decision made in building this project. It is intended to serve as interview preparation for the follow-up call, where the expected question is: *"Walk us through the considerations that shaped your solution."*

---

## Process Decisions

### Decision 1: AI tools are permitted and expected

**Decision:** Use AI coding tools (Claude Code as primary) throughout this project.

**Reasoning:** The exercise email states explicitly: *"There are no other restrictions than doing this work on your own and using tools that are available to you."* The estimated time (5-6 hours) for a stack that includes Docker Compose, PostgreSQL, a REST API, a frontend, nginx, Terraform for AWS, and a GitHub Actions CI/CD pipeline is only achievable with AI assistance. Because of this, we assume that the exercise was designed with AI tools in mind.

---

### Decision 2: Claude Code as primary tool

**Decision:** Use Claude Code as the primary AI tool, with Cursor open alongside it to review code as it is generated.

**Reasoning:** This project is heavily infrastructure-focused (Docker Compose, Terraform, nginx, GitHub Actions, Dockerfiles) in addition to application code (Python API, pipeline script, HTML frontend). Claude Code can execute shell commands directly — running `docker compose up`, checking if an endpoint responds, reading output, and managing git. This matters for a project where many problems only reveal themselves when you actually run the code. Cursor is kept open in parallel for inline code review, since Claude Code CLI alone does not provide enough visibility into granular file changes.

---

### Decision 3: Documentation-first, human-directed AI development

**Decision:** Write architecture decisions and component specs before any code is generated. Every AI-generated file gets a human sign-off before committing.

**Reasoning:**
AI coding, especially agentic coding like Claude Code can quickly get out of hand with lots of generated code and little oversight. Ensuring documentation and requirements are clearly lined up before coding AND reviewed thoroughly ensures the code generated will be as expected/desired. The flow will be as follows:

```
Requirements (1_README.md — provided by HKS)
    ↓
Architecture decisions (this document — authored before coding begins)
    ↓
Component specs (INFRASTRUCTURE_PLAN.md — what each service does and why)
    ↓
Build (AI-assisted, human-directed: human makes decisions and signs off, Claude Code builds)
    ↓
Verification (docker compose up works, API responds, anomalies visible in UI, cloud-ready check)
    ↓
Demo readiness (can walk through end-to-end at follow-up interview)
```

---

## Architecture Decisions

### Decision 4: FastAPI over Flask for the REST API

**Decision:** Use FastAPI for the REST API layer.

**Reasoning:** Flask is simpler and more widely familiar, but FastAPI provides automatic request/response validation via Pydantic models and type hints throughout, which makes the contract between the API and frontend explicit and catches bugs at the boundary. The type hints also make the code more readable during a walkthrough. Note: FastAPI's auto-generated `/docs` UI is available at `http://localhost:8000/docs` when hitting the API container directly, but is not proxied through nginx in the current setup.

---

### Decision 5: Vanilla HTML/JS frontend, no framework

**Decision:** Build the frontend as a single static HTML file with vanilla JavaScript.

**Reasoning:** The requirement is "simple web interface displaying recent anomalies in a table." A React or Vue app adds a build step, package dependencies, and complexity with no functional benefit for displaying one table. A single HTML file served by nginx is faster to build, easier to explain, and harder to break. The frontend is not the evaluation focus.

---

### Decision 6: Single nginx container handles both frontend and API routing

**Decision:** One nginx container serves the static frontend at `/` and routes `/api/` requests to the FastAPI container.

**Reasoning:** nginx is required by the exercise. The only question was whether to use one container or two. nginx can do both jobs simultaneously — serve HTML files directly and forward API traffic to another service. One container doing both is simpler than two with the same external behavior.

---

### Decision 7: Pipeline runs on a schedule, not once

**Decision:** The data pipeline (generate CSV → ingest sensor readings → detect anomalies → store results) runs continuously on a configurable interval (default: every 1 minute, set via `PIPELINE_INTERVAL_MINUTES` in `.env`), generating a fresh batch of data each cycle.

**Reasoning:** The exercise describes a "scalable research data processing pipeline" — which implies continuous operation, not a one-time load. A scheduled pipeline also makes the demo more compelling: the interviewer can watch new anomalies appear in the frontend while the system is running. The pipeline code is identical either way; only the trigger mechanism changes. A `while True` loop with `time.sleep()` inside the container keeps the implementation simple — no new dependencies.

---

### Decision 8: AWS as cloud provider, flat Terraform structure

**Decision:** Use AWS for cloud deployment, with all Terraform configuration in a single flat folder rather than split into subfolders.

**Reasoning:** AWS is the industry standard for research computing infrastructure. Simo mentioned during the initial call that HKS primarily uses AWS and is focused on helping students and researchers work with cloud infrastructure.

Splitting Terraform into subfolders (one for networking, one for the database, one for containers) is better for large teams maintaining code long-term. For a single-engineer exercise it adds boilerplate with no benefit — the flat structure is simpler to read and easier to walk through in an interview.

---

### Decision 9: Human sign-off on every generated file

**Decision:** Every file substantially generated by AI includes a sign-off block where the reviewer records what they changed, verified, and noted.

**Reasoning:** When asked "how did you use AI?" in the follow-up interview, this makes the answer concrete — you can point to specific files and describe exactly what you changed and why. It also enforces a deliberate review pass on every file rather than accepting AI output without reading it.

---

### Decision 10: All query filters are server-side

**Decision:** Every filter on the `/api/anomalies` endpoint (sensor, anomaly type, date range, minimum confidence) is applied in SQL, not in JavaScript after the data is fetched.

**Reasoning:** Client-side filtering fetches all rows matching the other filters and then discards results in the browser. With `limit=100` and a high confidence threshold, the API could return 100 rows of which 0 meet the threshold — even though thousands of qualifying rows exist in the database. Server-side filtering means the database does the work, `limit` applies after filtering, and the response always contains the most relevant results. It also means all filter behavior is testable without a browser.

---

### Decision 11: Pipeline seeds only on first boot

**Decision:** The 10,000-row initial seed batch runs only when the database is empty, not on every container start.

**Reasoning:** The original behavior re-seeded on every pipeline container restart, which caused duplicate data and inflated row counts when `docker compose restart` was used to pick up code changes. Adding an existence check (`SELECT EXISTS(SELECT 1 FROM sensor_readings LIMIT 1)`) before the seed cycle means restarts are safe and `docker compose down -v` is the explicit, deliberate way to reset to a clean state.

---

### Decision 12: Two-path CI based on AWS credential availability

**Decision:** The CI pipeline takes one of two paths depending on whether `AWS_ROLE_ARN` is configured: if credentials are present, it builds and pushes to ECR and deploys to ECS; if not, it builds all Docker images locally via `docker compose build` to verify the Dockerfiles are valid.

**Reasoning:** Skipping the build step entirely when AWS credentials are absent means CI only runs tests — it doesn't verify that the images actually build. The two-path design ensures every push produces a meaningful build artifact (either ECR images or a verified local build), without requiring AWS credentials to be configured for the local development workflow.

---

## Human Review

- **Reviewer:** Tucker Paron
- **Date reviewed:** 2026-05-05
- **Changes from AI draft:** 
    - Originally suggested a "one-shot" (non-scheduled) pipeline. I changed this to a scheduled one as the instructions emphasize "scalability"
    - Ensured every decision had a Decision and Reasoning section. AI originally generated decisions with inconsisntent section naming and frivilous details which were trimmed.
- **Notes:**
    - Questioned whether sign-off should appear on each individual decision or only at the end of the document — kept one sign-off at the end. Per-decision sign-offs would be excessive for this exercise scope.
    - Questioned Decision 6 (single nginx container) — kept after explanation. nginx is required by the exercise; one container doing both jobs (serving frontend and proxying API) is simpler than two containers with identical external behavior.
    - Questioned Decision 8 (flat Terraform) — kept. Nested module structure is better for large teams but adds boilerplate with no benefit for a single-engineer exercise.
    - Questioned whether the Verification section belonged in this document — moved it to INFRASTRUCTURE_PLAN.md where it functions as an operational checklist. Only the definition of "cloud-ready" (an interpretive decision) was kept here, folded into Decision 8.
