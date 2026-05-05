# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: None
# Notes: 
#   - Verified in Docker Desktop. Layers appear as expected.
#   - docker compose logs pipeline -f shows the output appears as expected in terminal
# ──────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

COPY services/pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy provided root scripts, renaming them so they are importable
# (Python cannot import modules whose names start with a number)
COPY 2_generate_data.py ./generate_data.py
COPY 3_anomaly_detector.py ./anomaly_detector.py

COPY services/pipeline/run_pipeline.py .

CMD ["python", "run_pipeline.py"]
