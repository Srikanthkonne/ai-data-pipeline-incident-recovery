resource "aws_secretsmanager_secret" "gemini_api_key" {
  name        = "${local.resource_prefix}/gemini-api-key"
  description = "Gemini API key used by the autonomous incident recovery worker."
}
