# T05 — Ensure application performance, scalability, and reliability

## Oferta (línea 5, literal de `oferta-coforge.txt`)

> Ensure application performance, scalability, and reliability

## Solución

`rag-banking-agent` garantiza rendimiento, escalabilidad y fiabilidad en dos
capas defensivas que operan ANTES y DURANTE el streaming:

- **Antes del LLM (guardrails)**: `app.security.guardrails.check_prompt` valida
  cada prompt del usuario en microsegundos: rechaza vacíos, demasiado largos
  (`MAX_PROMPT_CHARS`) y patrones de inyección (SQL, prompt injection) sin
  consumir tokens del modelo. Un prompt bloqueado devuelve HTTP 400 al instante
  — el LLM nunca se invoca, cero coste, cero latencia.
- **Durante el stream (PII masking)**: `app.security.pii.StreamMasker` enmascara
  IBAN, DNI, tarjeta y email en el stream SSE token a token, emitiendo
  progresivamente (`max_buffer`) sin esperar al final de la respuesta. Un LLM
  real parte un IBAN en varios tokens (`"ES91"`, `" 2100 0418"`, `" 4502…"`):
  el masker detecta la entidad aunque esté dividida entre chunks.

## R1 — PII streaming y validación de prompts

**EARS:**
> El servicio DEBE enmascarar datos PII (IBAN, DNI, tarjeta, email) en el stream
> de respuesta, incluso cuando la entidad esté dividida entre varios tokens del
> LLM. El `StreamMasker` DEBE emitir progresivamente sin esperar al final del
> stream. Los prompts del usuario DEBEN validarse ANTES de invocar al LLM:
> prompts vacíos, demasiado largos o con patrones de inyección DEBEN ser
> rechazados sin consumir recursos del modelo.

**Comprobación ejecutable** (verificada ahora mismo, evidencia abajo):

```bash
pytest tests/test_pii.py tests/test_guardrails.py
```

Casos concretos que hacen cumplir el EARS:

**PII masking (rendimiento + fiabilidad):**
- `tests/test_pii.py::test_masks_iban_dni_card_email` — enmascara 4 tipos de PII
  en una sola cadena; ningún dato real pasa.
- `tests/test_pii.py::test_leaves_normal_text` — texto sin PII pasa intacto (no
  false positives que degraden la experiencia).
- `tests/test_pii.py::test_stream_masker_catches_entity_split_across_tokens` —
  DNI y email divididos entre tokens se detectan y enmascaran. El peor caso de
  un LLM real.
- `tests/test_pii.py::test_stream_masker_emits_progressively_on_long_text` —
  con `max_buffer=60`, el masker emite parcialmente sin esperar al flush final.
  Rendimiento: el cliente ve tokens en tiempo real.

**Guardrails (rendimiento + escalabilidad):**
- `tests/test_guardrails.py::test_allows_legit_prompts` — 2 prompts legítimos
  pasan sin filtro.
- `tests/test_guardrails.py::test_blocks_injection` — 5 variantes de inyección
  (SQL, prompt injection, system prompt extraction) bloqueadas antes del LLM.
- `tests/test_guardrails.py::test_blocks_empty_and_too_long` — vacío y demasiado
  largo → rechazados instantáneamente. Protección contra abuso y DoS.
- `tests/test_guardrails.py::test_sanitizes_whitespace_and_control_chars` —
  null bytes y espacios redundantes se limpian antes de llegar al modelo.

**Evidencia (02-backend-api, worktree `chat/02-backend-api`, 2026-09-15,
comprobación literal sin `-q`):**

```
$ pytest tests/test_pii.py tests/test_guardrails.py
.............                                                            [100%]
13 passed in 0.94s
```

## R2 — no necesario (evitar solapamiento)

T03 cubre el contrato REST completo (`/consultar` SSE, identidad, HTTP status).
T01 cubre el arranque fail-loud. T15 cubre los health probes K8s. T10 cubre la
encapsulación OOP de tools. El timeout del LLM (`llm_timeout_seconds`) y el
cierre limpio de streams (`event: error`) se ejercitan en `test_api.py`, que
pertenece a T03. Con R1 cerrado, T05 queda cubierto con las dos capas
defensivas (pre-LLM y durante-stream) sin solapar.

---
Chat: 02-backend-api
Model: claude-opus-4-6
Plan: PLAN-CS-T05
Tarea: 37
