# CONTRATO-BANCO.md

> Generado automáticamente por `generar_contrato_banco.py` desde `oferta.yaml` § stack.
> NO editar a mano: editar oferta.yaml y regenerar.

Este documento lista cada tecnología del stack, lo que el POC implementa,
lo que el banco puede decidir sustituir, y los ficheros/variables que cambian.
0 secretos en código: solo NOMBRES de variables; los VALORES los inyecta el banco.

## Variables de entorno (inyectadas por el banco)

| Variable | Origen |
|----------|--------|
| `ANTHROPIC_API_KEY` | K8s Secret / Vault |
| `APP_ENV` | K8s Secret / Vault |
| `APP_HOST` | K8s Secret / Vault |
| `APP_PORT` | K8s Secret / Vault |
| `DATABASE_URL` | K8s Secret / Vault |
| `DOCKER_REGISTRY` | K8s Secret / Vault |
| `IMAGE_TAG` | K8s Secret / Vault |
| `LLAMAINDEX_DATABASE_URL` | K8s Secret / Vault |
| `NAMESPACE` | K8s Secret / Vault |
| `OPENAI_API_KEY` | K8s Secret / Vault |
| `POSTGRES_DB` | K8s Secret / Vault |
| `POSTGRES_PASSWORD` | K8s Secret / Vault |
| `POSTGRES_USER` | K8s Secret / Vault |

## Lenguaje y framework backend

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| Python 3.11 | Lenguaje del microservicio, tipado estricto, async nativo | Versión de Python aprobada (3.11+ preferido por async y typing) | Dockerfile (FROM), .github/workflows/ci.yml (python-version), requirements*.txt | — |
| FastAPI + Uvicorn | Framework HTTP async con OpenAPI automática | Framework HTTP: Flask, Django REST, framework interno del banco | requirements.txt, app/main.py (app factory), Dockerfile (CMD) | `APP_HOST`, `APP_PORT` |
| Pydantic / pydantic-settings | Validación de esquemas y configuración por entorno | Validación: marshmallow, attrs, o schema del framework elegido | requirements.txt, app/core/config.py, app/api/schemas.py | `APP_ENV` |
| SSE (Server-Sent Events) | Streaming de tokens del agente al cliente en tiempo real | Streaming: WebSocket, gRPC streaming, polling largo | requirements.txt, app/api/routes.py (streaming handler) | — |
| Registro SQLite con raíles y triggers | Base de datos de evidencia con reglas D4/D7/C8 como triggers SQL | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| MCP sypnose (registro) | Servidor MCP que expone lectura/escritura del registro a los chats | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| MCP knowledge-hub (KB) | Servidor MCP para la base de conocimiento del proyecto | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |

