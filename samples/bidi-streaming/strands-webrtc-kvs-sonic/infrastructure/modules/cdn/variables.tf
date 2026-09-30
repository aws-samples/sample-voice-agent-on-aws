variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
}

variable "frontend_bucket_id" {
  description = "S3 frontend bucket ID"
  type        = string
}

variable "frontend_bucket_arn" {
  description = "S3 frontend bucket ARN"
  type        = string
}

variable "frontend_bucket_regional_domain_name" {
  description = "S3 frontend bucket regional domain name"
  type        = string
}
