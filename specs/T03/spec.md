# T03 — Design, build, and consume RESTful APIs and microservices

## Oferta (línea 3, literal de `oferta-coforge.txt`)

> Design, build, and consume RESTful APIs and microservices

## Solución

`rag-banking-agent` expone un API REST versionado (`/api/v1`) con un único
endpoint de negocio (`/consultar`) que responde en streaming SSE. El diseño
separa las responsabilidades en capas independientes que se componen en
`app.api.routes`:

- **Identidad**: `app.security.identity.get_customer_id` extrae y valida la
  cabecera `X-Customer-Id` que inyecta la pasarela del banco (OAuth2/AD). Si
  falta o es malformada → HTTP 401 inmediato, el LLM nunca se invoca. El LLM
  nunca elige el cliente.
- **Streaming SSE**: la respuesta se transmite token a token como `event: token`,
  con cierre `event: done`. Los errores del motor (timeout, excepción) se
  emiten como `event: error` dentro del stream, no como HTTP 500 — el cliente
  SSE siempre recibe una señal de fin.
- **PII en stream**: `StreamMasker` enmascara datos sensibles token a token,
  incluso cuando el LLM parte una entidad entre chunks (ver T05 para el
  detalle del masker).
- **Guardrails**: `check_prompt` bloquea inyecciones y prompts inválidos antes
  del LLM → HTTP 400 (ver T05 para el detalle de las reglas).
- **Validación de schema**: `QueryRequest` (Pydantic) rechaza body inválido →
  HTTP 422.

## R1 — Endpoint /consultar con SSE, identidad y manejo de errores

**EARS:**
> El endpoint `/api/v1/consultar` DEBE responder con Server-Sent Events (SSE)
> en streaming. DEBE requerir la cabecera `X-Customer-Id` (inyectada por la
> pasarela del banco) y rechazar con HTTP 401 peticiones sin ella o con un ID
> malformado (vacío, inyección SQL, demasiado largo). Los errores del motor
> DEBEN emitirse como `event: error` SSE, nunca como excepciones HTTP no
> controladas. Los campos del body DEBEN validarse por el schema Pydantic
> (`pregunta` no vacía → HTTP 422).

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
pytest tests/test_api.py tests/test_identity.py -k "consultar or identity"
```

Casos concretos que hacen cumplir el EARS:

**Streaming SSE:**
- `tests/test_api.py::test_consultar_streams_sse` — respuesta SSE con tokens,
  `event: done` al final, content-type `text/event-stream`. El motor recibe el
  customer_id de la cabecera, no del prompt.
- `tests/test_api.py::test_consultar_masks_pii_in_stream` — IBAN dividido entre
  tokens se enmascara en el stream SSE.
- `tests/test_api.py::test_consultar_engine_error_emits_sse_error` — excepción
  del motor → `event: error` en el stream, no HTTP 500.

**Identidad (X-Customer-Id):**
- `tests/test_api.py::test_consultar_requires_identity` — sin cabecera → HTTP
  401, el motor nunca se invoca.
- `tests/test_api.py::test_consultar_rejects_forged_identity` — ID con inyección
  SQL (`C1' OR 1=1`) → HTTP 401.
- `tests/test_identity.py::test_reads_identity_from_gateway_header` — extrae y
  normaliza el ID de la cabecera (strip).
- `tests/test_identity.py::test_rejects_missing_or_forged_identity` — 4 variantes
  (None, vacío, inyección, demasiado largo) → HTTP 401.

**Validación y guardrails:**
- `tests/test_api.py::test_consultar_blocks_injection` — prompt con inyección →
  HTTP 400, motor nunca invocado.
- `tests/test_api.py::test_consultar_validation_error` — pregunta vacía → HTTP
  422 (schema Pydantic).

**Evidencia (02-backend-api, worktree `chat/02-backend-api`, 2026-09-15,
comprobación literal sin `-q`):**

```
$ pytest tests/test_api.py tests/test_identity.py -k "consultar or identity"
............                                                             [100%]
12 passed, 3 deselected in 1.22s
```

(Los 3 deselected son los tests de health probes: `test_liveness`,
`test_readiness_ok`, `test_readiness_503_when_engine_missing` — pertenecen a
T15, no a T03.)

## R2 — no necesario (evitar solapamiento)

T15 cubre los health probes K8s (`-k "liveness or readiness"`). T01 cubre el
arranque fail-loud. T05 cubre el PII masker y los guardrails como módulos
independientes. T10 cubre la encapsulación OOP de tools. Con R1 cerrado, T03
queda cubierto con el contrato REST completo del endpoint de negocio sin solapar.

---
Chat: 02-backend-api
Model: claude-opus-4-6
Plan: PLAN-CS-T03
Tarea: 35
