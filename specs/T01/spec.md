# T01 — Develop and maintain web applications using Python for backend services

## Oferta (línea 1, literal de `oferta-coforge.txt`)

> Develop and maintain web applications using Python for backend services

## Solución

`rag-banking-agent` es un servicio FastAPI (`app/main.py`) con dos motores de
consulta intercambiables detrás del mismo contrato `QueryEngineLike.astream()`:
RAG puro (`LlamaIndexEngine`) o agente con tools bancarias (`AgentEngine`,
PLAN-0001), seleccionados por la variable de entorno `ENGINE_MODE`.

Mantener un backend Python en producción significa, ante todo, que el servicio
nunca mienta sobre su propio estado: si `ENGINE_MODE` pide un motor real (`rag`
o `agent`) y faltan las credenciales de los modelos de frontera
(`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`), el pod no puede anunciarse "listo" y
luego fallar en silencio en cada petición — eso es exactamente lo que un banco
no puede permitirse (ver hallazgo B1 de 07-verificador sobre el commit
`97ede33`, corregido en `c6e1407`).

- `app.main._select_engine_mode`: decide la rama (`fake`/`rag`/`agent`) sin
  construir nada. `USE_FAKE_ENGINE=1` siempre gana sobre `ENGINE_MODE`, así el
  desarrollo local y los tests nunca acaban exigiendo credenciales reales.
- `app.main._require_llm_credentials`: para los modos reales, valida las
  credenciales ANTES de tocar BD/LLM. Si faltan, lanza `RuntimeError` con el
  nombre exacto de la variable que falta — el lifespan de FastAPI revienta y
  el pod nunca llega a `/health/ready`.

## R1 — Arranque fail-loud del motor real

**EARS:**
> Cuando el servicio arranque con `ENGINE_MODE=rag` o `ENGINE_MODE=agent` (motor
> real) y falte `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`, el sistema DEBE fallar
> antes de alcanzar `ready`, con un mensaje que identifique la credencial
> concreta que falta. Cuando `USE_FAKE_ENGINE=1` esté presente, el sistema DEBE
> arrancar sin necesitar BD ni LLM reales, sin importar `ENGINE_MODE`.

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
pytest tests/test_main.py tests/test_engine_mode.py
```

(Sin `-q`: con `addopts = -q` ya en `pytest.ini`, añadir otro `-q` sube a `-qq` y
pytest deja de imprimir la línea `N passed` — la evidencia de la entrega se
quedaba solo con los puntos. Corrección pedida por el Lead tras revisar una
ENTREGA real.)

Casos concretos que hacen cumplir el EARS (no solo "verde genérico"):

- `tests/test_engine_mode.py::test_agent_mode_without_credentials_fails_at_startup_not_silently`
  — `ENGINE_MODE=agent` sin claves → `create_app()` + `lifespan_context` lanza
  `RuntimeError`, nunca llega a `ready`. Es la regresión directa de B1.
- `tests/test_engine_mode.py::test_require_llm_credentials_raises_when_both_missing`
  / `..._raises_when_only_one_missing` / `..._passes_when_both_present` — las 3
  combinaciones del guard.
- `tests/test_engine_mode.py::test_construct_real_engine_never_touches_infra_without_credentials`
  — sin credenciales, ni siquiera se intenta construir `LlamaIndexEngine`/`AgentEngine`.
- `tests/test_main.py::test_create_app_with_fake_engine` — `USE_FAKE_ENGINE=1`
  arranca sin BD ni LLM.

**Evidencia (02-backend-api, worktree `chat/02-backend-api`, 2026-09-15, comprobación
literal sin `-q`):**

```
$ pytest tests/test_main.py tests/test_engine_mode.py
...............                                                          [100%]
15 passed in 1.20s
```

## R2 — no necesario (evitar solapamiento)

La línea 1 también podría leerse como "el backend expone un contrato HTTP
operable" (health checks, etc.), pero eso ya lo cubre por completo T-03
(`oferta.yaml`, línea "Design, build, and consume RESTful APIs and
microservices") con su propio EARS y `pytest tests/test_api.py -q`. Duplicarlo
aquí como R2 solaparía dos líneas de la oferta sobre el mismo código
(`app/api/routes.py::liveness/readiness`). Con R1 cerrado, T-01 queda cubierto.

## Corrección sobre el encargo (Ley del Arquitecto §11)

El encargo original pedía incluir `pytest tests/test_api.py -k identidad` en la
comprobación de R1. Verificado ahora mismo:

```
$ pytest tests/test_api.py -k identidad -v
collected 10 items / 10 deselected / 0 selected
```

**0 tests seleccionados** — falso positivo: los tests reales se llaman
`test_consultar_requires_identity` / `test_consultar_rejects_forged_identity`
(inglés, "identity", no "identidad"). Un `-k identidad` así nunca falla porque
nunca verifica nada; habría quedado como comprobación "verde" sin comprobar
nada, justo el defecto que motivó devolver la tarea 33.

Además, esos dos tests son sobre la identidad del cliente en `/consultar`
(cabecera `X-Customer-Id`), que es el EARS de **T-03**, no de T-01 (que trata
del arranque del servicio, no de la autenticación por request). Los dejo fuera
de R1 y los doy por cubiertos donde sí encajan: la comprobación de T-03
(`pytest tests/test_api.py -q`, ya en `oferta.yaml`) los incluye sin filtro y
sí pasan (`pytest tests/test_api.py -k identity -v` → 2 passed).

No se tocó `oferta.yaml` — eso es terreno de 05-arquitecto-sypnose (registro);
este documento es la base para que lo cargue con la barrera correcta.

---
Chat: 02-backend-api
Model: claude-sonnet-5
Plan: PLAN-CS-T01
Tarea: T01.R0
