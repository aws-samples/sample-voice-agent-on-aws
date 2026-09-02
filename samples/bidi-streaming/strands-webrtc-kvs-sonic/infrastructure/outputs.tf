output "bedrock_role_arn" {
  description = "IAM role ARN for Bedrock access"
  value       = module.bedrock.role_arn
}

# Storage
output "frontend_bucket_id" {
  description = "Frontend S3 bucket ID"
  value       = module.storage.frontend_bucket_id
}

# Auth
output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.auth.user_pool_id
}

output "user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  value       = module.auth.user_pool_client_id
}

output "identity_pool_id" {
  description = "Cognito Identity Pool ID"
  value       = module.auth.identity_pool_id
}

# CDN
output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.cdn.distribution_id
}

output "cloudfront_domain_name" {
  description = "CloudFront domain name"
  value       = module.cdn.distribution_domain_name
}

# Agent
output "agent_runtime_arn" {
  description = "AgentCore Runtime ARN"
  value       = module.agent.agent_runtime_arn
}

output "agent_runtime_id" {
  description = "AgentCore Runtime ID"
  value       = module.agent.agent_runtime_id
}

output "ecr_repository_url" {
  description = "ECR repository URL for agent image"
  value       = module.agent.repository_url
}

output "agentcore_role_arn" {
  description = "IAM role ARN for AgentCore runtime"
  value       = module.agent.agentcore_role_arn
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (pass-through)"
  value       = var.knowledge_base_id
}
