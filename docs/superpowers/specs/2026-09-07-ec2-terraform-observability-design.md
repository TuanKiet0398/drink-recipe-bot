# EC2 Deployment (Terraform) + Prometheus/Grafana Observability — Design

## Context

The Matcha Bot repo has application code, tests, a Docker Compose file for local
development, and a GitHub Actions workflow that runs tests and pushes images to GHCR.
It has no infrastructure-as-code, no deployment target, and no runtime monitoring.
The only operational signal today is the `token_usage` table and the admin Usage page,
which are read manually through the admin SPA.

This spec covers two tightly coupled subsystems:

- **Infrastructure** — Terraform that provisions a single EC2 instance to run the
  whole stack as containers, plus the CD step that ships new images to it.
- **Observability** — Prometheus metrics exported by the backend, scraped alongside
  host and container metrics, and rendered in a provisioned Grafana dashboard.

They are specified together because the Terraform instance must be sized and
configured for the monitoring containers it will host.

### Explicitly out of scope

The following belong to separate specs and must not be pulled into this work:

- LLM tracing (Langfuse/LangSmith/OpenTelemetry), evaluation datasets, quality
  scoring, and Telegram thumbs-up/down feedback.
- Alertmanager and alert delivery channels (Slack, Telegram, email). Prometheus
  will evaluate alert rules; alerts are viewed in the Grafana UI only.
- S3 remote state for Terraform.
- HTTPS, custom domains, load balancing, auto-scaling, multi-AZ, RDS.
- Log aggregation (Loki). Logs stay accessible via `docker logs`.

## Goals

1. `terraform apply` from an empty AWS account produces a running host, reproducibly.
2. A manually triggered GitHub Actions run deploys the current images to that host and
   fails loudly if the deployed backend is not healthy.
3. Grafana shows host health, HTTP traffic, and LLM token/cost/latency without any
   manual dashboard configuration.
4. No change to the bot's behaviour, and no new externally reachable attack surface
   beyond the two ports described below.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Compute | One EC2 instance, `t3.small` | `t3.micro` (1 GB) cannot hold chromadb plus Grafana plus Prometheus. |
| Configuration management | `user_data` only, no Ansible | One host; a second tool is not justified. |
| Persistence | Docker named volumes on the root EBS volume | No RDS, no EFS. Matches the current local setup, so no application change. |
| Terraform state | Local file, gitignored | Single operator. An S3 backend needs its own bootstrap; deferred. |
| Deploy trigger | `workflow_dispatch` only | Production releases stay a deliberate human action. |
| Deploy transport | SSH with a `.pem` key from GitHub Actions | Simple and debuggable. See the port 22 decision below. |
| Alerting | Prometheus rules, viewed in Grafana | Alertmanager deferred. |

## Infrastructure

### Layout

```
infra/
  main.tf                  # provider, data sources (default VPC/subnet, AL2023 AMI)
  network.tf               # security group
  compute.tf               # aws_instance, aws_eip, aws_key_pair, root EBS
  iam.tf                   # instance profile allowing ssm:GetParametersByPath on /matcha/*
  ssm.tf                   # SecureString parameters
  outputs.tf               # public_ip, ssh_command, grafana_url
  variables.tf
  terraform.tfvars.example
  user_data.sh
  scripts/put-secrets.sh
  README.md
```

### Variables

