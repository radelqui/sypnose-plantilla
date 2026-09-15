# T10 — Understanding of software design principles and object-oriented programming

## Oferta (línea 10, literal de `oferta-coforge.txt`)

> Understanding of software design principles and object-oriented programming

## Solución

`rag-banking-agent` aplica principios de diseño OOP para proteger la identidad
del cliente y prevenir inyección en las tools bancarias del agente (PLAN-0001):

- **Encapsulación (bind_tools)**: `app.agent.tools.bind_tools(engine, customer_id)`
  devuelve funciones con el `customer_id` ya atado internamente. La firma
  resultante de `get_account_balance` tiene 0 parámetros — el LLM NO puede
  elegir ni ver el identificador del cliente. Si intenta colar uno como kwarg,
  la tool revienta con un error genérico (H2/H3), nunca con el nombre interno.
- **Validación de entradas (principio de mínimo privilegio)**: cada tool valida
  IDs y códigos de producto con regex estricto ANTES de tocar la BD. Un ID
  malformado (`"1; DROP TABLE"`, `"a'b"`) se rechaza sin ejecutar SQL.
- **SQL parametrizado (no concatenación)**: `get_account_balance` usa `:cid` como
  bind parameter; el customer_id NUNCA aparece en el texto SQL. Igual con
  `get_product_info` y su `:code`.
- **Protocol (structural typing)**: `RagEngineLike` y `QueryEngineLike` definen
  contratos sin herencia — cualquier objeto con `astream(question, customer_id)`
  es un motor válido. Esto permite FakeEngine en tests y LlamaIndexEngine/
  AgentEngine en producción sin acoplar.

## R1 — Encapsulación de identidad y validación de entradas en tools

**EARS:**
> Cuando el agente construya tools bancarias para un cliente, las funciones
> resultantes DEBEN ocultar el `customer_id` al LLM (`bind_tools` reduce la
> firma a 0 parámetros de identidad) y DEBEN validar todas las entradas contra
> inyección (SQL parametrizado con `:cid`, regex en IDs y códigos de producto)
> ANTES de ejecutar cualquier consulta a la BD. Un ID malformado DEBE ser
> rechazado con `ToolError`, sin tocar la BD.

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
pytest tests/test_tools.py
```

Casos concretos que hacen cumplir el EARS:

- `tests/test_tools.py::test_bound_tools_never_expose_customer_id` — `bind_tools`
  devuelve funciones con 0 parámetros de identidad; el LLM no puede elegir
  cliente. La función atada ejecuta SQL con `{"cid": "C123"}` sin exponerlo.
- `tests/test_tools.py::test_balance_uses_parametrized_query` — SQL parametrizado
  con `:cid`; el customer_id NUNCA aparece en el texto SQL (`assert "C123" not in sql`).
- `tests/test_tools.py::test_balance_rejects_bad_ids` — 4 variantes de IDs
  malformados (vacío, inyección SQL, demasiado largo, comilla) → `ToolError` sin
  tocar la BD.
- `tests/test_tools.py::test_bind_tools_rejects_bad_identity` — un customer_id
  malformado en el propio `bind_tools` se rechaza antes de construir las tools.
- `tests/test_tools.py::test_balance_not_found` — ID válido pero inexistente →
  `ToolError("no encontrado")`, no un error genérico de BD.
- `tests/test_tools.py::test_product_normalizes_code` — normalización de códigos
  de producto (strip + upper) antes de la consulta.

**Evidencia (02-backend-api, worktree `chat/02-backend-api`, 2026-09-15,
comprobación literal sin `-q`):**

```
$ pytest tests/test_tools.py
.........                                                                [100%]
9 passed in 1.44s
```

## R2 — no necesario (evitar solapamiento)

T01 cubre el arranque fail-loud (`_require_llm_credentials`). T03 cubre el
contrato REST (`/consultar`, SSE, PII masking). T15 cubre los health probes K8s.
Los principios de diseño del agente runtime (`AgentEngine` como adapter,
`_safe_tool_call` como decorator, `build_agent` como factory) se ejercitan en
`tests/test_agent_runtime.py`, pero ese fichero depende de `llama_index` (no
disponible en el venv unitario). Las tools en sí (`app.agent.tools`) demuestran
encapsulación, validación y SQL parametrizado sin depender de LlamaIndex, lo que
las hace la comprobación más robusta y autónoma para T10.

---
Chat: 02-backend-api
Model: claude-opus-4-6
Plan: PLAN-CS-T10
Tarea: 42
