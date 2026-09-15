# AWS deployment (Terraform)

**Status: authored, not applied.** The build machine had no Terraform binary and no AWS credentials, so no
cloud resources were created and no URL exists yet. CI runs `terraform fmt -check`, `init -backend=false` and `validate`.

| Resource | Purpose |
|---|---|
| VPC, 2 public + 2 private subnets | network |
| ALB | port 80 → web (Next.js); port 8080 → API (root paths, `/docs`) |
| ECS Fargate services `api`, `web` | containers from ECR |
| RDS PostgreSQL 16 (private, encrypted) | canonical store; URL in Secrets Manager |
| S3 (private, encrypted) | synthetic artefacts and benchmark reports |
| CloudWatch log groups | container logs and OpenTelemetry console spans |

Before the web image is built, point the UI at the load balancer so the browser calls the API through it:
`--build-arg NEXT_PUBLIC_API_URL=http://<alb-dns>:8080` (the `api_url` output). The API image seeds the database from seed 42 on start.

```bash
cd infra/aws
terraform init && terraform apply
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -f infra/docker/api.Dockerfile -t <api_repository>:latest . && docker push <api_repository>:latest
docker build -f infra/docker/web.Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://<alb-dns>:8080 -t <web_repository>:latest . && docker push <web_repository>:latest
aws ecs update-service --cluster ee-validation --service api --force-new-deployment
```

Cost note: RDS db.t4g.micro, two small Fargate tasks and an ALB run continuously. Run `terraform destroy` when you are not demoing.
HTTPS (ACM certificate + 443 listener) is intentionally left for a real domain.
