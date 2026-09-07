resource "aws_key_pair" "deploy" {
  key_name   = "${var.project}-deploy"
  public_key = var.ssh_public_key
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = aws_key_pair.deploy.key_name
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    project       = var.project
    region        = var.region
    ghcr_username = var.ghcr_username
    ghcr_token    = var.ghcr_token
  })

  # Changing user_data alone should not silently leave a stale host: the
  # instance is replaced so the new bootstrap actually runs.
  user_data_replace_on_change = true

  tags = { Name = "${var.project}-app" }

  depends_on = [aws_ssm_parameter.secret]
}

# An Elastic IP means instance replacement does not change EC2_HOST.
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = { Name = "${var.project}-app" }
}
