# T08 — Knowledge of relational databases such as PostgreSQL, MySQL, or SQL Server

## Oferta (línea 8, literal de `oferta-coforge.txt`)

> Knowledge of relational databases such as PostgreSQL, MySQL, or SQL Server.

## Solución

`rag-banking-agent` demuestra dominio de PostgreSQL en tres capas:

1. **Esquema DDL** (`scripts/init_db.sql`): tabla `data_documentos_bancarios`
   que replica exactamente el modelo híbrido de PGVectorStore 0.9.0
   (vector + full-text BM25), con cinco columnas tipadas (`id BIGSERIAL`,
   `text VARCHAR`, `metadata_ JSONB`, `node_id VARCHAR`,
   `embedding vector(1536)`) más una columna generada
   `text_search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', text)) STORED`.
   Tres índices con los nombres que crea la propia librería para que su
   `CREATE INDEX IF NOT EXISTS` no duplique nada:
   - HNSW (`data_documentos_bancarios_embedding_idx`) para similitud vectorial,
   - GIN (`documentos_bancarios_idx`) para full-text español,
   - BTREE (`documentos_bancarios_idx_1`) sobre `metadata_->>'ref_doc_id'`
     (borrado por documento, añadido en PGVectorStore 0.9.0).

2. **Roles de mínimo privilegio** (regla del banco: el LLM solo puede SELECT):
   - `app_user`: LOGIN con SELECT/INSERT/UPDATE/DELETE (API de ingestión).
   - `ai_readonly`: LOGIN con solo SELECT + `statement_timeout = 5s`
     (el motor RAG usa `LLAMAINDEX_DATABASE_URL` con este rol).
   - Contraseñas inyectadas por psql variable interpolation
     (`\set var \`echo "$ENV_VAR"\`` + `:'var'`), nunca literales en el SQL
     (regla "0 secretos en código").

3. **Configuración del ORM vectorial** (`app/rag/vector_store.py`):
   `PGVectorStore.from_params()` con `perform_setup=False` (el DBA crea el
   esquema, la app no ejecuta DDL), `hybrid_search=True`,
   `text_search_config="spanish"`, `use_jsonb=True`, y parámetros HNSW
   alineados con el índice del SQL (`m=16`, `ef_construction=64`).

4. **Despliegue** (`docker-compose.yml`): imagen `pgvector/pgvector:pg16`,
   credenciales vía `env_file: .env` (git-ignored), URLs de conexión con
   `${APP_PW}`/`${RO_PW}` interpolados por Docker Compose.

## R1 — Esquema híbrido pgvector con roles de mínimo privilegio

**EARS:**
> Cuando se inspeccionen los ficheros de definición de base de datos del
> servicio (`scripts/init_db.sql`, `app/rag/vector_store.py` y
> `docker-compose.yml`), el sistema DEBE presentar: (a) una tabla
> `data_documentos_bancarios` con las seis columnas que espera PGVectorStore
> 0.9.0 en modo híbrido, (b) tres índices nombrados según la convención de
> la librería (HNSW, GIN, BTREE), (c) un rol `ai_readonly` con solo SELECT
> y `statement_timeout`, (d) cero contraseñas literales en el SQL ni en el
> compose (inyección por variable de entorno), y (e) `perform_setup=False` y
> `hybrid_search=True` en la configuración de PGVectorStore.

**Comprobación ejecutable** (script determinista sobre ficheros reales, sin
necesidad de base de datos en ejecución):

```bash
bash scripts/validate_pgvector_schema.sh
```

El script valida cada condición del EARS inspeccionando los ficheros fuente
del repositorio con `grep` determinista:

- **Tabla y columnas** — busca las 6 columnas tipadas en `init_db.sql`.
- **Índices** — busca los 3 `CREATE INDEX IF NOT EXISTS` con los nombres
  exactos de la librería.
- **Rol ai_readonly** — verifica `CREATE ROLE ai_readonly`, `GRANT SELECT`,
  y `statement_timeout`.
- **Cero literales** — verifica que `PASSWORD` en `init_db.sql` solo aparece
  seguido de `:'variable'` (interpolación psql), nunca de una cadena literal.
- **Compose sin hardcoded** — verifica `env_file:` y `${APP_PW}`/`${RO_PW}`
  en `docker-compose.yml`.
- **PGVectorStore** — verifica `perform_setup=False`, `hybrid_search=True`,
  `text_search_config="spanish"` y `use_jsonb=True` en
  `app/rag/vector_store.py`.

Salida esperada: 10 líneas `[OK]`, exit code 0. Cualquier fallo produce
`[FALLO]` y exit code 1.

## Corrección sobre el encargo (Ley del Arquitecto §11)

El brief marca el estado de T08 como "inferido" y la evidencia como "PARCIAL
(psql manual no en CI)". Esto es correcto: la validación de esquema contra
una base de datos real (`EXPLAIN ANALYZE` con `ai_readonly`) está documentada
en `tests/integracion/README.md` pero aún no se ejecuta en CI (queda
pendiente el paso de GitHub Actions con servicio Postgres+pgvector, a cargo
de 01-git-cicd). La comprobación de R1 no requiere base de datos activa: es
una validación estática sobre los propios ficheros que define el esquema,
suficiente para demostrar "knowledge of relational databases" sin depender de
infraestructura externa.

---
Chat: 03-datos-rag
Model: claude-opus-4-6
Plan: PLAN-CS-T08
Tarea: 40
