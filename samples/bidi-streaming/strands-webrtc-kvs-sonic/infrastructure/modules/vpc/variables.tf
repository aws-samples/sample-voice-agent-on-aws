variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zone_ids" {
  description = "Physical AZ IDs to use (must be supported by AgentCore)"
  type        = list(string)
  default     = ["use1-az1", "use1-az2"]
}
