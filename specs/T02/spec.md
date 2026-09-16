# T02 — Program AI agents

## Oferta (línea 2, literal de `oferta-coforge.txt`)

> Program AI agents

## Solución

`rag-banking-agent` expone un agente LlamaIndex real (`AgentEngine` /
`build_agent`, `app/agent/runtime.py`, PLAN-0001) que envuelve las tools
bancarias de `app/agent/tools.py` (`bind_tools`) tras el contrato
`QueryEngineLike.astream(question, customer_id)`.

La regla de oro del banco ("El LLM nunca elige el cliente") se implementa en
`bind_tools`: el `customer_id` llega de la cabecera de la pasarela (`X-Customer-Id`,
ver `app/security/identity.py`) y se cierra sobre las funciones ANTES de
entregárselas al agente — la firma que ve el LLM (`balance()`) ni siquiera admite
un `customer_id` como parámetro. `AgentEngine.astream` construye un agente nuevo
por request, con tools recién atadas a ESE cliente, así que dos clientes en la
misma instancia nunca comparten identidad (cubierto además por PLAN-0001 H2/H3:
un intento de colar un `customer_id` ajeno en `tool_kwargs` no ejecuta SQL ni
filtra nombres internos, ver `_safe_tool_call` en `app/agent/runtime.py`).

## R1 — El LLM nunca elige el cliente en `get_account_balance`

**EARS (literal del registro SYPNOSE, tarea 10):**
> Cuando el cliente autenticado pregunte su saldo, el agente DEBE invocar
> `get_account_balance` con el `customer_id` de la cabecera y NUNCA con uno
> aportado por el prompt.

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
"C:\MICD\Coforge Santander\rag-banking-agent\.venv\Scripts\python.exe" -m pytest tests/test_agent_runtime.py -q
```

Casos concretos que hacen cumplir el EARS (no solo "verde genérico"):

- `test_agent_engine_ejecuta_tool_atada_al_cliente_y_transmite_respuesta` — el
  SQL parametrizado de `get_account_balance` se ejecuta con `{"cid": "C123"}`,
  el `customer_id` real de la cabecera, no uno inventado por el LLM.
- `test_agent_engine_aisla_clientes_distintos` — dos preguntas de saldo
  seguidas con `C1` y `C2` sobre la MISMA instancia de `AgentEngine` ejecutan
  SQL con `{"cid":"C1"}` y `{"cid":"C2"}` respectivamente: cada request arma
  sus tools desde cero.
- `test_tool_kwargs_con_customer_id_ajeno_no_filtra_nombres_ni_ejecuta_sql` —
  si el `tool_call` del LLM trae `customer_id="C999"` en `tool_kwargs` (que
  `balance()` no admite), la tool falla de forma segura y **0** consultas SQL
  se ejecutan, ni con `C123` ni con `C999`.
- `test_agent_engine_no_filtra_nombres_internos_ni_con_llm_hostil_de_extremo_a_extremo`
  — de punta a punta (`AgentEngine.astream`, lo que de verdad llega al
  cliente), aunque el LLM intente colar `C999` y repita el error de la tool,
  la respuesta transmitida es el mensaje genérico, nunca el `customer_id`
  ajeno ni un nombre interno.

**Evidencia (04-agentes, worktree `chat/04-agentes`, 2026-09-16, comprobación
literal):**

```
$ "C:\MICD\Coforge Santander\rag-banking-agent\.venv\Scripts\python.exe" -m pytest tests/test_agent_runtime.py -q
........                                                                 [100%]
```

## Corrección sobre el encargo (Ley del Arquitecto §11)

El requisito registrado traía como comprobación literal `pytest
tests/test_agent_runtime.py -q` (sin ruta de intérprete). Verificado ahora
mismo desde el worktree:

```
$ pytest tests/test_agent_runtime.py -q
ModuleNotFoundError: No module named 'llama_index'
```

El `pytest` del PATH global (`C:\Python313\Scripts\pytest`, 8.4.2) no es el
entorno del proyecto: no tiene `llama-index-core` ni el resto de dependencias
pinneadas en `requirements.txt` (a diferencia de `tests/test_pii.py` /
`test_guardrails.py` de T12, que son Python puro y sí corren con el intérprete
global). `tests/test_agent_runtime.py` importa `llama_index.core...` en la
cabecera: sin el venv del proyecto, ni siquiera se puede recolectar el módulo
— un `ModuleNotFoundError` en la recolección, no un test fallado, pero igual
de inválido como comprobación "tal cual".

Corrijo la comprobación a la forma literal que sí funciona sola desde el
worktree, con la ruta absoluta al intérprete del venv del proyecto (el mismo
que usa el resto de la suite; no hay `.venv` propio dentro del worktree, que
es solo un `git worktree` de `rag-banking-agent`, sin entorno virtual copiado):

```bash
"C:\MICD\Coforge Santander\rag-banking-agent\.venv\Scripts\python.exe" -m pytest tests/test_agent_runtime.py -q
```

No es un `-k` que reduzca lo que se comprueba (ver el falso positivo que
corrigió 02-backend-api en `specs/T01/spec.md`) — es el mismo alcance completo
del fichero, con el intérprete correcto. Aviso a 05-arquitecto-sypnose para
`cargar_requisito` con esta forma.

---
Chat: 04-agentes
Model: claude-sonnet-5
Plan: PLAN-CS-T02
Tarea: 10
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
