"""Cinco remates de la auditoría de restauración — orden del lead (21-sep-2026).

Remate 1: Restaurar M5/R1 comprobacion + nota_lead tarea 63→82
Remate 2: 8 eventos complementarios con texto COMPLETO antes/después
Remate 3: 7 eventos requisito_cargado (3 R2 + 4 F2)

    python3 remates_auditoria.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
APROBACION = "aprobado por 00-lead, auditoría de restauración 21-sep"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ═══════════════════════════════════════════════════════════
# REMATE 1: M5/R1 restauración
# ═══════════════════════════════════════════════════════════

M5_R1_VIEJO_COMP = "docker compose -f microservicio/demo/docker-compose.demo.yml config --quiet"


def remate_1_m5r1(conn, ts):
    """Restaurar M5/R1 comprobacion al original del campo VIEJO del evento 24248."""
    print("\n[REMATE 1] Restaurar M5/R1 comprobacion")

    row = conn.execute(
        "SELECT ears, comprobacion FROM requisito WHERE plan_id='PLAN-CS-M5' AND ref='R1'"
    ).fetchone()
    if not row:
        print("  [SKIP] PLAN-CS-M5/R1 no existe")
        return
    old_ears, old_comp = row

    if old_comp == M5_R1_VIEJO_COMP:
        print("  [SKIP] M5/R1 ya tiene la comprobacion restaurada")
    else:
        conn.execute(
            "UPDATE requisito SET comprobacion=? WHERE plan_id='PLAN-CS-M5' AND ref='R1'",
            (M5_R1_VIEJO_COMP,),
        )
        detalle_rest = (
            f"PLAN-CS-M5/R1 restaurado (comprobacion). "
            f"Vigente antes: comp='{old_comp}'. "
            f"Restaurado a: comp='{M5_R1_VIEJO_COMP}'. "
            f"Origen: evento 24248 campo VIEJO. "
            f"La comprobacion vigente (python microservicio/demo/comprobar_compose.py) "
            f"se traslada a PLAN-CS-F2/R3 (no se crea R2 en M5). {APROBACION}."
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "requisito_restaurado", "PLAN-CS-M5", detalle_rest),
        )
        print(f"  [OK] M5/R1 comprobacion restaurada a: {M5_R1_VIEJO_COMP}")

    nota = (
        "Tarea 63 (PLAN-CS-M5/R1) devuelta (evento 25004): "
        "queda sustituida por la tarea 82 de PLAN-CS-F2/R3 "
        "(compose demo publicado en main). "
        "La comprobacion original (docker compose config --quiet) "
        "se restaura en M5/R1; la nueva (python comprobar_compose.py) "
        "vive en F2/R3. " + APROBACION + "."
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "nota_lead", "PLAN-CS-M5", nota),
    )
    print("  [OK] nota_lead: tarea 63 sustituida por tarea 82 de F2/R3")


# ═══════════════════════════════════════════════════════════
# REMATE 2: 8 eventos complementarios con texto COMPLETO
# ═══════════════════════════════════════════════════════════

COMPLEMENTARIOS = [
    {
        "evento_truncado": 24994,
        "plan_id": "PLAN-CS-T06",
        "antes_ears": (
            "Ninguna tarea DEBE pasar a espera_firma sin verificada_por "
            "distinto del agente ejecutor (D7). Los actores 07-verificador "
            "DEBEN haber emitido al menos 5 eventos con veredicto CUMPLE "
            "registrados en la tabla evento del registro SYPNOSE."
        ),
        "antes_comp": (
            "sqlite3 ~/sypnose-f1/registry.db \"SELECT COUNT(*) FROM evento "
            "WHERE detalle LIKE '%CUMPLE%' AND actor LIKE 'IA:07%'\" → ≥5"
        ),
        "despues_ears": (
            "Ninguna tarea DEBE pasar a espera_firma sin verificada_por "
            "distinto del agente ejecutor."
        ),
        "despues_comp": (
            "SELECT COUNT(*) FROM tarea WHERE progreso='espera_firma' "
            "AND (verificada_por IS NULL OR verificada_por=agente) → 0"
        ),
    },
    {
        "evento_truncado": 24995,
        "plan_id": "PLAN-CS-T07",
        "antes_ears": (
            "Cuando un push a `main` dispare el pipeline CI/CD, el sistema DEBE "
            "ejecutar escaneo de secretos, lint, SAST, tests con cobertura ≥85 %, "
            "build Docker, escaneo de vulnerabilidades Trivy y push a ghcr.io en "
            "secuencia; el job de deploy DEBE quedar detenido esperando aprobación "
            "humana en el environment `production` antes de proceder."
        ),
        "antes_comp": (
            "gh run view 34983669221 --repo radelqui/rag-banking-agent "
            "--json status --jq '.status'"
        ),
        "despues_ears": (
            "Cuando main pase lint, SAST, secret scanning, tests ≥85% y escaneo de "
            "imagen, el job deploy DEBE quedar esperando aprobación manual."
        ),
        "despues_comp": (
            "gh run list --branch main --limit 1 --json status,conclusion,url "
            "+ gh run view <id> (job deploy en waiting)"
        ),
    },
    {
        "evento_truncado": 24996,
        "plan_id": "PLAN-CS-T03",
        "antes_ears": (
            "El endpoint `/api/v1/consultar` DEBE responder con Server-Sent Events "
            "(SSE) en streaming. DEBE requerir la cabecera `X-Customer-Id` (inyectada "
            "por la pasarela del banco) y rechazar con HTTP 401 peticiones sin ella o "
            "con un ID malformado (vacío, inyección SQL, demasiado largo). Los errores "
            "del motor DEBEN emitirse como `event: error` SSE, nunca como excepciones "
            "HTTP no controladas. Los campos del body DEBEN validarse por el schema "
            "Pydantic (`pregunta` no vacía → HTTP 422)."
        ),
        "antes_comp": (
            'pytest tests/test_api.py tests/test_identity.py -k "consultar or identity"'
        ),
        "despues_ears": (
            "Cuando /consultar reciba una pregunta válida con identidad, "
            "DEBE responder text/event-stream con eventos token y done; "
            "sin identidad DEBE devolver 401."
        ),
        "despues_comp": "pytest tests/test_api.py tests/test_identity.py",
    },
    {
        "evento_truncado": 24997,
        "plan_id": "PLAN-CS-T05",
        "antes_ears": (
            "El servicio DEBE enmascarar datos PII (IBAN, DNI, tarjeta, email) en el "
            "stream de respuesta, incluso cuando la entidad esté dividida entre varios "
            "tokens del LLM. El `StreamMasker` DEBE emitir progresivamente sin esperar "
            "al final del stream. Los prompts del usuario DEBEN validarse ANTES de "
            "invocar al LLM: prompts vacíos, demasiado largos o con patrones de "
            "inyección DEBEN ser rechazados sin consumir recursos del modelo."
        ),
        "antes_comp": "pytest tests/test_pii.py tests/test_guardrails.py",
        "despues_ears": (
            "El Deployment DEBE declarar startup/readiness/liveness, "
            "requests/limits de memoria y preStop para no cortar SSE."
        ),
        "despues_comp": (
            "python -c \"import yaml;d=[x for x in yaml.safe_load_all("
            "open('k8s/deployment.yaml')) if x and x['kind']=='Deployment'][0];"
            "c=d['spec']['template']['spec']['containers'][0];"
            "assert all(k in c for k in ('startupProbe','readinessProbe',"
            "'livenessProbe','resources','lifecycle'));print('ok')\""
        ),
    },
    {
        "evento_truncado": 24998,
        "plan_id": "PLAN-CS-T10",
        "antes_ears": (
            "Cuando el agente construya tools bancarias para un cliente, las funciones "
            "resultantes DEBEN ocultar el `customer_id` al LLM (`bind_tools` reduce "
            "la firma a 0 parámetros de identidad) y DEBEN validar todas las entradas "
            "contra inyección (SQL parametrizado con `:cid`, regex en IDs y códigos de "
            "producto) ANTES de ejecutar cualquier consulta a la BD. Un ID malformado "
            "DEBE ser rechazado con `ToolError`, sin tocar la BD."
        ),
        "antes_comp": "pytest tests/test_tools.py",
        "despues_ears": (
            "El motor DEBE cumplir el Protocol QueryEngineLike y ser sustituible "
            "(Fake/RAG/Agente) sin tocar routes.py."
        ),
        "despues_comp": (
            "git diff $(git rev-list --max-parents=0 HEAD)..HEAD "
            "-- app/api/routes.py vacío + pytest -q"
        ),
    },
    {
        "evento_truncado": 24999,
        "plan_id": "PLAN-CS-T08",
        "antes_ears": (
            "Cuando se inspeccionen los ficheros de definición de base de datos del "
            "servicio (`scripts/init_db.sql`, `app/rag/vector_store.py` y "
            "`docker-compose.yml`), el sistema DEBE presentar: (a) una tabla "
            "`data_documentos_bancarios` con las seis columnas que espera PGVectorStore "
            "0.9.0 en modo híbrido, (b) tres índices nombrados según la convención de la "
            "librería (HNSW, GIN, BTREE), (c) un rol `ai_readonly` con solo SELECT y "
            "`statement_timeout`, (d) cero contraseñas literales en el SQL ni en el "
            "compose (inyección por variable de entorno), y (e) `perform_setup=False` y "
            "`hybrid_search=True` en la configuración de PGVectorStore."
        ),
        "antes_comp": "bash scripts/validate_pgvector_schema.sh",
        "despues_ears": (
            "Cuando el rol ai_readonly ejecute una consulta híbrida sobre volumen "
            "sembrado, el plan de ejecución DEBE usar el índice HNSW de la columna "
            "de embeddings y el índice GIN de texto, y el rol NO DEBE poder escribir."
        ),
        "despues_comp": (
            "tests/integracion/README.md (precondición: sembrar volumen antes del "
            "EXPLAIN; comando psql) ejecutado en CI con service Postgres"
        ),
    },
    {
        "evento_truncado": 25000,
        "plan_id": "PLAN-CS-M2",
        "antes_ears": (
            "Cuando se ejecute `python microservicio/comprobar_esqueleto.py` desde el "
            "worktree de plantilla, el sistema DEBERÁ instanciar demo-x en `.tmp/demo-x`, "
            "ejecutar `make test` (todos en verde) y verificar que el diff fuera de "
            "`app/demo_x/` y `tests/demo_x/` contra el tag `esqueleto-v1` es vacío, "
            "sin editar ningún fichero a mano."
        ),
        "antes_comp": "python microservicio/comprobar_esqueleto.py",
        "despues_ears": (
            "Cuando se ejecute `python microservicio/instanciar_microservicio.py "
            "demo-x --puerto 8010 --destino /tmp/demo-x` desde el worktree de "
            "plantilla, el sistema DEBERÁ dejar un repo en el que `make test` está "
            "en verde y `docker build .` termina bien, sin editar ningún fichero a mano."
        ),
        "despues_comp": (
            "cd /tmp && rm -rf demo-x && python microservicio/"
            "instanciar_microservicio.py demo-x --puerto 8010 "
            "--destino /tmp/demo-x && make -C /tmp/demo-x test"
        ),
    },
    {
        "evento_truncado": 25001,
        "plan_id": "PLAN-CS-M2",
        "antes_ears": (
            "Cuando se compare el microservicio generado con el esqueleto "
            "(`git diff --stat esqueleto-v1..HEAD -- . ':!app/<dominio>' "
            "':!tests/<dominio>'`), el resultado DEBERÁ ser vacío (0 ficheros "
            "fuera de la lógica de negocio). El tag `esqueleto-v1` se crea al "
            "instanciar. La comprobación está integrada en `comprobar_esqueleto.py` "
            "(paso 3/3)."
        ),
        "antes_comp": "python microservicio/comprobar_esqueleto.py",
        "despues_ears": (
            "Cuando se compare el microservicio generado con el esqueleto "
            "(`git diff --stat esqueleto-v1..HEAD -- . ':!app/<dominio>' "
            "':!tests/<dominio>'`), el resultado DEBERÁ ser vacío (0 ficheros "
            "fuera de la lógica de negocio). El tag `esqueleto-v1` se crea al "
            "cerrar las tareas de extracción (53/54/55)."
        ),
        "despues_comp": (
            "cd /tmp/demo-x && git diff --stat esqueleto-v1..HEAD "
            "-- . ':!app/demo_x/' ':!tests/demo_x/' | wc -l"
        ),
    },
]


def remate_2_complementarios(conn, ts):
    """Añadir eventos complementarios con texto COMPLETO para 24994-25001."""
    print("\n[REMATE 2] 8 eventos complementarios con texto COMPLETO")

    for c in COMPLEMENTARIOS:
        ev_id = c["evento_truncado"]
        plan_id = c["plan_id"]

        existing = conn.execute(
            "SELECT 1 FROM evento WHERE plan_id=? AND accion='requisito_restaurado_completo' "
            "AND detalle LIKE ?",
            (plan_id, f"%complemento del evento {ev_id}%"),
        ).fetchone()
        if existing:
            print(f"  [SKIP] complemento de {ev_id} ({plan_id}) ya existe")
            continue

        detalle = (
            f"Complemento del evento {ev_id} ({plan_id}) con texto COMPLETO "
            f"(el evento original trunca a ~80 chars). "
            f"ANTES ears: {c['antes_ears']} "
            f"ANTES comprobacion: {c['antes_comp']} "
            f"DESPUÉS ears: {c['despues_ears']} "
            f"DESPUÉS comprobacion: {c['despues_comp']} "
            f"Fuente: backup pre-restauracion registry-backup-20260921-115610 "
            f"y eventos originales de requisito_actualizado. {APROBACION}."
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "requisito_restaurado_completo", plan_id, detalle),
        )
        print(f"  [OK] complemento de {ev_id} ({plan_id})")


# ═══════════════════════════════════════════════════════════
# REMATE 3: requisito_cargado para 3 R2 + 4 F2
# ═══════════════════════════════════════════════════════════

RESTAURAR_SHA = "6aa69c54669615fc96963d474e25e0bcb7e777ae"
CREAR_F2_SHA = "dfc74f528f45f18169396588c8220ba7541a0afe"

R2_CARGADOS = [
    {
        "plan_id": "PLAN-CS-T05",
        "ref": "R2",
        "ears": (
            "El servicio DEBE enmascarar datos PII (IBAN, DNI, tarjeta, email) en el "
            "stream de respuesta, incluso cuando la entidad esté dividida entre varios "
            "tokens del LLM. El `StreamMasker` DEBE emitir progresivamente sin esperar "
            "al final del stream. Los prompts del usuario DEBEN validarse ANTES de "
            "invocar al LLM: prompts vacíos, demasiado largos o con patrones de "
            "inyección DEBEN ser rechazados sin consumir recursos del modelo."
        ),
        "comprobacion": "pytest tests/test_pii.py tests/test_guardrails.py",
        "fichero": "plantilla/restaurar_requisitos.py",
        "sha": RESTAURAR_SHA,
    },
    {
        "plan_id": "PLAN-CS-T08",
        "ref": "R2",
        "ears": (
            "Cuando se inspeccionen los ficheros de definición de base de datos del "
            "servicio (`scripts/init_db.sql`, `app/rag/vector_store.py` y "
            "`docker-compose.yml`), el sistema DEBE presentar: (a) una tabla "
            "`data_documentos_bancarios` con las seis columnas que espera PGVectorStore "
            "0.9.0 en modo híbrido, (b) tres índices nombrados según la convención de la "
            "librería (HNSW, GIN, BTREE), (c) un rol `ai_readonly` con solo SELECT y "
            "`statement_timeout`, (d) cero contraseñas literales en el SQL ni en el "
            "compose (inyección por variable de entorno), y (e) `perform_setup=False` y "
            "`hybrid_search=True` en la configuración de PGVectorStore."
        ),
        "comprobacion": "bash scripts/validate_pgvector_schema.sh",
        "fichero": "plantilla/restaurar_requisitos.py",
        "sha": RESTAURAR_SHA,
    },
    {
        "plan_id": "PLAN-CS-T10",
        "ref": "R2",
        "ears": (
            "Cuando el agente construya tools bancarias para un cliente, las funciones "
            "resultantes DEBEN ocultar el `customer_id` al LLM (`bind_tools` reduce "
            "la firma a 0 parámetros de identidad) y DEBEN validar todas las entradas "
            "contra inyección (SQL parametrizado con `:cid`, regex en IDs y códigos de "
            "producto) ANTES de ejecutar cualquier consulta a la BD. Un ID malformado "
            "DEBE ser rechazado con `ToolError`, sin tocar la BD."
        ),
        "comprobacion": "pytest tests/test_tools.py",
        "fichero": "plantilla/restaurar_requisitos.py",
        "sha": RESTAURAR_SHA,
    },
]

F2_CARGADOS = [
    {
        "plan_id": "PLAN-CS-F2",
        "ref": "R1",
        "ears": (
            "Cuando se consulte la última ejecución del workflow de CI en la rama main de "
            "radelqui/rag-banking-agent, el job de tests DEBE haber terminado en success con "
            "las cinco puertas ejecutadas (ruff, bandit, pytest con cobertura mínima del 85 %, "
            "gitleaks y trivy) y el job de despliegue DEBE quedar esperando la aprobación humana; "
            "la rama main DEBE tener protección de rama con el check de tests como requerido; "
            "y el main local de los worktrees DEBE coincidir con origin/main."
        ),
        "comprobacion": "python ci/comprobar_ci_main.py",
        "fichero": "plantilla/crear_plan_f2.py",
        "sha": CREAR_F2_SHA,
    },
    {
        "plan_id": "PLAN-CS-F2",
        "ref": "R2",
        "ears": (
            "El fichero specs/T09/spec.md del repositorio de la plantilla DEBE contener, escrito "
            "por 01-git-cicd (trailer Chat: 01-git-cicd), el requisito R1 de la línea T09 con "
            "esta regla: desde el commit de corte en que se instaló el hook commit-msg en cada "
            "repositorio (identificado por su sha y su fecha), el 100 % de los commits lleva los "
            "trailers Chat, Model y Plan, medido como igualdad y no como umbral; los commits "
            "anteriores al corte se listan como deuda histórica con su recuento y no se reescribe "
            "la historia. La comprobación del requisito es un script que recorre los commits "
            "posteriores al corte en rag-banking-agent, sypnose-plantilla y como-estoy-hecho, "
            "termina con código distinto de 0 si a alguno le falta un trailer, e imprime el "
            "recuento de deuda anterior al corte."
        ),
        "comprobacion": "python plantilla/comprobar_trailers.py",
        "fichero": "plantilla/crear_plan_f2.py",
        "sha": CREAR_F2_SHA,
    },
    {
        "plan_id": "PLAN-CS-F2",
        "ref": "R3",
        "ears": (
            "El fichero microservicio/demo/docker-compose.demo.yml y su README de tres órdenes "
            "DEBEN existir en la rama main de radelqui/sypnose-plantilla, con los servicios "
            "rag-banking-agent, como-estoy-hecho y la base efímera, healthcheck en cada servicio "
            "de aplicación y ninguna variable con valor de secreto."
        ),
        "comprobacion": "python microservicio/demo/comprobar_compose.py",
        "fichero": "plantilla/crear_plan_f2.py",
        "sha": CREAR_F2_SHA,
    },
    {
        "plan_id": "PLAN-CS-F2",
        "ref": "R4",
        "ears": (
            "El fichero specs/T06/spec.md DEBE estar escrito por el rol 07-verificador (trailer "
            "Chat: 07-verificador en el commit que lo crea o lo reescribe), con el requisito R1 "
            "de T06 restaurado a su invariante original (ninguna tarea pasa a espera_firma sin "
            "verificada_por distinto del agente ejecutor; recuento igual a 0) y sin el contador "
            "de eventos con la palabra CUMPLE."
        ),
        "comprobacion": "git log -1 --format=%(trailers:key=Chat,valueonly) -- specs/T06/spec.md",
        "fichero": "plantilla/crear_plan_f2.py",
        "sha": CREAR_F2_SHA,
    },
]


def remate_3_requisito_cargado(conn, ts):
    """Añadir evento requisito_cargado para 3 R2 + 4 F2 requisitos."""
    print("\n[REMATE 3] 7 eventos requisito_cargado")

    for r in R2_CARGADOS + F2_CARGADOS:
        plan_id = r["plan_id"]
        ref = r["ref"]

        existing = conn.execute(
            "SELECT 1 FROM evento WHERE plan_id=? AND accion='requisito_cargado' "
            "AND detalle LIKE ?",
            (plan_id, f"%{ref}%texto completo%"),
        ).fetchone()
        if existing:
            print(f"  [SKIP] requisito_cargado {plan_id}/{ref} ya existe")
            continue

        req = conn.execute(
            "SELECT ears, comprobacion FROM requisito WHERE plan_id=? AND ref=?",
            (plan_id, ref),
        ).fetchone()
        if not req:
            print(f"  [WARN] {plan_id}/{ref} no existe en requisito — skip")
            continue

        db_ears, db_comp = req
        if db_ears != r["ears"]:
            print(f"  [WARN] {plan_id}/{ref} ears en BD difiere del esperado")
            print(f"    BD:       {db_ears[:80]}...")
            print(f"    Esperado: {r['ears'][:80]}...")
        if db_comp != r["comprobacion"]:
            print(f"  [WARN] {plan_id}/{ref} comp en BD difiere del esperado")
            print(f"    BD:       {db_comp[:80]}...")
            print(f"    Esperado: {r['comprobacion'][:80]}...")

        detalle = (
            f"{plan_id}/{ref} requisito_cargado — texto completo. "
            f"EARS: {r['ears']} "
            f"Comprobación: {r['comprobacion']} "
            f"Fichero dictado: {r['fichero']}@{r['sha'][:12]}. {APROBACION}."
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "requisito_cargado", plan_id, detalle),
        )
        print(f"  [OK] {plan_id}/{ref}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Remates auditoría restauración (1-3)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-remates-auditoria")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        remate_1_m5r1(conn, ts)
        remate_2_complementarios(conn, ts)
        remate_3_requisito_cargado(conn, ts)

        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[dry-run] transaccion deshecha")
        else:
            conn.execute("COMMIT")
            print("\n[OK] Remates 1-3 completados")

            last_ev = conn.execute("SELECT MAX(id) FROM evento").fetchone()[0]
            print(f"  último evento: {last_ev}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
