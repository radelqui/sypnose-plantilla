# M5 — Demo viva

## Objetivo

Los dos microservicios (rag-banking-agent y como-estoy-hecho) corriendo en el
servidor 67 con docker-compose, accesibles por HTTPS en rutas públicas, con
health checks y smoke tests que demuestran que funcionan.

## R0 — Spec EARS: demo viva con docker-compose, smoke test y proxy

**EARS (R1 — Compose):**
> Cuando se ejecute `docker compose -f docker-compose.demo.yml up -d` en el
> servidor 67, DEBEN arrancar tres servicios (postgres, rag-banking-agent en
> puerto 8000, como-estoy-hecho en puerto 8010) con `USE_FAKE_ENGINE=1` y un
> PostgreSQL+pgvector efímero; `docker compose ps` DEBE mostrar los tres en
> estado `running` en menos de 60 segundos.

**EARS (R2 — Smoke test):**
> Cuando se ejecute `python microservicio/demo/smoke_test.py` con las variables
> `BASE_RAG` y `BASE_CEH` apuntando a las URLs vivas, el script DEBE verificar
> GET /health/live (200), GET /health/ready (200 o skip si no aplica), y
> POST /api/v1/consultar con pregunta de prueba (200 + SSE stream) para
> rag-banking-agent, y GET /health/live (200), GET /como-estoy-hecho/ui/ (200 +
> contiene 'viewport') para como-estoy-hecho; exit 0 si todo pasa.

**EARS (R3 — Proxy):**
> Cuando las URLs `https://coforge.sypnose.cloud/demo/rag/health/live` y
> `https://coforge.sypnose.cloud/demo/ceh/health/live` se consulten desde
> fuera del servidor, DEBEN devolver 200 con el JSON de health del servicio
> correspondiente.

**Comprobación ejecutable (literal, única):**

```bash
python microservicio/demo/smoke_test.py
```

Variables de entorno:
- `BASE_RAG=http://localhost:8000` (compose local) o `https://coforge.sypnose.cloud/demo/rag` (proxy)
- `BASE_CEH=http://localhost:8010` (compose local) o `https://coforge.sypnose.cloud/demo/ceh` (proxy)
