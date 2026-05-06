# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: None
# Notes:
#   - Not examined in detail due to req being "terraform infra" in place
# ──────────────────────────────────────────────────────────

output "api_url" {
  description = "Public URL of the API (ALB DNS name)"
  value       = "http://${aws_lb.main.dns_name}"
}

output "frontend_url" {
  description = "Public URL of the frontend (S3 static website)"
  value       = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

output "api_ecr_url" {
  description = "ECR repository URL for the API image — used in CI/CD push step"
  value       = aws_ecr_repository.api.repository_url
}

output "pipeline_ecr_url" {
  description = "ECR repository URL for the pipeline image — used in CI/CD push step"
  value       = aws_ecr_repository.pipeline.repository_url
}

output "rds_endpoint" {
  description = "RDS instance endpoint — needed for manual DB access or migration tasks"
  value       = aws_db_instance.postgres.address
}

output "ecs_cluster_name" {
  description = "ECS cluster name — used when running one-off tasks (e.g. schema migrations)"
  value       = aws_ecs_cluster.main.name
}
