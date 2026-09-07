terraform {
  required_version = ">= 1.6"

  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.0" }
    http = { source = "hashicorp/http", version = "~> 3.4" }
  }

  # State is local and gitignored. A single operator does not need a remote
  # backend, and bootstrapping S3 + DynamoDB for state is its own chicken
  # and egg problem. Back the file up by hand; losing it orphans resources.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# GitHub publishes the CIDR ranges its Actions runners use. The deploy job
# SSHes in from one of them, so port 22 must accept them. The list is large
# and changes over time — re-apply periodically to refresh it.
data "http" "github_meta" {
  url = "https://api.github.com/meta"
}

locals {
  # cidr_blocks cannot hold IPv6 ranges, so drop them.
  github_actions_cidrs = [
    for cidr in jsondecode(data.http.github_meta.response_body).actions :
    cidr if !strcontains(cidr, ":")
  ]
}
