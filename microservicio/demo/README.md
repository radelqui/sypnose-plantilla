# Demo — rag-banking-agent + como-estoy-hecho

Demo local con los dos microservicios y un PostgreSQL+pgvector efímero.
`USE_FAKE_ENGINE=1` permite arrancar sin claves reales de LLM.

## Arranque en tres órdenes

```bash
# 1. Copiar variables (los defaults del compose bastan para demo)
cp .env.example .env

# 2. Construir y arrancar los tres servicios
docker compose -f docker-compose.demo.yml up -d --build

# 3. Verificar que todo está corriendo
docker compose -f docker-compose.demo.yml ps
```

## Servicios

| Servicio | Puerto | Health |
|----------|--------|--------|
| rag-banking-agent | 8000 | `GET /api/v1/health/live` |
| como-estoy-hecho | 8010 | `GET /health` |
| postgres (pgvector) | 5432 | `pg_isready` |

## Parar la demo

```bash
docker compose -f docker-compose.demo.yml down -v
```

El flag `-v` elimina el volumen de PostgreSQL (datos efímeros de demo).

## Variables

Las 13 variables del CONTRATO-BANCO están en `.env.example`.
0 secretos en código: los valores reales los inyecta el banco.