## Base de datos

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| SQLAlchemy 2 async + asyncpg | ORM async con pool de conexiones para PostgreSQL | ORM/driver: psycopg2 sync, Django ORM, driver propietario del banco | requirements.txt, app/core/db.py, docker-compose.yml (env vars) | `DATABASE_URL`, `LLAMAINDEX_DATABASE_URL` |
| PostgreSQL 16 + pgvector | Base de datos relacional con extensión vectorial para RAG híbrido | PostgreSQL del banco con pgvector aprobado; versión y extensiones según DBA | docker-compose.yml (imagen), scripts/init_db.sql (extensión y roles), app/core/config.py (URLs) | `DATABASE_URL`, `LLAMAINDEX_DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| Índices HNSW + GIN/tsvector | Búsqueda semántica (HNSW cosine) + texto exacto (GIN tsvector español) | Parámetros HNSW (m, ef_construction), idioma de tsvector, política de reindexado | scripts/init_db.sql (parámetros de índice y configuración de idioma) | — |

## IA y agentes

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| LlamaIndex (core + postgres + anthropic + openai) | RAG con retriever híbrido (vectores + texto), FunctionTool, FunctionAgent | Framework RAG: LangChain, Haystack, SDK directo del LLM, framework interno | requirements.txt, app/rag/engine.py, app/agent/tools.py, scripts/ingest.py | `LLAMAINDEX_DATABASE_URL` |
| Modelo de frontera (Anthropic API) | LLM para razonamiento del agente bancario | LLM provider: Amazon Bedrock, Azure OpenAI, pasarela interna, modelo on-premise | requirements.txt (llm adapter), app/core/config.py (ANTHROPIC_API_KEY → var nueva), k8s/deployment.yaml (secretos) | `ANTHROPIC_API_KEY` |
| Modelo de embeddings (OpenAI API) | Generación de vectores 1536d para búsqueda semántica | Embeddings provider: Azure OpenAI, Bedrock Titan, Cohere, modelo local | requirements.txt (embeddings adapter), app/core/config.py (OPENAI_API_KEY → var nueva), scripts/init_db.sql (dimensión vector) | `OPENAI_API_KEY` |

## Contenedores y despliegue

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| Docker multi-stage slim + docker-compose | Imagen mínima non-root para producción; entorno local reproducible | Registry: Harbor, ACR, ECR, GHCR; imagen base aprobada por seguridad | Dockerfile (FROM base image), .github/workflows/ci.yml (registry login), docker-compose.yml | `DOCKER_REGISTRY` |
| Kubernetes (Deployment + Service + HPA) | Orquestación con escalado automático, probes y secretos | Plataforma: EKS, AKS, OpenShift, GKE; políticas de red, RBAC y Secrets→Vault | k8s/deployment.yaml (apiVersion, securityContext, registry, secretRef→Vault), k8s/secrets.example.yaml | `NAMESPACE`, `IMAGE_TAG` |

## CI/CD y calidad

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| GitHub Actions (CI/CD) | Pipeline test→build→scan→deploy con aprobación humana | CI/CD: Jenkins, Azure DevOps, GitLab CI, Tekton | .github/workflows/ci.yml → pipeline equivalente en la herramienta elegida | — |
| pytest + pytest-asyncio + httpx | Tests unitarios e integración async con cobertura mínima 85% | Framework de tests compatible; umbral de cobertura según política | requirements-dev.txt, .github/workflows/ci.yml (comando test) | — |
| ruff | Linter rápido (reemplaza flake8+isort+pyupgrade) | Linter: flake8, pylint, SonarQube policy engine | requirements-dev.txt, .github/workflows/ci.yml (lint step), pyproject.toml | — |
| bandit | SAST para Python (detecta inyecciones, eval, secretos) | SAST: SonarQube, Snyk Code, Checkmarx, Fortify | requirements-dev.txt, .github/workflows/ci.yml (SAST step) | — |
| trivy | Escaneo de vulnerabilidades de imagen Docker (CRITICAL+HIGH) | Escaneo de imagen: Snyk Container, Prisma Cloud, Aqua, Grype | .github/workflows/ci.yml (scan step, action/plugin) | — |
| Scripts con barrera (hash + backup) | Toda escritura al registro pasa verificación de hashes canónicos y backup | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| Caparazón de hooks (11 módulos) | Cerco, auditoría git, brief, stop, commit-msg para cada sesión de chat | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| Verificador independiente + segundo verificador | 07-verificador verifica cada tarea; D7b impide auto-verificación por rol | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| Firmas por delegación | 05-arquitecto firma tareas y líneas tras veredicto de 07 | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |

## Prácticas de ingeniería

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| Spec-Driven Development (EARS) | Requisitos EARS antes del código; comprobación literal única por tarea | Formato de spec: OpenSpec, Spec Kit, Gherkin, formato interno del banco | specs/Txx/spec.md (formato), comprobar_esqueleto.py (parser) | — |
| TDD con puerta de cobertura ≥85% | Tests como entrega; CI bloquea merge si cobertura < 85% | N/A (práctica de ingeniería, no tecnología sustituible) | — | — |
| Revisión independiente (D7) | Verificador distinto del autor; triggers SQL impiden auto-verificación | N/A (práctica de ingeniería, no tecnología sustituible) | — | — |
| Trunk-based por chat (rama + trailers) | Cada chat en su rama con trailers Chat/Model/Plan/Tarea en commit-msg | N/A (práctica de ingeniería, no tecnología sustituible) | — | — |
| Decisiones fechadas (ADR equivalente) | Decisiones numeradas y fechadas en PLAN.md y TRASPASO-* como ADR ligero | N/A (práctica de ingeniería, no tecnología sustituible) | — | — |
| FinOps por evento (coste_turno_usd) | Coste por turno y por actor registrado en cada evento del registro | N/A (práctica de ingeniería, no tecnología sustituible) | — | — |
| Claude Agent SDK (Claude Code) | La fábrica SYPNOSE corre sobre Claude Code, construido sobre el Claude Agent SDK: agentes por chat con hooks, MCP y permisos | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |

## Opcional / futuro

| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |
|------------|------------------|------------------------|------------|-----------|
| React/Vue con EventSource | Frontend SPA que consume SSE del agente | Framework frontend: React, Angular, Vue, micro-frontend interno | nuevo directorio frontend/, package.json, .github/workflows/ci.yml (build frontend) | — |
| Claude Agent SDK (producto) | Implementar el agente ¿Cómo estoy hecho? con el SDK de Anthropic en lugar de LlamaIndex | Bedrock vía SDK de AWS o SDK de Anthropic directo | app/como_estoy_hecho/agente.py (adaptador de motor) | — |
| AWS EKS + IAM + Secrets Manager | Plataforma Kubernetes gestionada con integración IAM y secretos nativos | EKS, AKS, OpenShift, GKE, plataforma interna del banco | microservicio/esqueleto/terraform/ (módulos EKS, IAM, Secrets Manager) | — |
| Amazon Bedrock | Acceso a modelos de frontera vía API gestionada de AWS con IAM | Bedrock, Azure OpenAI, API directa de Anthropic, modelo on-premise | requirements.txt (boto3 + bedrock adapter), app/core/config.py | — |
| Terraform | Infraestructura como código para el despliegue en AWS | Terraform, CloudFormation, Pulumi, CDK, herramienta interna del banco | microservicio/esqueleto/terraform/ | — |
| Temporal.io | Orquestación de workflows durables para procesos bancarios complejos | Temporal, Step Functions, Airflow, herramienta interna del banco | requirements.txt (temporalio), app/workflows/ | — |
| OpenTelemetry | Observabilidad distribuida (traces, métricas, logs) estándar CNCF | Backend: Datadog, Grafana Cloud, Elastic APM, Jaeger, herramienta interna | requirements.txt (opentelemetry-*), app/core/telemetry.py, microservicio/esqueleto/app/main.py | — |
| Vista pública (09-sypnose-vista) | Página web con el estado del proyecto para stakeholders | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| KB de lecciones aprendidas | Base de conocimiento con alertas, feedback y lecciones del proyecto | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |
| graphify (knowledge graph) | Transforma el registro en grafo de conocimiento navegable | N/A (artefacto de proceso de desarrollo, no entra en producción) | — | — |

## Notas

- Las tecnologías del bloque **plantilla** (registro SQLite, barrera, caparazón, MCP, verificador,
  firmas, vista pública, KB, graphify) son artefactos del proceso de desarrollo SYPNOSE.
  No entran en producción del banco y no requieren decisión.
- Cada variable listada se inyecta vía K8s Secret o Vault; el código solo lee el nombre.
- Para sustituir una tecnología, modificar `oferta.yaml` § stack y regenerar este fichero:
  `python3 generar_contrato_banco.py`
