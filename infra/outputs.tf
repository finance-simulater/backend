output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.web.id
}

output "ec2_public_ip" {
  description = "Elastic IP attached to EC2"
  value       = aws_eip.web.public_ip
}

output "ssh_command" {
  description = "SSH command template"
  value       = "ssh -i <your-key.pem> ubuntu@${aws_eip.web.public_ip}"
}

output "api_docs_url" {
  description = "Temporary API docs URL after app is running"
  value       = "http://${aws_eip.web.public_ip}/docs"
}

output "rds_endpoint" {
  description = "RDS MySQL endpoint"
  value       = aws_db_instance.mysql.endpoint
}

output "rds_database_url_template" {
  description = "DATABASE_URL template for .env.prod"
  value       = "mysql+pymysql://${var.db_username}:<db_password>@${aws_db_instance.mysql.endpoint}/${var.db_name}"
}

output "frontend_bucket_name" {
  description = "S3 bucket for frontend build artifacts"
  value       = aws_s3_bucket.frontend.bucket
}

output "frontend_cloudfront_distribution_id" {
  description = "CloudFront distribution ID for frontend"
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_cloudfront_domain_name" {
  description = "CloudFront domain name for frontend"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_url" {
  description = "Frontend URL"
  value       = length(var.frontend_domain_names) > 0 ? "https://${var.frontend_domain_names[0]}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "upload_bucket_name" {
  description = "S3 bucket for user-uploaded files"
  value       = aws_s3_bucket.uploads.bucket
}
