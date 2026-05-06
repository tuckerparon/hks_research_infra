# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: None
# Notes:
#   - Not examined in detail due to req being "terraform infra" in place
# ──────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Short project name used as a prefix on all resource names"
  type        = string
  default     = "hks"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "sensor_data"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "pipeline_user"
}

variable "db_password" {
  description = "PostgreSQL master password — provide via TF_VAR_db_password or terraform.tfvars (never commit)"
  type        = string
  sensitive   = true
}

variable "pipeline_interval_minutes" {
  description = "How often the pipeline runs a new ingestion cycle"
  type        = number
  default     = 5
}

variable "api_cpu" {
  description = "Fargate CPU units for the API task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Fargate memory (MB) for the API task"
  type        = number
  default     = 1024
}

variable "pipeline_cpu" {
  description = "Fargate CPU units for the pipeline task"
  type        = number
  default     = 512
}

variable "pipeline_memory" {
  description = "Fargate memory (MB) for the pipeline task"
  type        = number
  default     = 1024
}
