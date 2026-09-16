# Terraform — {{SERVICE_NAME}}

Infraestructura como código para desplegar `{{SERVICE_NAME}}` en **EKS** (AWS) o **AKS** (Azure).

## Requisitos previos

- Terraform >= 1.5
- Credenciales AWS configuradas (`aws configure`) o Azure CLI (`az login`)
- `kubectl` apuntando al clúster destino
- Fichero `terraform.tfvars` con los valores del banco (nunca se commitea)

## Despliegue en EKS (AWS)

```bash
# 1. Inicializar providers y backend
terraform init

# 2. Revisar el plan de cambios
terraform plan -var-file=terraform.tfvars

# 3. Aplicar la infraestructura
terraform apply -var-file=terraform.tfvars
```

## Despliegue en AKS (Azure)

Para AKS, sustituir el provider `aws` por `azurerm` y el módulo `eks` por el
equivalente `aks` del registro de Terraform. Los recursos de Kubernetes
(`kubernetes_namespace`, `kubernetes_deployment`, `kubernetes_secret`,
`kubernetes_service`) son idénticos porque usan el provider `kubernetes`
agnóstico de nube.

```bash
# 1. Inicializar providers y backend
terraform init

# 2. Revisar el plan de cambios
terraform plan -var-file=terraform.tfvars

# 3. Aplicar la infraestructura
terraform apply -var-file=terraform.tfvars
```

## Destruir la infraestructura

```bash
terraform destroy -var-file=terraform.tfvars
```

## Variables

Las 13 variables están definidas en `variables.tf`. Los valores sensibles
(contraseñas, tokens) se marcan con `sensitive = true` y nunca aparecen en
logs de Terraform.

Crear `terraform.tfvars` (excluido de git) con los valores del banco:

```hcl
aws_region              = "eu-west-1"
vpc_id                  = "vpc-xxxxxxxxx"
subnet_ids              = ["subnet-aaa", "subnet-bbb"]
namespace               = "{{SERVICE_NAME}}"
docker_registry         = "123456789.dkr.ecr.eu-west-1.amazonaws.com"
image_tag               = "v1.0.0"
app_env                 = "production"
app_host                = "0.0.0.0"
database_url            = "postgresql+asyncpg://app_user:pw@pg.banco.svc:5432/banco"
llamaindex_database_url = "postgresql+asyncpg://ai_readonly:pw@pg.banco.svc:5432/banco"
postgres_user           = "app_user"
postgres_password       = "changeme"
postgres_db             = "banco"
anthropic_api_key       = "token-pasarela"
openai_api_key          = "token-pasarela"
```

## Seguridad

- 0 secretos en código: solo nombres de variables.
- Los valores sensibles los inyecta el banco (K8s Secret / Vault / Secrets Manager).
- El contenedor corre como non-root con filesystem de solo lectura.
- Capabilities: drop ALL.
