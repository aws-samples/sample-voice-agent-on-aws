variable "frontend_source_dir" {
  description = "Path to the frontend source directory"
  type        = string
}

variable "frontend_bucket_name" {
  description = "S3 bucket name for frontend static assets"
  type        = string
}

variable "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  type        = string
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_client_id" {
  type = string
}

variable "cognito_identity_pool_id" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "agent_runtime_arn" {
  type = string
}

variable "aws_profile" {
  description = "AWS CLI profile for S3 sync and CloudFront invalidation"
  type        = string
  default     = null
}
