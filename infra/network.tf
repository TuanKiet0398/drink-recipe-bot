resource "aws_security_group" "app" {
  name        = "${var.project}-app"
  description = "Matcha Bot host: admin UI, Grafana, and SSH"
  vpc_id      = data.aws_vpc.default.id

  # Prometheus (9090), cadvisor, node_exporter and the backend itself are
  # deliberately absent — they publish no host port and are reachable only
  # inside the Docker network.
  ingress {
    description = "Admin SPA"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "Grafana"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "SSH from the operator and from GitHub Actions runners"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = concat([var.allowed_cidr], local.github_actions_cidrs)
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
