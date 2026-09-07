variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-southeast-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro (1GB) cannot hold chromadb plus Grafana plus Prometheus."
  type        = string
  default     = "t3.small"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size. Holds Docker images, SQLite, Chroma, and 15 days of Prometheus data."
  type        = number
  default     = 30
}

variable "allowed_cidr" {
  description = "Operator's home IP in CIDR form, e.g. 203.0.113.4/32. Grants access to ports 80, 3000, and 22."
  type        = string
}

variable "ssh_public_key" {
  description = "Public half of the deploy keypair. The private .pem goes into the EC2_SSH_KEY GitHub secret."
  type        = string
}

variable "ghcr_username" {
  description = "GitHub username used by the instance to docker login ghcr.io."
  type        = string
}

variable "ghcr_token" {
  description = "GitHub PAT with read:packages, used by the instance to pull private images."
  type        = string
  sensitive   = true
}

variable "ghcr_repo" {
  description = "owner/repo in lowercase, used to build image names."
  type        = string
}

variable "openai_api_key" {
  description = "Stored as an SSM SecureString. Pass via TF_VAR_openai_api_key, never a committed tfvars file."
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "AES-GCM key for channel credentials. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "admin_username" {
  description = "Admin dashboard Basic Auth username."
  type        = string
  default     = "admin"
}

variable "admin_password" {
  description = "Admin dashboard Basic Auth password. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "matcha"
}
