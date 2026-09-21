"""Crea PLAN-CS-M6 (adaptación a las 7 piezas del responsable de la oferta).

El responsable publicó su plantilla en LinkedIn con 7 piezas: 1 Temporal,
2 Claude Agent SDK, 3 OpenHands, 4 vLLM, 5 pgvector+Apache AGE,
6 K8s/IAM/secretos/aislamiento, 7 extras RTK/agentmemory/MCP.
Este plan carga: 4 opciones nuevas de stack (vllm, openhands, apache-age,
rtk-agentmemory), las 7 filas de portada_pieza_agenticas y la comprobación
literal comprobar_m6.py.

    python3 crear_plan_m6.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import (
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
    verificar_sin_delete,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_m6.py"

PLAN_ID = "PLAN-CS-M6"
SOL_ID = "sol:coforge:sypnose-plantilla"

REQUISITOS = [
    {
        "ref": "R1",
        "titulo": "7 piezas del responsable cargadas + 4 opciones de stack",
        "ears": (
            "Cuando se ejecute python plantilla/comprobar_m6.py --db <copia de registry.db> "
            "desde el worktree, DEBE encontrar las 7 piezas de la plantilla del responsable "
            "(Temporal, Claude Agent SDK, OpenHands, vLLM, pgvector+Apache AGE, "
            "K8s/IAM/secretos, extras RTK/agentmemory/MCP) cargadas en el registro con "
            "estado y evidencia (hecho/parcial) o marca de opción no-en-POC, y el stack "
            "con las 4 opciones nuevas (vllm, openhands, apache-age, rtk-agentmemory) "
            "en estado opcion-no-poc con decide_banco y que_cambia."
        ),
        "comprobacion": "python plantilla/comprobar_m6.py --db copia-registry.db",
    },
]

TAREAS = [
    {
        "req_ref": "R1",
        "titulo": (
            "Cargar 4 opciones de stack (vLLM, OpenHands, Apache AGE, RTK+agentmemory) "
            "y las 7 piezas agénticas en portada; comprobación comprobar_m6.py"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    verificar_sin_delete()
    verificar_repo_limpio()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_canonicos_registrados(conn)

    if conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        print(f"[skip] {PLAN_ID} ya existe")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db, "pre-m6")

    sol = conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone()
    if not sol:
        conn.close()
        raise SystemExit(f"[FALLO] {SOL_ID} no existe en nodo")
    print(f"  [sol] {SOL_ID} existe")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
            "VALUES (?, 'mantener', "
            "'Adaptar la plantilla a las 7 piezas del responsable de la oferta', "
            "'Que la oferta cubra la plantilla publicada por el responsable en LinkedIn: "
            "Temporal, Claude Agent SDK, OpenHands, vLLM, pgvector+Apache AGE, K8s/IAM/secretos, extras RTK/agentmemory/MCP', "
            "'El responsable publicó su plantilla con 7 piezas; la oferta debe mostrar dónde está cada una "
            "hoy (hecho/parcial) y qué cambiaría (opción no-en-POC)', "
            "?, 'abierto', ?, 'H:carlos', 'plantilla/wt-M6', ?)",
            (PLAN_ID, SOL_ID, ACTOR, ts),
        )
        print(f"  [plan] {PLAN_ID} creado y abierto (afecta {SOL_ID})")

        for req in REQUISITOS:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (PLAN_ID, req["ref"], req["ears"], req["comprobacion"]),
            )
            print(f"  [req] {PLAN_ID}/{req['ref']} creado")

        tarea_ids = []
        for t in TAREAS:
            cur = conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (PLAN_ID, t["req_ref"], t["titulo"], "pendiente", t["agente"]),
            )
            tarea_ids.append(cur.lastrowid)
            print(f"  [tarea] {cur.lastrowid}: {PLAN_ID}/{t['req_ref']} → {t['agente']}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_creado", PLAN_ID,
             f"plan {PLAN_ID} afecta {SOL_ID}, {len(REQUISITOS)} requisitos, "
             f"{len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)}). "
             f"Orden del lead 2026-09-17: adaptar a las 7 piezas del responsable."),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(f"\n[OK] {PLAN_ID}: {len(REQUISITOS)} req, {len(TAREAS)} tareas")
    if args.dry_run:
        print("--dry-run: transacción deshecha")


if __name__ == "__main__":
    main()
