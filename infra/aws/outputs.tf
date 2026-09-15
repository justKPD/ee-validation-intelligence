output "url" { value = "http://${aws_lb.main.dns_name}" }
output "api_url" { value = "http://${aws_lb.main.dns_name}:8080" }
output "api_repository" { value = aws_ecr_repository.api.repository_url }
output "web_repository" { value = aws_ecr_repository.web.repository_url }
output "artefact_bucket" { value = aws_s3_bucket.artefacts.bucket }
output "database_url_secret" { value = aws_secretsmanager_secret.db_url.arn }
