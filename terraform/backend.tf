# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer: Tucker Paron
# Date: 2026-05-05
# Changes from AI draft: None
# Notes:
#   - Not examined in detail due to req being "terraform infra" in place
# ──────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state stored in S3 so the team shares a single source of truth.
  # DynamoDB table provides state locking to prevent concurrent applies.
  # The bucket and table must be created manually before first `terraform init`.
  backend "s3" {
    bucket         = "hks-terraform-state"
    key            = "sensor-pipeline/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "hks-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}
