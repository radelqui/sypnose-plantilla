# T07 — Participate in CI/CD implementation and deployment processes

## Oferta (línea 7, literal de `oferta-coforge.txt`)

> Participate in CI/CD implementation and deployment processes

## Solución

`rag-banking-agent` tiene un pipeline GitHub Actions (`.github/workflows/ci.yml`)
con tres jobs secuenciales: **test** → **build-and-push** → **deploy**.

- **test**: escaneo de secretos (gitleaks), lint (ruff), SAST (bandit), tests con
  cobertura ≥85 % (`pytest --cov=app --cov-fail-under=85`) contra Postgres+pgvector
  en vivo (service container con `secrets.CI_PG_PASSWORD`, cero literales en YAML).
- **build-and-push**: Docker multi-stage build (`python:3.11-slim`), escaneo Trivy
  (CRITICAL/HIGH, `exit-code: 1`, `ignore-unfixed: true`) ANTES de publicar, push a
  `ghcr.io` solo si el escaneo pasa.
- **deploy**: environment `production` con required reviewers — puerta de aprobación
  humana. Hasta que un revisor autorizado apruebe, el despliegue no ocurre.

Las 6 actions están pinadas por SHA (estándar bancario: sin tags movibles).
Concurrency group por rama con `cancel-in-progress` para PRs.

El pipeline se disparó en `main` (run 34983669221). Los dos primeros jobs
completaron en verde; el tercero quedó en "waiting" — la puerta humana funciona.

## R1 — Pipeline CI/CD completo con puerta de aprobación humana

**EARS:**
> Cuando un push a `main` dispare el pipeline CI/CD, el sistema DEBE ejecutar
> escaneo de secretos, lint, SAST, tests con cobertura ≥85 %, build Docker,
> escaneo de vulnerabilidades Trivy y push a ghcr.io en secuencia; el job de
> deploy DEBE quedar detenido esperando aprobación humana en el environment
> `production` antes de proceder.

**Comprobación ejecutable** (determinista — un run en "waiting" prueba que test y
build-and-push pasaron y que deploy está bloqueado por la puerta humana):

```bash
gh run view 34983669221 --repo radelqui/rag-banking-agent --json status --jq '.status'
```

Resultado esperado: `waiting`

---
Chat: 01-git-cicd
Model: claude-opus-4-6
Plan: PLAN-CS-T07
Tarea: 39
