"""Restauración de requisitos ablandados — orden del lead.

Fuente: Requerimientos/F1/restauracion-requisitos.md v1, 21-sep-2026.
El arquitecto actúa como OPERADOR: texto literal, no redacta nada nuevo.

    python3 restaurar_requisitos.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
APROBACION = "aprobado por 00-lead, Requerimientos/F1/restauracion-requisitos.md"

RESTAURACIONES = [
    {
        "plan_id": "PLAN-CS-T06",
        "ref": "R1",
        "evento_origen": 23018,
        "evento_rejuicio": 24978,
        "ears": (
            "Ninguna tarea DEBE pasar a espera_firma sin verificada_por "
            "distinto del agente ejecutor."
        ),
        "comprobacion": (
            "SELECT COUNT(*) FROM tarea WHERE progreso='espera_firma' "
            "AND (verificada_por IS NULL OR verificada_por=agente) → 0"
        ),
        "crear_r2": False,
        "nota": "Se elimina comprobacion vigente (LIKE CUMPLE cuenta NO CUMPLE)",
    },
    {
        "plan_id": "PLAN-CS-T07",
        "ref": "R1",
        "evento_origen": 23169,
        "evento_rejuicio": 24979,
        "ears": (
            "Cuando main pase lint, SAST, secret scanning, tests ≥85% y escaneo de "
            "imagen, el job deploy DEBE quedar esperando aprobación manual."
        ),
        "comprobacion": (
            "gh run list --branch main --limit 1 --json status,conclusion,url "
            "+ gh run view <id> (job deploy en waiting)"
        ),
        "crear_r2": False,
        "nota": "Se elimina comprobacion vigente (run historico fijo)",
    },
    {
        "plan_id": "PLAN-CS-T03",
        "ref": "R1",
        "evento_origen": 22941,
        "evento_rejuicio": 24984,
        "ears": (
            "Cuando /consultar reciba una pregunta válida con identidad, "
            "DEBE responder text/event-stream con eventos token y done; "
            "sin identidad DEBE devolver 401."
        ),
        "comprobacion": "pytest tests/test_api.py tests/test_identity.py",
        "crear_r2": False,
        "nota": "Comprobacion superconjunto (15 tests, en verde hoy); absorbe vigente",
    },
    {
        "plan_id": "PLAN-CS-T05",
        "ref": "R1",
        "evento_origen": 22925,
        "evento_rejuicio": 24983,
        "ears": (
            "El Deployment DEBE declarar startup/readiness/liveness, "
            "requests/limits de memoria y preStop para no cortar SSE."
        ),
        "comprobacion": (
            "python -c \"import yaml;d=[x for x in yaml.safe_load_all("
            "open('k8s/deployment.yaml')) if x and x['kind']=='Deployment'][0];"
            "c=d['spec']['template']['spec']['containers'][0];"
            "assert all(k in c for k in ('startupProbe','readinessProbe',"
            "'livenessProbe','resources','lifecycle'));print('ok')\""
        ),
        "crear_r2": True,
        "nota": "Vigente pasa a R2 (PII)",
    },
    {
        "plan_id": "PLAN-CS-T10",
        "ref": "R1",
        "evento_origen": 22909,
        "evento_rejuicio": 24987,
        "ears": (
            "El motor DEBE cumplir el Protocol QueryEngineLike y ser sustituible "
            "(Fake/RAG/Agente) sin tocar routes.py."
        ),
        "comprobacion": (
            "git diff $(git rev-list --max-parents=0 HEAD)..HEAD "
            "-- app/api/routes.py vacío + pytest -q"
        ),
        "crear_r2": True,
        "nota": "Vigente pasa a R2",
    },
    {
        "plan_id": "PLAN-CS-T08",
        "ref": "R1",
        "evento_origen": 22864,
        "evento_rejuicio": 24981,
        "ears": (
            "Cuando el rol ai_readonly ejecute una consulta híbrida sobre volumen "
            "sembrado, el plan de ejecución DEBE usar el índice HNSW de la columna "
            "de embeddings y el índice GIN de texto, y el rol NO DEBE poder escribir."
        ),
        "comprobacion": (
            "tests/integracion/README.md (precondición: sembrar volumen antes del "
            "EXPLAIN; comando psql) ejecutado en CI con service Postgres"
        ),
        "crear_r2": True,
        "nota": (
            "Vigente pasa a R2 (validacion estatica); enmienda verificador "
            "(ev 24981): precondicion de sembrar volumen"
        ),
    },
]

M2_RESTAURACIONES = [
    {
        "plan_id": "PLAN-CS-M2",
        "ref": "R0",
        "evento_rejuicio": 24990,
        "ears": (
            "Cuando se ejecute `python microservicio/instanciar_microservicio.py "
            "demo-x --puerto 8010 --destino /tmp/demo-x` desde el worktree de "
            "plantilla, el sistema DEBERÁ dejar un repo en el que `make test` está "
            "en verde y `docker build .` termina bien, sin editar ningún fichero a mano."
        ),
        "comprobacion": (
            "cd /tmp && rm -rf demo-x && python microservicio/"
            "instanciar_microservicio.py demo-x --puerto 8010 "
            "--destino /tmp/demo-x && make -C /tmp/demo-x test"
        ),
        "nota": "Restaurado desde spec @7a4f4b4; vuelve clausula docker build",
    },
    {
        "plan_id": "PLAN-CS-M2",
        "ref": "R1",
        "evento_rejuicio": 24990,
        "ears": (
            "Cuando se compare el microservicio generado con el esqueleto "
            "(`git diff --stat esqueleto-v1..HEAD -- . ':!app/<dominio>' "
            "':!tests/<dominio>'`), el resultado DEBERÁ ser vacío (0 ficheros "
            "fuera de la lógica de negocio). El tag `esqueleto-v1` se crea al "
            "cerrar las tareas de extracción (53/54/55)."
        ),
        "comprobacion": (
            "cd /tmp/demo-x && git diff --stat esqueleto-v1..HEAD "
            "-- . ':!app/demo_x/' ':!tests/demo_x/' | wc -l"
        ),
        "nota": "Restaurado desde spec @7a4f4b4; R1 comprobacion separada de R0",
    },
]

DEVOLUCIONES = [
    {"tarea_id": 17, "plan_id": "PLAN-CS-T09", "motivo": (
        "T09/R1 original (igualdad trailers=commits) falla hoy (304 vs 320). "
        "Requisito nuevo por 01-git-cicd en PLAN-CS-F2/R2. Re-juicio: 24966 NO CUMPLE."
    )},
    {"tarea_id": 38, "plan_id": "PLAN-CS-T06", "motivo": (
        "T06/R0 spec debe escribirla el rol 07 (no el ejecutor de la tarea). "
        "Nueva tarea en PLAN-CS-F2/R4. Re-juicio: 24967 NO CUMPLE."
    )},
    {"tarea_id": 63, "plan_id": "PLAN-CS-M5", "motivo": (
        "M5/R1: el fichero docker-compose.demo.yml no existe en ninguna rama publica. "
        "01 publica compose y README en main, nueva tarea PLAN-CS-F2/R3. "
        "Re-juicio: 24986 NO CUMPLE."
    )},
]

NOTAS_LEAD = [
    {"tarea_id": 13, "plan_id": "PLAN-CS-T05", "rejuicio": 24983, "nota": (
        "Tarea 13 (T05/R1): CUMPLE y firma sin evento tarea_entregada. "
        "No se fabrica entrega con fecha antigua. Re-juicio 24983 valida "
        "sobre clon limpio de hoy. " + APROBACION + "."
    )},
    {"tarea_id": 18, "plan_id": "PLAN-CS-T10", "rejuicio": 24987, "nota": (
        "Tarea 18 (T10/R1): CUMPLE y firma sin evento tarea_entregada. "
        "No se fabrica entrega con fecha antigua. Re-juicio 24987 valida "
        "sobre clon limpio de hoy. " + APROBACION + "."
    )},
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def restaurar(conn, r, ts, dry_run):
    plan_id = r["plan_id"]
    ref = r["ref"]

    current = conn.execute(
        "SELECT ears, comprobacion FROM requisito WHERE plan_id=? AND ref=?",
        (plan_id, ref),
    ).fetchone()
    if not current:
        print(f"  [SKIP] {plan_id}/{ref} no existe")
        return
    old_ears, old_comp = current

    if old_ears == r["ears"] and old_comp == r["comprobacion"]:
        print(f"  [SKIP] {plan_id}/{ref} ya tiene el texto restaurado")
        return

    if r.get("crear_r2"):
        existing_r2 = conn.execute(
            "SELECT 1 FROM requisito WHERE plan_id=? AND ref='R2'", (plan_id,)
        ).fetchone()
        if not existing_r2:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, "R2", old_ears, old_comp),
            )
            print(f"    [R2] {plan_id}/R2 creado con texto vigente")
        else:
            print(f"    [R2] {plan_id}/R2 ya existe, no se duplica")

    conn.execute(
        "UPDATE requisito SET ears=?, comprobacion=? WHERE plan_id=? AND ref=?",
        (r["ears"], r["comprobacion"], plan_id, ref),
    )

    evento_origen = r.get("evento_origen", "spec @7a4f4b4")
    evento_rejuicio = r["evento_rejuicio"]
    detalle = (
        f"{plan_id}/{ref} restaurado. "
        f"Vigente antes: ears='{old_ears[:80]}...', comp='{old_comp[:60]}...'. "
        f"Restaurado a: ears='{r['ears'][:80]}...', comp='{r['comprobacion'][:60]}...'. "
        f"Origen: evento {evento_origen}. Re-juicio: evento {evento_rejuicio}. "
        f"{r.get('nota', '')}. {APROBACION}."
    )

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "requisito_restaurado", plan_id, detalle),
    )
    print(f"  [OK] {plan_id}/{ref} restaurado ({r.get('nota', '')})")


def devolver(conn, d, ts):
    tid = d["tarea_id"]
    row = conn.execute(
        "SELECT progreso FROM tarea WHERE id=?", (tid,)
    ).fetchone()
    if not row:
        print(f"  [SKIP] tarea {tid} no existe")
        return
    if row[0] == "devuelta":
        print(f"  [SKIP] tarea {tid} ya devuelta")
        return

    conn.execute(
        "UPDATE tarea SET progreso='devuelta' WHERE id=?", (tid,)
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "tarea_devuelta", d["plan_id"],
         f"tarea {tid} devuelta. {d['motivo']} {APROBACION}."),
    )
    print(f"  [OK] tarea {tid} devuelta")


def nota_lead(conn, n, ts):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "nota_lead", n["plan_id"], n["nota"]),
    )
    print(f"  [OK] nota_lead tarea {n['tarea_id']}")


def main():
    ap = argparse.ArgumentParser(description="Restaurar requisitos ablandados")
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
        backup_registro(conn, db_path, "pre-restauracion")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        print("[1/4] Restauraciones principales (6 requisitos)")
        for r in RESTAURACIONES:
            restaurar(conn, r, ts, args.dry_run)

        print("\n[2/4] Restauraciones M2 (R0 + R1)")
        for r in M2_RESTAURACIONES:
            restaurar(conn, r, ts, args.dry_run)

        print("\n[3/4] Devoluciones (3 tareas)")
        for d in DEVOLUCIONES:
            devolver(conn, d, ts)

        print("\n[4/4] Notas lead (tareas 13, 18)")
        for n in NOTAS_LEAD:
            nota_lead(conn, n, ts)

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(f"\n[OK] Restauracion completa")
    if args.dry_run:
        print("--dry-run: transaccion deshecha")


if __name__ == "__main__":
    main()
