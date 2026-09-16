# Variables — {{SERVICE_NAME}}
# 13 variables del CONTRATO-BANCO.md.
# Los VALORES los inyecta el banco (terraform.tfvars, Vault, CI/CD).

# --- Infra AWS ---

variable "aws_region" {
  description = "Región AWS del clúster EKS"
  type        = string
  default     = "eu-west-1"
}

variable "vpc_id" {
  description = "VPC donde reside el clúster EKS"
  type        = string
}

variable "subnet_ids" {
  description = "Subnets del clúster EKS"
  type        = list(string)
}

# --- Kubernetes / Despliegue ---

variable "namespace" {
  description = "Namespace de Kubernetes para el microservicio"
  type        = string
  default     = "{{SERVICE_NAME}}"
}

variable "docker_registry" {
  description = "Registry de imágenes Docker (ECR, ACR, Harbor)"
  type        = string
}

variable "image_tag" {
  description = "Tag de la imagen Docker a desplegar"
  type        = string
  default     = "latest"
}

# --- Aplicación ---

variable "app_env" {
  description = "Entorno de ejecución (production, staging, development)"
  type        = string
  default     = "production"
}

variable "app_host" {
  description = "Host de escucha del microservicio"
  type        = string
  default     = "0.0.0.0"
}

# --- Base de datos ---

variable "database_url" {
  description = "URL de conexión a PostgreSQL (app, read-write)"
  type        = string
  sensitive   = true
}

variable "llamaindex_database_url" {
  description = "URL de conexión a PostgreSQL (LLM, solo SELECT)"
  type        = string
  sensitive   = true
}

variable "postgres_user" {
  description = "Usuario de PostgreSQL"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "Contraseña de PostgreSQL"
  type        = string
  sensitive   = true
}

variable "postgres_db" {
  description = "Nombre de la base de datos PostgreSQL"
  type        = string
}

# --- LLM / IA ---

variable "anthropic_api_key" {
  description = "Token de la pasarela LLM (Anthropic / Bedrock)"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "Token de la pasarela de embeddings (OpenAI / Azure)"
  type        = string
  sensitive   = true
}
