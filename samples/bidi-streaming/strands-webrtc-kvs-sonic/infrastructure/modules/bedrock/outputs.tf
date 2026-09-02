output "role_arn" {
  description = "IAM role ARN for the voice agent"
  value       = aws_iam_role.voice_agent.arn
}
