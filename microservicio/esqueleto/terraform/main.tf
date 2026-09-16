# Terraform — {{SERVICE_NAME}}
# Providers y módulos base para despliegue en EKS/AKS.
# 0 secretos en código: solo nombres de variables; los valores los inyecta el banco.

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_ca)
  token                  = module.eks.cluster_token
}

# --- EKS ---

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.namespace
  cluster_version = "1.29"

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  eks_managed_node_groups = {
    default = {
      instance_types = ["t3.medium"]
      min_size       = 1
      max_size       = 3
      desired_size   = 2
    }
  }
}

# --- Namespace ---

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.namespace
    labels = {
      app = "{{SERVICE_NAME}}"
    }
  }
}

# --- Secrets (solo nombres, valores inyectados por Vault / External Secrets) ---

resource "kubernetes_secret" "db" {
  metadata {
    name      = "{{SERVICE_NAME}}-db-secrets"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    DATABASE_URL            = var.database_url
    LLAMAINDEX_DATABASE_URL = var.llamaindex_database_url
    POSTGRES_USER           = var.postgres_user
    POSTGRES_PASSWORD       = var.postgres_password
    POSTGRES_DB             = var.postgres_db
  }

  type = "Opaque"
}

resource "kubernetes_secret" "llm" {
  metadata {
    name      = "{{SERVICE_NAME}}-llm-secrets"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    ANTHROPIC_API_KEY = var.anthropic_api_key
    OPENAI_API_KEY    = var.openai_api_key
  }

  type = "Opaque"
}

# --- Deployment ---

resource "kubernetes_deployment" "app" {
  metadata {
    name      = "{{SERVICE_NAME}}"
    namespace = kubernetes_namespace.app.metadata[0].name
    labels = {
      app = "{{SERVICE_NAME}}"
    }
  }

  spec {
    replicas = 2

    selector {
      match_labels = {
        app = "{{SERVICE_NAME}}"
      }
    }

    template {
      metadata {
        labels = {
          app = "{{SERVICE_NAME}}"
        }
      }

      spec {
        container {
          name  = "{{SERVICE_NAME}}"
          image = "${var.docker_registry}/{{SERVICE_NAME}}:${var.image_tag}"

          port {
            container_port = {{SERVICE_PORT}}
          }

          env {
            name  = "APP_ENV"
            value = var.app_env
          }

          env {
            name  = "APP_HOST"
            value = var.app_host
          }

          env {
            name  = "APP_PORT"
            value = "{{SERVICE_PORT}}"
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.db.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.llm.metadata[0].name
            }
          }

          resources {
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
          }

          security_context {
            read_only_root_filesystem = true
            run_as_non_root           = true
            capabilities {
              drop = ["ALL"]
            }
          }

          liveness_probe {
            http_get {
              path = "/api/v1/health/live"
              port = {{SERVICE_PORT}}
            }
            initial_delay_seconds = 10
            period_seconds        = 30
          }

          readiness_probe {
            http_get {
              path = "/api/v1/health/ready"
              port = {{SERVICE_PORT}}
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }
        }
      }
    }
  }
}

# --- Service ---

resource "kubernetes_service" "app" {
  metadata {
    name      = "{{SERVICE_NAME}}"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = {
      app = "{{SERVICE_NAME}}"
    }

    port {
      port        = {{SERVICE_PORT}}
      target_port = {{SERVICE_PORT}}
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}
