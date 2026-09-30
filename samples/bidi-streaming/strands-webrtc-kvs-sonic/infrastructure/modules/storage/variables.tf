variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
}

variable "unique_bucket_suffix" {
  description = "Append a random suffix to S3 bucket names for global uniqueness"
  type        = bool
  default     = true
}
