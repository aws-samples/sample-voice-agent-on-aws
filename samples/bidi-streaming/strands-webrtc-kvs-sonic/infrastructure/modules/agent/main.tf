data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# Content hash - triggers rebuild when source files change
# -----------------------------------------------------------------------------

locals {
  # Hash ALL files that go into the Docker image (exclude __pycache__, .pyc, .dockerignore)
  all_src_files = [for f in fileset(var.agent_source_dir, "**") : f if !can(regex("__pycache__|\\.pyc$|\\.pyo$|\\.dockerignore$", f))]
  src_hash      = sha1(join("", [for f in sort(local.all_src_files) : filesha1("${var.agent_source_dir}/${f}")]))
  image_tag     = "src-${local.src_hash}"
}

# -----------------------------------------------------------------------------
# ECR repository
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "agent" {
  name                 = "${var.project_name}-${var.environment}-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  repository = aws_ecr_repository.agent.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# -----------------------------------------------------------------------------
# Docker build + push
# -----------------------------------------------------------------------------

resource "terraform_data" "docker_push" {
  triggers_replace = local.image_tag

  provisioner "local-exec" {
    environment = { AWS_PROFILE = var.aws_profile != null ? var.aws_profile : "" }
    command     = <<-EOF
      set -e
      SRC="$(cd "${var.agent_source_dir}" && pwd)"
      REGISTRY="${aws_ecr_repository.agent.repository_url}"
      REGION="${var.aws_region}"
      docker build --platform linux/arm64 --provenance=false \
        --build-arg BEDROCK_KB_ID="${var.knowledge_base_id}" \
        -t "$REGISTRY:${local.image_tag}" \
        -f "$SRC/Dockerfile" "$SRC"
      aws ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "$(echo $REGISTRY | cut -d/ -f1)"
      docker push "$REGISTRY:${local.image_tag}"
    EOF
  }
}

# -----------------------------------------------------------------------------
# IAM role for AgentCore runtime
# -----------------------------------------------------------------------------

resource "aws_iam_role" "agentcore" {
  name = "${var.project_name}-${var.environment}-agentcore"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "agentcore" {
  name = "agentcore-permissions"
  role = aws_iam_role.agentcore.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:DescribeLogGroups", "logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
        ]
      },
      # AgentCore's documented execution-role policy requires this account-level
      # CloudWatch Logs action; PutResourcePolicy does not support resource scoping.
      {
        Sid      = "CloudWatchLogsResourcePolicy"
        Effect   = "Allow"
        Action   = ["logs:PutResourcePolicy"]
        Resource = "*"
      },
      {
        Sid      = "XRay"
        Effect   = "Allow"
        Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
        Resource = "*"
      },
      {
        Sid       = "CloudWatchMetrics"
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" } }
      },
      {
        Sid    = "WorkloadIdentity"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
        Resource = [
          "arn:aws:bedrock-agentcore:*:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:*:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*",
        ]
      },
      {
        Sid      = "NovaSonicAccess"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:InvokeModelWithBidirectionalStream"]
        Resource = ["arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-2-sonic-v1*"]
      },
      {
        Sid      = "KnowledgeBaseAccess"
        Effect   = "Allow"
        Action   = ["bedrock:Retrieve"]
        Resource = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/${var.knowledge_base_id}"]
      },
      {
        Sid      = "ECRImageAccess"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
        Resource = [aws_ecr_repository.agent.arn]
      },
      {
        Sid      = "ECRTokenAccess"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "KVSAccess"
        Effect = "Allow"
        Action = [
          "kinesisvideo:DescribeSignalingChannel",
          "kinesisvideo:GetSignalingChannelEndpoint",
          "kinesisvideo:GetIceServerConfig",
          "kinesisvideo:ConnectAsMaster",
          "kinesisvideo:CreateSignalingChannel",
        ]
        Resource = "*"
      },
      {
        Sid    = "VPCNetworking"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
        ]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# AgentCore Runtime (Docker / VPC / WebRTC)
# -----------------------------------------------------------------------------

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = replace("${var.project_name}_${var.environment}_voice_agent", "-", "_")
  role_arn           = aws_iam_role.agentcore.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent.repository_url}:${local.image_tag}"
    }
  }

  environment_variables = {
    KVS_CHANNEL_NAME  = var.kvs_channel_name
    AWS_REGION        = var.aws_region
    BEDROCK_KB_ID     = var.knowledge_base_id
    CLOUDFRONT_ORIGIN = var.cloudfront_origin
    CONTAINER_ENV     = "true"
  }

  network_configuration {
    network_mode = "VPC"

    network_mode_config {
      subnets         = var.private_subnet_ids
      security_groups = [var.security_group_id]
    }
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  depends_on = [
    aws_iam_role_policy.agentcore,
    terraform_data.docker_push,
  ]
}

# The AWS provider does not yet expose AgentCore metadata_configuration.
# Enforce MMDSv2 after runtime creation and every image/configuration update.
resource "terraform_data" "runtime_metadata" {
  triggers_replace = sha1(jsonencode({
    runtime_id        = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
    image_uri         = "${aws_ecr_repository.agent.repository_url}:${local.image_tag}"
    role_arn          = aws_iam_role.agentcore.arn
    subnets           = sort(var.private_subnet_ids)
    security_groups   = [var.security_group_id]
    region            = var.aws_region
    knowledge_base    = var.knowledge_base_id
    kvs_channel       = var.kvs_channel_name
    cloudfront_origin = var.cloudfront_origin
    protocol          = "HTTP"
    idle_timeout      = 900
    max_lifetime      = 28800
    require_mmdsv2    = true
  }))

  provisioner "local-exec" {
    environment = { AWS_PROFILE = var.aws_profile != null ? var.aws_profile : "" }
    command     = <<-EOF
      "${abspath("${path.root}/../.venv/bin/python")}" <<'PYTHON'
      import time
      import boto3

      client = boto3.client("bedrock-agentcore-control", region_name="${var.aws_region}")
      runtime_id = "${aws_bedrockagentcore_agent_runtime.this.agent_runtime_id}"
      client.update_agent_runtime(
          agentRuntimeId=runtime_id,
          agentRuntimeArtifact={
              "containerConfiguration": {
                  "containerUri": "${aws_ecr_repository.agent.repository_url}:${local.image_tag}",
              },
          },
          roleArn="${aws_iam_role.agentcore.arn}",
          networkConfiguration={
              "networkMode": "VPC",
              "networkModeConfig": {
                  "subnets": ${jsonencode(var.private_subnet_ids)},
                  "securityGroups": ${jsonencode([var.security_group_id])},
              },
          },
          protocolConfiguration={"serverProtocol": "HTTP"},
          lifecycleConfiguration={"idleRuntimeSessionTimeout": 900, "maxLifetime": 28800},
          environmentVariables={
              "KVS_CHANNEL_NAME": "${var.kvs_channel_name}",
              "AWS_REGION": "${var.aws_region}",
              "BEDROCK_KB_ID": "${var.knowledge_base_id}",
              "CLOUDFRONT_ORIGIN": "${var.cloudfront_origin}",
              "CONTAINER_ENV": "true",
          },
          metadataConfiguration={"requireMMDSV2": True},
      )

      for _ in range(120):
          state = client.get_agent_runtime(agentRuntimeId=runtime_id)["status"]
          if state == "READY":
              break
          if state.endswith("FAILED"):
              raise RuntimeError(f"AgentCore runtime entered {state}")
          time.sleep(5)
      else:
          raise TimeoutError("Timed out waiting for AgentCore runtime update")
      PYTHON
    EOF
  }
}
