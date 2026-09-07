output "public_ip" {
  description = "Elastic IP. Put this in the EC2_HOST GitHub secret."
  value       = aws_eip.app.public_ip
}

output "ssh_command" {
  description = "Ready-to-paste SSH command."
  value       = "ssh -i matcha-deploy.pem ec2-user@${aws_eip.app.public_ip}"
}

output "grafana_url" {
  description = "Grafana, reachable only from allowed_cidr."
  value       = "http://${aws_eip.app.public_ip}:3000"
}

output "admin_url" {
  description = "Admin SPA, reachable only from allowed_cidr."
  value       = "http://${aws_eip.app.public_ip}"
}
