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
  description = "CIDR allowed to SSH into EC2, e.g. 123.123.123.123/32"
  type        = string
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
