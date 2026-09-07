# Infrastructure

One EC2 instance running the whole stack as containers, provisioned by
Terraform. State is local and gitignored — back up `infra/terraform.tfstate`
by hand, because losing it orphans the resources.

## First-time bootstrap

1. Configure AWS credentials:

   ```bash
   aws configure
   ```

2. Generate the deploy keypair:

   ```bash
   ssh-keygen -t ed25519 -f matcha-deploy -C matcha-deploy -N ""
   ```

   `matcha-deploy` (the private half) goes into the `EC2_SSH_KEY` GitHub
   secret. `matcha-deploy.pub` goes into `TF_VAR_ssh_public_key`.

3. Export the variables:

   ```bash
   source infra/scripts/put-secrets.sh
   export TF_VAR_ssh_public_key="$(cat matcha-deploy.pub)"
   export TF_VAR_grafana_admin_password='pick-something-strong'
   export TF_VAR_ghcr_token='ghp_...'          # needs read:packages
   export TF_VAR_ghcr_username='your-username'
   export TF_VAR_ghcr_repo='your-username/mlops_project'
   ```

4. Apply:

   ```bash
   cd infra && terraform init && terraform apply
   ```

5. Put the `public_ip` output into the `EC2_HOST` GitHub secret, alongside
   `EC2_USER` (`ec2-user`), `EC2_SSH_KEY`, and `GHCR_TOKEN`.

6. Run the `Deploy` workflow manually from the Actions tab.

7. Open the `grafana_url` output and sign in as `admin` with
   `TF_VAR_grafana_admin_password`. The "Matcha Bot Overview" dashboard is
   already provisioned.

## Routine operations

**Your home IP changed.** Re-apply with the new value; only the security
group changes, and the instance is untouched:

```bash
export TF_VAR_allowed_cidr="$(curl -s ifconfig.me)/32"
cd infra && terraform apply
```

**GitHub's Actions IP ranges changed** and deploys started timing out.
Re-apply — the ranges are read live from `api.github.com/meta` on every
plan:

```bash
cd infra && terraform apply
```

**Roll back to an earlier build.** Images are tagged with both `latest` and
the commit SHA:

```bash
ssh -i matcha-deploy.pem ec2-user@<ip>
cd /opt/matcha
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=<old-sha>/' .env
docker compose --env-file ./.env -f docker-compose.prod.yml up -d
```

**Change an alert threshold or a dashboard panel.** Edit the file under
`monitoring/`, commit, and run the `Deploy` workflow — the deploy copies
`monitoring/` to the host every time. Do not edit dashboards in the Grafana
UI; `allowUiUpdates` is off and edits would be lost.

**Change a model price.** Set `MODEL_PRICES_JSON` in `/opt/matcha/.env`,
e.g. `MODEL_PRICES_JSON={"gpt-4o-mini":[0.15,0.6]}`, then restart the
backend. No rebuild needed.

**Look at Prometheus directly.** It publishes no host port, so tunnel to it:

```bash
ssh -i matcha-deploy.pem -L 9090:localhost:9090 ec2-user@<ip> \
  'docker compose -f /opt/matcha/docker-compose.prod.yml port prometheus 9090'
```

Simpler: use Grafana's Explore tab, which queries the same data.

## What runs where

| Service | Host port | Reachable from |
|---|---|---|
| frontend (nginx, admin SPA) | 80 | `allowed_cidr` only |
| grafana | 3000 | `allowed_cidr` only |
| backend | none | inside the Docker network |
| prometheus | none | inside the Docker network |
| node_exporter, cadvisor | none | inside the Docker network |

The backend's `/metrics` endpoint is unauthenticated because Prometheus
cannot present Basic Auth. It stays private because the backend publishes no
host port and nginx proxies only `/admin/` and `/health`.

## Known trade-offs

- Single instance: replacing it means downtime, and the Docker volumes are
  not backed up.
- Local Terraform state: no locking, no history, no team access.
- Port 22 accepts the whole GitHub Actions range, which is wide. Key-only
  authentication and fail2ban are the mitigations; moving the deploy job to
  SSM Run Command would remove the exposure entirely.
- Cost figures in Grafana are estimates from a hard-coded price table
  (`backend/app/metrics.py`). The provider's bill is authoritative.

## Using Ollama

The LLM provider is chosen in the admin panel under Settings, not in Terraform.

Two things to know when pointing it at Ollama:

- **Do not run Ollama on this instance.** A `t3.small` has 2 GB of RAM, which the
  application stack and the monitoring stack already share. Run Ollama on a
  separate host and give its URL in the Settings page.
- **Port 11434 is not open.** The security group opens only 80, 3000, and 22. If
  the Ollama host is reachable over the public internet it needs no change here;
  if you place it inside the VPC, add an egress path deliberately rather than
  widening ingress.

When the backend runs in Docker on a developer machine, `http://localhost:11434`
points at the container itself. Use `http://host.docker.internal:11434/v1`.

Embeddings never follow this setting — they always use OpenAI's
`text-embedding-3-small`, because the Chroma index is built with it.
