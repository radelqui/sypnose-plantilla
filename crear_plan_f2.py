"""Crea PLAN-CS-F2 (Reparaciones tras el re-juicio) — operador, no autor.

Requisitos dictados por 00-lead en Requerimientos/F2/requisitos-dictados.md
(sha256 d36404c19fa8eeb5d28bdccadef023c8b76c3588c1a81c0add8645746f868c2e).
El arquitecto actua como operador: no es autor ni ejecutor.

    python3 crear_plan_f2.py --db ~/sypnose-f1/registry.db [--dry-run]
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
FUENTE = "plantilla/crear_plan_f2.py"

PLAN_ID = "PLAN-CS-F2"
SOL_ID = "sol:coforge:rag-banking-agent"
FICHERO_HASH = "d36404c19fa8eeb5d28bdccadef023c8b76c3588c1a81c0add8645746f868c2e"

EARS_R1 = (
    "Cuando se consulte la última ejecución del workflow de CI en la rama main de "
    "radelqui/rag-banking-agent, el job de tests DEBE haber terminado en success con "
    "las cinco puertas ejecutadas (ruff, bandit, pytest con cobertura mínima del 85 %, "
    "gitleaks y trivy) y el job de despliegue DEBE quedar esperando la aprobación humana; "
    "la rama main DEBE tener protección de rama con el check de tests como requerido; "
    "y el main local de los worktrees DEBE coincidir con origin/main."
)
COMPROBACION_R1 = "python ci/comprobar_ci_main.py"

EARS_R2 = (
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
)
COMPROBACION_R2 = "python plantilla/comprobar_trailers.py"

EARS_R3 = (
    "El fichero microservicio/demo/docker-compose.demo.yml y su README de tres órdenes "
    "DEBEN existir en la rama main de radelqui/sypnose-plantilla, con los servicios "
    "rag-banking-agent, como-estoy-hecho y la base efímera, healthcheck en cada servicio "
    "de aplicación y ninguna variable con valor de secreto."
)
COMPROBACION_R3 = "python microservicio/demo/comprobar_compose.py"

EARS_R4 = (
    "El fichero specs/T06/spec.md DEBE estar escrito por el rol 07-verificador (trailer "
    "Chat: 07-verificador en el commit que lo crea o lo reescribe), con el requisito R1 "
    "de T06 restaurado a su invariante original (ninguna tarea pasa a espera_firma sin "
    "verificada_por distinto del agente ejecutor; recuento igual a 0) y sin el contador "
    "de eventos con la palabra CUMPLE."
)
COMPROBACION_R4 = 'git log -1 --format=%(trailers:key=Chat,valueonly) -- specs/T06/spec.md'

TAREAS = [
    {
        "req_ref": "R1",
        "titulo": "CI de main en verde y proteccion de rama",
        "agente": "IA:01-git-cicd:claude-opus-4-6",
    },
    {
        "req_ref": "R2",
        "titulo": "Requisito honesto de trailers para la linea de Git",
        "agente": "IA:01-git-cicd:claude-opus-4-6",
    },
    {
        "req_ref": "R3",
        "titulo": "Compose de la demo publicado en main",
        "agente": "IA:01-git-cicd:claude-opus-4-6",
    },
    {
        "req_ref": "R4",
        "titulo": "Spec de T06 escrita por el rol verificador",
        "agente": "IA:07-verificador:claude-opus-5",
    },
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(description="Crear PLAN-CS-F2 (reparaciones re-juicio)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        print(f"[skip] {PLAN_ID} ya existe")
        conn.close()
        return

    sol = conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone()
    if not sol:
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-f2")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, "
            "dueno, worktree, abierto_en) "
            "VALUES (?, 'mantener', "
            "'Reparaciones tras el re-juicio retroactivo: CI, trailers, compose, spec T06', "
            "'Que los artefactos pendientes del microservicio y la plantilla cumplan sus "
            "requisitos originales sin haber sido ablandandos', "
            "'Re-juicio retroactivo (eventos 24966, 24967, 24986), informe de viabilidad de "
            "Jev (§2.1, §7.3) y restauracion de requisitos F1', "
            "?, 'abierto', ?, 'H:carlos', 'plantilla/wt-F2', ?)",
            (PLAN_ID, SOL_ID, ACTOR, ts),
        )
        print(f"  [plan] {PLAN_ID} creado (afecta {SOL_ID})")

        reqs = [
            ("R1", EARS_R1, COMPROBACION_R1),
            ("R2", EARS_R2, COMPROBACION_R2),
            ("R3", EARS_R3, COMPROBACION_R3),
            ("R4", EARS_R4, COMPROBACION_R4),
        ]
        for ref, ears, comp in reqs:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (PLAN_ID, ref, ears, comp),
            )
            print(f"  [req] {PLAN_ID}/{ref}")

        tarea_ids = []
        for t in TAREAS:
            cur = conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
                "VALUES (?,?,?,?,?)",
                (PLAN_ID, t["req_ref"], t["titulo"], "pendiente", t["agente"]),
            )
            tarea_ids.append(cur.lastrowid)
            print(f"  [tarea] {cur.lastrowid}: {PLAN_ID}/{t['req_ref']} -> {t['agente']}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_creado", PLAN_ID,
             f"plan {PLAN_ID} reparaciones re-juicio, afecta {SOL_ID}, "
             f"4 requisitos (R1-R4), 4 tareas ({','.join(str(t) for t in tarea_ids)}). "
             f"Requisitos dictados por 00-lead, fichero Requerimientos/F2/requisitos-dictados.md "
             f"sha256 {FICHERO_HASH[:16]}...; el arquitecto actua como operador, "
             f"no es autor ni ejecutor. "
             f"Ejecutores: R1-R3 IA:01-git-cicd:claude-opus-4-6, "
             f"R4 IA:07-verificador:claude-opus-5 (veredicto R4 por humano o segundo "
             f"verificador, D7b)."),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(f"\n[OK] {PLAN_ID}: 4 req, 4 tareas")
    for i, tid in enumerate(tarea_ids):
        print(f"  tarea {tid}: {TAREAS[i]['titulo']}")
    if args.dry_run:
        print("--dry-run: transaccion deshecha")


if __name__ == "__main__":
    main()
