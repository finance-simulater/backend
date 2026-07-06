variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "Project name used for AWS resource names"
  type        = string
  default     = "finance-simulater"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_pair_name" {
  description = "Existing AWS EC2 key pair name"
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "Deprecated. Single CIDR allowed to SSH into EC2, e.g. 123.123.123.123/32. Prefer ssh_allowed_cidrs."
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to SSH into EC2, e.g. [\"123.123.123.123/32\"]"
  type        = list(string)
  default     = []
}

variable "db_identifier" {
  description = "RDS DB instance identifier"
  type        = string
  default     = "finance-mysql"
}

variable "db_name" {
  description = "Initial MySQL database name"
  type        = string
  default     = "finance"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "finance_admin"
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "db_password must be at least 8 characters."
  }
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_publicly_accessible" {
  description = "Allow public RDS endpoint for learning/local access"
  type        = bool
  default     = true
}

variable "frontend_bucket_name" {
  description = "S3 bucket name for frontend build artifacts. Leave empty to generate one from project name and AWS account ID."
  type        = string
  default     = ""
}

variable "frontend_bucket_force_destroy" {
  description = "Allow Terraform to delete the frontend S3 bucket even when it contains files."
  type        = bool
  default     = false
}

variable "frontend_domain_names" {
  description = "Optional custom frontend domain names for CloudFront aliases. ACM certificate must be in us-east-1 when this is set."
  type        = list(string)
  default     = []
}

variable "frontend_acm_certificate_arn" {
  description = "Optional ACM certificate ARN for CloudFront custom domain. The certificate must be issued in us-east-1."
  type        = string
  default     = ""

  validation {
    condition     = var.frontend_acm_certificate_arn == "" || can(regex(":us-east-1:", var.frontend_acm_certificate_arn))
    error_message = "frontend_acm_certificate_arn must be empty or an ACM certificate ARN from us-east-1."
  }
}

variable "upload_bucket_name" {
  description = "S3 bucket name for user-uploaded files. Leave empty to generate one from project name and AWS account ID."
  type        = string
  default     = ""
}

variable "upload_bucket_force_destroy" {
  description = "Allow Terraform to delete the upload S3 bucket even when it contains files."
  type        = bool
  default     = false
}

variable "upload_allowed_origins" {
  description = "Browser origins allowed to upload directly to the upload S3 bucket with presigned URLs."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://localhost:5173",
  ]

  validation {
    condition     = length(var.upload_allowed_origins) > 0
    error_message = "upload_allowed_origins must contain at least one origin."
  }
}
