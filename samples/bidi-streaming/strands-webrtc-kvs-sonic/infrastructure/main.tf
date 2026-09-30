terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "bidir-streaming-voice-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Local dev IAM role for Bedrock access
module "bedrock" {
  source = "./modules/bedrock"

  aws_region        = var.aws_region
  knowledge_base_id = var.knowledge_base_id
}

# S3 bucket for frontend static files
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
}

# Cognito user pool + identity pool for browser auth
module "auth" {
  source = "./modules/auth"

  project_name      = var.project_name
  environment       = var.environment
  callback_urls     = var.cognito_callback_urls
  agent_runtime_arn = module.agent.agent_runtime_arn
  users             = var.cognito_users
}

# CloudFront distribution for frontend (S3 origin only)
module "cdn" {
  source = "./modules/cdn"

  project_name                         = var.project_name
  environment                          = var.environment
  frontend_bucket_id                   = module.storage.frontend_bucket_id
  frontend_bucket_arn                  = module.storage.frontend_bucket_arn
  frontend_bucket_regional_domain_name = module.storage.frontend_bucket_regional_domain_name
}

# VPC for AgentCore WebRTC (private subnets + NAT for TURN egress)
module "vpc" {
  source = "./modules/vpc"

  project_name          = var.project_name
  environment           = var.environment
  availability_zone_ids = var.availability_zone_ids
}

# -----------------------------------------------------------------------------
# Agent Module - ECR, Docker build/push, AgentCore runtime (VPC + WebRTC)
# -----------------------------------------------------------------------------
module "agent" {
  source = "./modules/agent"

  project_name       = var.project_name
  environment        = var.environment
  aws_region         = var.aws_region
  knowledge_base_id  = var.knowledge_base_id
  agent_source_dir   = "${path.root}/../src"
  aws_profile        = var.aws_profile
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.security_group_id
  cloudfront_origin  = module.cdn.distribution_domain_name
}

# -----------------------------------------------------------------------------
# Frontend Module - Build, deploy to S3, invalidate CloudFront
# -----------------------------------------------------------------------------
module "frontend" {
  source = "./modules/frontend"

  frontend_source_dir        = "${path.root}/../frontend"
  frontend_bucket_name       = module.storage.frontend_bucket_id
  cloudfront_distribution_id = module.cdn.distribution_id
  cognito_user_pool_id       = module.auth.user_pool_id
  cognito_client_id          = module.auth.user_pool_client_id
  cognito_identity_pool_id   = module.auth.identity_pool_id
  aws_region                 = var.aws_region
  agent_runtime_arn          = module.agent.agent_runtime_arn
  aws_profile                = var.aws_profile
}
