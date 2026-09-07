# Values arrive through TF_VAR_* environment variables and land in state,
# which is why state is gitignored and must be treated as a secret file.
locals {
  secrets = {
    OPENAI_API_KEY         = var.openai_api_key
    ENCRYPTION_KEY         = var.encryption_key
    ADMIN_USERNAME         = var.admin_username
    ADMIN_PASSWORD         = var.admin_password
    GRAFANA_ADMIN_PASSWORD = var.grafana_admin_password
    GHCR_REPO              = var.ghcr_repo
  }
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.secrets

  name  = "/${var.project}/${each.key}"
  type  = "SecureString"
  value = each.value
}
