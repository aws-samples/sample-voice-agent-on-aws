output "agent_runtime_arn" {
  description = "AgentCore agent runtime ARN"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
  depends_on  = [terraform_data.runtime_metadata]
}

output "agent_runtime_id" {
  description = "AgentCore agent runtime ID"
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
  depends_on  = [terraform_data.runtime_metadata]
}

output "repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.agent.repository_url
}

output "agentcore_role_arn" {
  description = "IAM role ARN for AgentCore runtime"
  value       = aws_iam_role.agentcore.arn
}
