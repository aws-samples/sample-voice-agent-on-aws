# -----------------------------------------------------------------------------
# Generate frontend .env.old from Terraform values
# -----------------------------------------------------------------------------

resource "local_file" "frontend_env" {
  filename = "${var.frontend_source_dir}/.env"
  content  = <<-EOF
    VITE_USER_POOL_ID=${var.cognito_user_pool_id}
    VITE_USER_POOL_CLIENT_ID=${var.cognito_client_id}
    VITE_IDENTITY_POOL_ID=${var.cognito_identity_pool_id}
    VITE_REGION=${var.aws_region}
    VITE_AGENT_RUNTIME_ARN=${var.agent_runtime_arn}
  EOF
}

# -----------------------------------------------------------------------------
# Build + deploy frontend
# -----------------------------------------------------------------------------

locals {
  src_hash = sha1(join("", [
    for f in sort(fileset(var.frontend_source_dir, "src/**"))
    : filesha1("${var.frontend_source_dir}/${f}")
  ]))
}

resource "terraform_data" "frontend_deploy" {
  triggers_replace = "${local.src_hash}-${local_file.frontend_env.content_sha1}"

  provisioner "local-exec" {
    environment = {
      AWS_PROFILE = var.aws_profile != null ? var.aws_profile : ""
    }
    command = <<-EOF
      set -e
      SRC="$(cd "${var.frontend_source_dir}" && pwd)"
      cd "$SRC" && npm run build
      aws s3 sync "$SRC/dist/" "s3://${var.frontend_bucket_name}/" --exclude "*.DS_Store" --delete
      aws cloudfront create-invalidation --distribution-id "${var.cloudfront_distribution_id}" --paths "/*"
    EOF
  }

  depends_on = [local_file.frontend_env]
}
