# CloudFront Function - SPA URL rewriting
# Rewrites paths without file extensions to /index.html so React Router works
resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${var.project_name}-${var.environment}-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Rewrite SPA routes to index.html"
  publish = true

  code = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      if (uri.includes('.')) {
        return request;
      }
      request.uri = '/index.html';
      return request;
    }
  EOF
}

# OAC for S3 frontend bucket
resource "aws_cloudfront_origin_access_control" "s3" {
  name                              = "${var.project_name}-${var.environment}-s3-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# S3 bucket policy - allow CloudFront OAC to read frontend assets
resource "aws_s3_bucket_policy" "frontend" {
  bucket = var.frontend_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontOAC"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${var.frontend_bucket_arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
        }
      }
    }]
  })
}

# CloudFront Distribution - serves frontend from S3 only
# (no API origin - browser connects directly to AgentCore via SigV4-signed WebSocket)
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  comment             = "${var.project_name} ${var.environment}"
  default_root_object = "index.html"

  origin {
    domain_name              = var.frontend_bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.s3.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security_headers.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Use the managed CachingOptimized policy by name instead of hardcoded ID
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

# Security response headers - HSTS, X-Frame-Options, X-Content-Type-Options, etc.
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "${var.project_name}-${var.environment}-security-headers"

  security_headers_config {
    strict_transport_security {
      access_control_max_age_sec = 63072000
      include_subdomains         = true
      override                   = true
    }
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
  }
}
