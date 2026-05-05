# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: None
# Notes:
# ──────────────────────────────────────────────────────────

FROM nginx:alpine

# Build context is project root (set in docker-compose.yml)
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY frontend /usr/share/nginx/html
