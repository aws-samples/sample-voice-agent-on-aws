data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Cognito User Pool
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-users"
  }
}

# -----------------------------------------------------------------------------
# Cognito User Pool Client - Public client for web app (SRP auth)
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.project_name}-${var.environment}-web-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  callback_urls = var.callback_urls

  supported_identity_providers = ["COGNITO"]

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
}

# -----------------------------------------------------------------------------
# Cognito Identity Pool - Exchange JWT for temporary AWS credentials
# Used by the browser to sign WebSocket requests to AgentCore with SigV4
# -----------------------------------------------------------------------------
resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${var.project_name}-${var.environment}-identity"
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.web.id
    provider_name           = aws_cognito_user_pool.main.endpoint
    server_side_token_check = false
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-identity"
  }
}

# -----------------------------------------------------------------------------
# IAM role for authenticated Cognito users
# Grants permission to invoke AgentCore Runtime via SigV4-signed WebSocket
# -----------------------------------------------------------------------------
resource "aws_iam_role" "cognito_authenticated" {
  name = "${var.project_name}-${var.environment}-cognito-auth-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })
}

# Only attach the AgentCore invoke policy when we have a real runtime ARN
resource "aws_iam_role_policy" "agentcore_invoke" {
  name = "agentcore-invoke"
  role = aws_iam_role.cognito_authenticated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeAgentRuntime",
          "bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream",
          "bedrock-agentcore:InvokeRuntime",
          "bedrock-agentcore:InvokeRuntimeWithResponseStream",
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    authenticated = aws_iam_role.cognito_authenticated.arn
  }
}

# -----------------------------------------------------------------------------
# Cognito Users
# -----------------------------------------------------------------------------
resource "aws_cognito_user" "this" {
  for_each = var.users

  user_pool_id = aws_cognito_user_pool.main.id
  username     = each.key
  password     = each.value

  attributes = {
    email          = each.key
    email_verified = "true"
  }
}
