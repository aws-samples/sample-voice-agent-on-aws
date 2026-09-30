# -----------------------------------------------------------------------------
# Optional random suffix for globally unique bucket names
# -----------------------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  count       = var.unique_bucket_suffix ? 1 : 0
  byte_length = 4
  keepers = {
    project_name = var.project_name
    environment  = var.environment
  }
}

locals {
  bucket_suffix = var.unique_bucket_suffix ? "-${random_id.bucket_suffix[0].hex}" : ""
}

# S3 bucket for frontend static files
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-${var.environment}-frontend${local.bucket_suffix}"

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend${local.bucket_suffix}"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
