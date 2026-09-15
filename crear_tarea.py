"""Crea una tarea en el registro SYPNOSE con barrera y backup.

    python3 crear_tarea.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T01 --ref R1 \
        --titulo "Ejecutar la comprobación de R1 y entregar por el caparazón" \
        --agente IA:02-backend-api:claude-sonnet-5
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Crea tarea en el registro")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--plan", required=True, help="plan_id, ej. PLAN-CS-T01")
    ap.add_argument("--ref", required=True, help="req_ref, ej. R1")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--agente", required=True, help="agente asignado")
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    req = conn.execute(
        "SELECT 1 FROM requisito WHERE plan_id=? AND ref=?",
        (args.plan, args.ref),
    ).fetchone()
    if not req:
        sys.exit(f"[FALLO] requisito {args.plan}/{args.ref} no existe")

    if args.dry_run:
        print(f"[dry-run] INSERT tarea: plan={args.plan} ref={args.ref} agente={args.agente}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "tarea")

    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
            (args.plan, args.ref, args.titulo, "pendiente", args.agente),
        )
        tarea_id = cur.lastrowid

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), args.actor, "tarea_creada", args.plan, f"tarea {tarea_id}: {args.titulo} (agente {args.agente})"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {tarea_id} creada: {args.plan}/{args.ref} → {args.agente}")


if __name__ == "__main__":
    main()
