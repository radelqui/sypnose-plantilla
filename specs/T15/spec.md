# T15 — Knowledge of microservices architecture

## Oferta (línea 15, literal de `oferta-coforge.txt`)

> Knowledge of microservices architecture

## Solución

`rag-banking-agent` es un microservicio FastAPI contenerizado que demuestra
patrones fundamentales de arquitectura de microservicios:

- **Health probes K8s**: `/api/v1/health/live` (liveness) y `/api/v1/health/ready`
  (readiness) permiten al orquestador de contenedores saber si el pod está vivo
  y si puede recibir tráfico. El readiness devuelve 503 cuando el motor no está
  cargado — sin esto, Kubernetes encamina peticiones a un pod que no puede
  responder.
- **Readiness gate**: `app.state.engine` se evalúa en cada readiness check. Si
  el lifespan no completó (motor no cargado) o el motor se liberó (shutdown),
  el pod nunca se anuncia "listo". Esto complementa el fail-loud de T01: T01
  impide arrancar sin credenciales; T15 impide servir sin motor.
- **Dockerfile multi-stage**: builder instala dependencias, runtime solo copia
  el resultado. Usuario sin privilegios (`appuser`, UID 10001). HEALTHCHECK
  integrado que valida el liveness cada 30s.
- **12-factor config**: `app.core.config.Settings` (Pydantic) lee TODO de
  variables de entorno; el código conoce nombres, no valores. Sin `.env`
  hardcodeado en la imagen.

## R1 — Health probes y readiness gate

**EARS:**
> Cuando el motor del servicio NO esté cargado (`app.state.engine is None`), el
> endpoint de readiness (`/api/v1/health/ready`) DEBE devolver HTTP 503 para que
> el orquestador de contenedores no encamine tráfico al pod. Cuando el motor SÍ
> esté cargado, DEBE devolver HTTP 200. El endpoint de liveness
> (`/api/v1/health/live`) DEBE devolver HTTP 200 siempre que el proceso esté
> activo.

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
pytest tests/test_api.py -k "liveness or readiness"
```

Casos concretos que hacen cumplir el EARS:

- `tests/test_api.py::test_liveness` — liveness devuelve 200 +
  `{"status":"alive"}`. Siempre que el proceso esté activo.
- `tests/test_api.py::test_readiness_ok` — readiness devuelve 200 cuando el
  motor está cargado (fixture `client` inyecta FakeEngine).
- `tests/test_api.py::test_readiness_503_when_engine_missing` — readiness
  devuelve 503 cuando `engine=None`. Es el caso real: si el lifespan falla o
  el shutdown ya ocurrió, Kubernetes NO encamina tráfico.

**Evidencia (02-backend-api, worktree `chat/02-backend-api`, 2026-09-15,
comprobación literal sin `-q`):**

```
$ pytest tests/test_api.py -k "liveness or readiness"
...                                                                      [100%]
3 passed, 7 deselected in 1.67s
```

## R2 — no necesario (evitar solapamiento)

T03 ("Design, build, and consume RESTful APIs and microservices") cubre el
contrato REST completo: `/consultar` con SSE, PII masking, identidad
(`X-Customer-Id`), prompt guardrails y manejo de errores. T01 cubre el arranque
fail-loud. El Dockerfile (HEALTHCHECK, non-root, multi-stage) se verifica por el
pipeline CI (Trivy scan, build multi-stage). Con R1 cerrado, T15 queda cubierto
sin solapar las otras líneas.

## Corrección sobre el encargo (Ley del Arquitecto §11)

El encargo del Lead mencionaba "tests del API y del Dockerfile/health". Para el
Dockerfile, no hay un test unitario determinista (`hadolint` y Trivy están en el
pipeline CI, no en `pytest`); se documenta la estructura (multi-stage, non-root,
HEALTHCHECK) como contexto arquitectónico. La comprobación ejecutable se centra
en los 3 tests de health probes, que son lo que K8s realmente evalúa en runtime.

---
Chat: 02-backend-api
Model: claude-opus-4-6
Plan: PLAN-CS-T15
Tarea: 47
