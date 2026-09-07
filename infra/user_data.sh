#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker fail2ban jq
# Amazon Linux 2023 ships the compose plugin separately.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

systemctl enable --now docker
systemctl enable --now fail2ban
usermod -aG docker ec2-user

# Key-only SSH. Port 22 accepts the wide GitHub Actions range, so password
# auth must be off.
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

mkdir -p /opt/matcha
chown ec2-user:ec2-user /opt/matcha

# Render /opt/matcha/.env from SSM. The instance profile allows reading
# only /${project}/*.
# JSON, not --output text: a value containing whitespace (an admin password,
# say) would be truncated by field-splitting.
aws ssm get-parameters-by-path \
  --region "${region}" \
  --path "/${project}" \
  --with-decryption \
  --output json \
  | jq -r '.Parameters[] | "\(.Name | split("/") | last)=\(.Value)"' \
  > /opt/matcha/.env
chmod 600 /opt/matcha/.env
chown ec2-user:ec2-user /opt/matcha/.env

echo "${ghcr_token}" | docker login ghcr.io -u "${ghcr_username}" --password-stdin
mkdir -p /home/ec2-user/.docker
cp /root/.docker/config.json /home/ec2-user/.docker/config.json
chown -R ec2-user:ec2-user /home/ec2-user/.docker

cat > /etc/systemd/system/matcha.service <<'UNIT'
[Unit]
Description=Matcha Bot stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/matcha
EnvironmentFile=/opt/matcha/.env
# The compose file arrives with the first deploy, so a boot before that
# must not fail the unit.
ExecStart=/bin/bash -c 'test -f docker-compose.prod.yml && docker compose -f docker-compose.prod.yml up -d || true'
ExecStop=/bin/bash -c 'test -f docker-compose.prod.yml && docker compose -f docker-compose.prod.yml down || true'

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable matcha.service
