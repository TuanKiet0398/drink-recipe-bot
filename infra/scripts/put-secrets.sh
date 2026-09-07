#!/usr/bin/env bash
# Exports the values in backend/.env as TF_VAR_* so `terraform apply` can
# store them in SSM without retyping. Source it, don't run it:
#
#   source infra/scripts/put-secrets.sh
set -euo pipefail

ENV_FILE="${1:-backend/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "No such env file: $ENV_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  case "$key" in
    OPENAI_API_KEY) export TF_VAR_openai_api_key="$value" ;;
    ENCRYPTION_KEY) export TF_VAR_encryption_key="$value" ;;
    ADMIN_USERNAME) export TF_VAR_admin_username="$value" ;;
    ADMIN_PASSWORD) export TF_VAR_admin_password="$value" ;;
  esac
done < "$ENV_FILE"

TF_VAR_allowed_cidr="$(curl -s ifconfig.me)/32"
export TF_VAR_allowed_cidr
echo "Exported TF_VAR_* from $ENV_FILE; allowed_cidr=$TF_VAR_allowed_cidr"
echo "Still needed: TF_VAR_grafana_admin_password, TF_VAR_ghcr_token, TF_VAR_ssh_public_key"