`region`, `instance_type` (default `t3.small`), `root_volume_size_gb` (default 30),
`allowed_cidr` (the operator's home IP as `x.x.x.x/32`), `ssh_public_key`,
`ghcr_username`, `ghcr_token`, `daily_cost_alert_usd` (default 5).

### Networking

The default VPC and its subnets are used via data sources; no VPC is created.

Security group ingress:

| Port | Source | Purpose |
|---|---|---|
| 80 | `var.allowed_cidr` | Admin SPA (nginx), which proxies `/admin/` to the backend |
| 3000 | `var.allowed_cidr` | Grafana |
| 22 | `var.allowed_cidr` **and** the GitHub Actions IP ranges | Operator SSH and the deploy job |

The GitHub Actions ranges come from a Terraform `http` data source reading
`https://api.github.com/meta` and using its `actions` list. This range is large and
changes over time, so `terraform apply` must be re-run periodically to refresh it; the
README states this. Prometheus (9090), cadvisor, node_exporter, and the backend's own
port are not published to the host at all — they are reachable only inside the Docker
network. Egress is unrestricted.

Password authentication over SSH is disabled in `user_data`; only the public key from
`var.ssh_public_key` is accepted.

### Secrets

`OPENAI_API_KEY`, `ENCRYPTION_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and
`GRAFANA_ADMIN_PASSWORD` are stored as SSM `SecureString` parameters under `/matcha/`.
Terraform declares the parameters; their values arrive through `TF_VAR_*` environment
variables and are never written to a committed `.tfvars` file. `infra/scripts/put-secrets.sh`
reads the operator's local `backend/.env` and writes the parameters, so the values do not
have to be retyped.

The instance profile grants `ssm:GetParametersByPath` and `kms:Decrypt` scoped to
`/matcha/*` only.

### user_data.sh

On first boot the instance:

1. Installs Docker, the Compose plugin, the AWS CLI, and fail2ban; enables and starts Docker.
2. Creates `/opt/matcha`.
3. Fetches `/matcha/*` from SSM and writes `/opt/matcha/.env` with mode `0600`.
4. Runs `docker login ghcr.io` using `var.ghcr_username` / `var.ghcr_token`.
5. Installs a systemd unit `matcha.service` that runs
   `docker compose -f /opt/matcha/docker-compose.prod.yml up -d` on boot, so the stack
   returns after an instance reboot.

The unit tolerates the compose file being absent on the very first boot; the first
deploy run puts it there.

## Runtime composition

`docker-compose.yml` is unchanged and remains the local development file that builds
from source. A new `docker-compose.prod.yml` pulls published images and adds the
monitoring stack.

| Service | Image | Published port | Notes |
|---|---|---|---|
| backend | `ghcr.io/<repo>-backend:${IMAGE_TAG:-latest}` | none | volume `backend_data` at `/app/data` |
| frontend | `ghcr.io/<repo>-frontend:${IMAGE_TAG:-latest}` | 80 | nginx already proxies `/admin/` |
| prometheus | `prom/prometheus` | none | volume `prom_data`; `--storage.tsdb.retention.time=15d`; `mem_limit: 400m` |
| grafana | `grafana/grafana` | 3000 | volume `grafana_data`; admin password from `.env`; `mem_limit: 300m` |
| node_exporter | `prom/node-exporter` | none | `/proc`, `/sys`, `/` mounted read-only |
| cadvisor | `gcr.io/cadvisor/cadvisor` | none | per-container CPU/memory |

Using `${IMAGE_TAG:-latest}` makes rollback a matter of setting `IMAGE_TAG` to an older
commit SHA in `/opt/matcha/.env` and re-running `docker compose up -d`.

### Monitoring configuration

```
monitoring/
  prometheus.yml
  alerts.yml
  grafana/
    provisioning/datasources/prometheus.yml
    provisioning/dashboards/dashboards.yml
    dashboards/matcha-overview.json
```

Scrape jobs at a 15-second interval: `backend` (`backend:8000/metrics`), `node`
(`node_exporter:9100`), `cadvisor` (`cadvisor:8080`), and `prometheus` itself.

Alert rules:

| Rule | Condition |
|---|---|
| `BackendDown` | `up{job="backend"} == 0` for 2m |
| `HighLLMErrorRate` | error share of `llm_calls_total` above 10% over 5m |
| `DailyCostExceeded` | 24h increase of `llm_cost_usd_total` above `daily_cost_alert_usd` |
| `DiskAlmostFull` | root filesystem free space below 15% |
| `HighMemory` | host memory usage above 90% for 10m |
| `TelegramPollFailing` | `telegram_poll_errors_total` increasing for 5m |

`matcha-overview.json` has four rows: Health (targets up, host CPU/memory/disk), HTTP
(request rate, p50/p95 latency, status codes), LLM (tokens by model, cumulative cost,
per-node latency, retrieved chunk count), and Telegram (messages per minute by channel,
poll errors). Datasource and dashboard are provisioned from these files, so the
dashboard lives in git and survives container replacement. Dashboard changes are made
by editing the JSON, not by clicking in Grafana.

## Backend instrumentation

Three existing choke points make instrumentation local rather than scattered:

- `log_token_usage()` in `app/token_usage.py` is called by every OpenAI call site
  (`nodes.py:84`, `:114`, `:138`, `:227`, `:243`).
- `retry_once()` in `app/retry.py` wraps every LLM and embedding call.
- `build_graph()` in `app/agent/graph.py:12-17` registers all three graph nodes in one place.

### New module: `app/metrics.py`

| Metric | Type | Labels |
|---|---|---|
| `llm_tokens_total` | Counter | `model`, `call_type`, `kind` (`prompt`/`completion`) |
| `llm_cost_usd_total` | Counter | `model`, `call_type` |
| `llm_calls_total` | Counter | `model`, `call_type`, `outcome` (`ok`/`error`) |
| `llm_retries_total` | Counter | `call_type` |
| `agent_node_duration_seconds` | Histogram | `node` |
| `retrieve_chunks_returned` | Histogram | — |
| `telegram_messages_total` | Counter | `channel_id`, `direction` (`in`/`out`) |
| `telegram_poll_errors_total` | Counter | `channel_id` |
| `active_channels` | Gauge | — |

**Label cardinality rule:** no metric may carry a per-user or per-conversation label.
`user_id`, `telegram_user_id`, `chat_id`, and message text are forbidden as label values.
`channel_id` is permitted because channels are few and administrator-created.

Cost is derived from `MODEL_PRICES: dict[str, tuple[float, float]]` — USD per million
prompt and completion tokens — defined in `metrics.py` and overridable at runtime via a
`MODEL_PRICES_JSON` environment variable, so a price change does not require a rebuild.
An unknown model contributes zero cost and logs a warning once. The dashboard labels the
cost panel as an estimate; the authoritative figure is the provider's bill.

### Changes to existing files

| File | Change |
|---|---|
| `app/token_usage.py` | call `record_llm_usage()` after the successful commit; the function must keep never raising |
| `app/retry.py` | add an optional `call_type` argument (default `"unknown"`); increment `llm_retries_total` and `llm_calls_total{outcome}` |
| `app/agent/graph.py` | wrap the three node lambdas in a timing decorator that observes `agent_node_duration_seconds` |
| `app/agent/nodes.py` | observe `retrieve_chunks_returned` after reranking |
| `app/channel_manager.py` | set `active_channels` after each `sync()` |
| `app/telegram_poller.py` | count inbound messages and poll errors |
| `app/routers/webhook.py` | count outbound messages |
| `app/routers/metrics.py` | new router exposing `GET /metrics` via `generate_latest()`, without `require_admin` |
| `app/main.py` | include the metrics router; attach `prometheus-fastapi-instrumentator` for HTTP latency and status metrics |
| `backend/pyproject.toml` | add `prometheus-client`, `prometheus-fastapi-instrumentator`, and `ruff` (dev) |

`/metrics` is unauthenticated because Prometheus cannot present Basic Auth credentials.
It is not externally reachable: `frontend/nginx.conf` proxies only `location /admin/`,
and the backend publishes no host port in `docker-compose.prod.yml`.

**Failure isolation:** every metric operation is wrapped so that a metrics failure can
never break a customer reply, following the existing pattern in `log_token_usage`.

## CI/CD

`.github/workflows/deploy.yml` keeps `workflow_dispatch` as its only trigger. No `push`
trigger is added.

The existing `test` job gains four checks: `ruff check` and `ruff format --check` for the
backend, `promtool check config` and `promtool check rules` for `monitoring/`,
`terraform fmt -check` and `terraform validate` for `infra/`, and
`docker compose -f docker-compose.prod.yml config` to catch YAML and variable errors.
`terraform plan` is not run in CI, as it would require AWS credentials.

A third job `deploy` runs after `build-and-push`, under the `production` environment:

1. Checkout.
2. Copy `docker-compose.prod.yml` and `monitoring/` to `/opt/matcha` over `scp`.
3. Over SSH: `docker compose pull`, `docker compose up -d`, `docker image prune -f`.
4. Health check: `curl http://localhost/health` from the instance, retried up to 30 times
   at 2-second intervals; the job fails if it never succeeds.

Shipping `monitoring/` on every deploy is what makes the Prometheus and Grafana
configuration version-controlled rather than hand-edited on the host.

New GitHub Secrets: `EC2_HOST` (the Elastic IP), `EC2_SSH_KEY` (the private key matching
`var.ssh_public_key`), `EC2_USER` (`ec2-user`), and `GHCR_TOKEN` (a PAT with
`read:packages`, used by the instance to pull private images).

### First-time bootstrap

Documented in `infra/README.md`:

1. `aws configure`.
2. `infra/scripts/put-secrets.sh` to populate SSM from the local `backend/.env`.
3. `terraform init && terraform apply` with `TF_VAR_allowed_cidr=$(curl -s ifconfig.me)/32`.
4. Put the `public_ip` output into the `EC2_HOST` GitHub Secret.
5. Run the `Deploy` workflow manually.
6. Open `http://<ip>:3000` and sign in to Grafana; the dashboard is already provisioned.

Because the address is an Elastic IP, instance replacement does not change `EC2_HOST`.
Changing the operator's home IP requires only `terraform apply` with a new
`allowed_cidr`, which modifies the security group without touching the instance.

## Testing

`backend/tests/test_metrics.py` is added and covers:

- `GET /metrics` returns 200 and its body contains the expected metric names.
- `record_llm_usage` computes the correct cost for a priced model and zero for an
  unknown model, without raising.
- `retry_once` increments `llm_retries_total` and records `outcome="ok"` when the first
  attempt fails and the second succeeds, and `outcome="error"` when both fail.
- The graph node wrapper records an observation in `agent_node_duration_seconds`.

The existing suite must stay green, in particular `test_token_usage.py`,
`test_agent_graph.py`, and `test_health.py`.

Before any `terraform apply`, `docker-compose.prod.yml` is run locally against
locally built images to confirm Grafana comes up with a populated dashboard.
Debugging the compose stack over SSH on a `t3.small` is slow enough to be worth avoiding.

## Risks

- **Stale price table.** Provider prices change, so the cost metric drifts. Mitigated by
  the `MODEL_PRICES_JSON` override and by labelling the panel an estimate.
- **Disk exhaustion.** Prometheus, Chroma, and SQLite share the root volume. Mitigated by
  a 15-day retention window, a 30 GB volume, and the `DiskAlmostFull` alert.
- **Broad SSH exposure.** The GitHub Actions ranges are wide and shift over time. Mitigated
  by key-only authentication, fail2ban, and periodic re-apply. Moving the deploy job to
  SSM Run Command would remove this exposure entirely and is the natural follow-up if the
  range proves unmanageable.
- **Local Terraform state.** Loss of the state file orphans the resources. Mitigated by
  manual backup; an S3 backend is the planned follow-up.
- **Single point of failure.** One instance means downtime during replacement, and the
  Docker volumes are not backed up. Accepted for this stage and recorded here so it is a
  known trade-off rather than an oversight.

## Implementation order

Each step is independently verifiable:

1. `app/metrics.py`, the instrumentation edits, and `test_metrics.py`; verify with
   `pytest` and `curl localhost:8000/metrics`.
2. `monitoring/` and `docker-compose.prod.yml`; verify locally that the dashboard shows data.
3. `infra/` Terraform and `user_data.sh`; verify with `plan`, then `apply`.
4. The `deploy` job and the new CI gates.
5. `infra/README.md`, updates to the root `README.md`, and the architecture diagram.
