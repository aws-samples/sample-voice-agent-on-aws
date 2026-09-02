variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
}

variable "callback_urls" {
  description = "Cognito callback URLs"
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "agent_runtime_arn" {
  description = "AgentCore Runtime ARN for IAM policy. Empty string skips the policy."
  type        = string
  default     = ""
}

variable "users" {
  description = "Map of users to create (email => permanent password)"
  type        = map(string)
  default     = {}
}
