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
