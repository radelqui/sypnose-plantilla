# T14 — Experience with CI/CD tools

## Oferta (nice-to-have, literal de `oferta-coforge.txt`)

> Experience with CI/CD tools.

## Solución

El pipeline GitHub Actions (`.github/workflows/ci.yml`) integra cinco
herramientas de CI/CD, todas pinadas por commit SHA (estándar bancario):

- **gitleaks** — escaneo de secretos en el historial completo (primer paso,
  antes de que GitGuardian avise).
- **ruff** — lint rápido de Python.
- **bandit** — análisis estático de seguridad (SAST).
- **pytest** — tests con cobertura ≥85 % contra Postgres+pgvector en vivo.
- **Trivy** — escaneo de vulnerabilidades de la imagen Docker
  (CRITICAL/HIGH, exit-code 1) antes de publicar a ghcr.io.

## R1 — Herramientas CI/CD integradas y pinadas

**EARS:**
> El workflow CI/CD DEBE integrar escaneo de secretos (gitleaks), lint (ruff),
> SAST (bandit), tests (pytest) y escaneo de vulnerabilidades de contenedor
> (Trivy), cada uno pinado por commit SHA.

**Comprobación ejecutable** (determinista — verifica que las 5 herramientas
están referenciadas en el workflow):

```bash
python -c "w=open('.github/workflows/ci.yml').read();assert all(t in w for t in ['gitleaks','trivy','bandit','ruff','pytest']);print('ok')"
```

Resultado esperado: `ok`

---
Chat: 01-git-cicd
Model: claude-opus-4-6
Plan: PLAN-CS-T14
Tarea: 46
