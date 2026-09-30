data "aws_caller_identity" "current" {}

# IAM role for local development - allows the developer to assume a role
# with the exact Bedrock permissions needed for the voice agent.
resource "aws_iam_role" "voice_agent" {
  name = "bidir-streaming-voice-agent"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.voice_agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "NovaSonicAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:InvokeModelWithBidirectionalStream",
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-2-sonic-v1*",
        ]
      },
      {
        Sid    = "KnowledgeBaseAccess"
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}",
        ]
      }
    ]
  })
}
