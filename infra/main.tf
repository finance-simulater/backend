terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

locals {
  frontend_bucket_name = var.frontend_bucket_name != "" ? var.frontend_bucket_name : "${var.project_name}-frontend-${data.aws_caller_identity.current.account_id}"
  frontend_origin_id   = "${var.project_name}-frontend-s3-origin"
  upload_bucket_name   = var.upload_bucket_name != "" ? var.upload_bucket_name : "${var.project_name}-uploads-${data.aws_caller_identity.current.account_id}"
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "web" {
  name               = "${var.project_name}-web-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name    = "${var.project_name}-web-role"
    Project = var.project_name
  }
}

resource "aws_iam_instance_profile" "web" {
  name = "${var.project_name}-web-instance-profile"
  role = aws_iam_role.web.name
}

resource "aws_security_group" "web" {
  name        = "${var.project_name}-web-sg"
  description = "Allow SSH from my IP and HTTP/HTTPS from internet"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from allowed IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-web-sg"
    Project = var.project_name
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow MySQL from local IP and EC2"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "MySQL from local IP"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description     = "MySQL from EC2"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-rds-sg"
    Project = var.project_name
  }
}

resource "aws_instance" "web" {
  ami                         = data.aws_ami.ubuntu_2204.id
  instance_type               = var.instance_type
  key_name                    = var.key_pair_name
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.web.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.web.name

  user_data = <<-EOF
    #!/bin/bash
    set -eux
    apt-get update -y
    apt-get remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc || true
    apt-get install -y ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $${UBUNTU_CODENAME:-$${VERSION_CODENAME}} stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    usermod -aG docker ubuntu
    systemctl enable docker
    systemctl start docker
  EOF

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}

resource "aws_eip" "web" {
  domain = "vpc"

  tags = {
    Name    = "${var.project_name}-eip"
    Project = var.project_name
  }
}

resource "aws_eip_association" "web" {
  instance_id   = aws_instance.web.id
  allocation_id = aws_eip.web.id
}

resource "aws_db_subnet_group" "mysql" {
  name       = "${var.project_name}-mysql-subnet-group"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name    = "${var.project_name}-mysql-subnet-group"
    Project = var.project_name
  }
}

resource "aws_db_instance" "mysql" {
  identifier             = var.db_identifier
  engine                 = "mysql"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage
  storage_type           = "gp2"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.mysql.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = var.db_publicly_accessible

  backup_retention_period = 0
  deletion_protection     = false
  skip_final_snapshot     = true

  tags = {
    Name    = var.db_identifier
    Project = var.project_name
  }
}

resource "aws_s3_bucket" "frontend" {
  bucket        = local.frontend_bucket_name
  force_destroy = var.frontend_bucket_force_destroy

  tags = {
    Name    = local.frontend_bucket_name
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project_name}-frontend-oac"
  description                       = "CloudFront access control for frontend S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} frontend"
  default_root_object = "index.html"
  aliases             = var.frontend_domain_names

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
    origin_id                = local.frontend_origin_id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = local.frontend_origin_id
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    compress               = true
  }

  custom_error_response {
    error_code            = 403
    error_caching_min_ttl = 0
    response_code         = 200
    response_page_path    = "/index.html"
  }

  custom_error_response {
    error_code            = 404
    error_caching_min_ttl = 0
    response_code         = 200
    response_page_path    = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.frontend_acm_certificate_arn != "" ? var.frontend_acm_certificate_arn : null
    cloudfront_default_certificate = var.frontend_acm_certificate_arn == "" ? true : null
    minimum_protocol_version       = var.frontend_acm_certificate_arn != "" ? "TLSv1.2_2021" : null
    ssl_support_method             = var.frontend_acm_certificate_arn != "" ? "sni-only" : null
  }

  tags = {
    Name    = "${var.project_name}-frontend-cdn"
    Project = var.project_name
  }

  lifecycle {
    precondition {
      condition     = length(var.frontend_domain_names) == 0 || var.frontend_acm_certificate_arn != ""
      error_message = "frontend_acm_certificate_arn is required when frontend_domain_names is set."
    }
  }
}

data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    sid     = "AllowCloudFrontServicePrincipalReadOnly"
    actions = ["s3:GetObject"]

    resources = [
      "${aws_s3_bucket.frontend.arn}/*",
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json
}

resource "aws_s3_bucket" "uploads" {
  bucket        = local.upload_bucket_name
  force_destroy = var.upload_bucket_force_destroy

  tags = {
    Name    = local.upload_bucket_name
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD", "POST", "PUT"]
    allowed_origins = var.upload_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

data "aws_iam_policy_document" "web_uploads_s3" {
  statement {
    sid = "AllowUploadBucketObjectAccess"

    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.uploads.arn}/*",
    ]
  }

  statement {
    sid = "AllowUploadBucketList"

    actions = [
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.uploads.arn,
    ]
  }
}

resource "aws_iam_role_policy" "web_uploads_s3" {
  name   = "${var.project_name}-uploads-s3-access"
  role   = aws_iam_role.web.id
  policy = data.aws_iam_policy_document.web_uploads_s3.json
}
