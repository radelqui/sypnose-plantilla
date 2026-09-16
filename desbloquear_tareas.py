"""Desbloquea tareas cuya tarea bloqueante ya está hecha.

    python3 desbloquear_tareas.py --db ~/sypnose-f1/registry.db --ids 53,54,55
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Desbloquear tareas")
    ap.add_argument("--db", required=True)
    ap.add_argument("--ids", required=True, help="IDs separados por coma")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = [int(x.strip()) for x in args.ids.split(",")]
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    tareas = []
    for tid in ids:
        row = conn.execute(
            "SELECT id, plan_id, progreso, bloqueada_por, agente FROM tarea WHERE id=?",
            (tid,),
        ).fetchone()
        if not row:
            sys.exit(f"[FALLO] tarea {tid} no existe")
        if row[2] != "bloqueada":
            sys.exit(f"[FALLO] tarea {tid} progreso={row[2]}, no es bloqueada")
        blq = row[3]
        if blq:
            blq_row = conn.execute("SELECT progreso FROM tarea WHERE id=?", (blq,)).fetchone()
            if not blq_row or blq_row[0] != "hecha":
                sys.exit(f"[FALLO] tarea {tid} bloqueada por {blq} que no está hecha ({blq_row[0] if blq_row else 'no existe'})")
        tareas.append(row)
        print(f"[tarea] {tid}: bloqueada por {blq} → pendiente")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "desbloquear")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in tareas:
            tid, plan_id = row[0], row[1]
            conn.execute(
                "UPDATE tarea SET progreso='pendiente', bloqueada_por=NULL WHERE id=?",
                (tid,),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "tarea_desbloqueada", plan_id,
                 f"tarea {tid} desbloqueada (tarea 52 R0 hecha)"),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {len(tareas)} tareas desbloqueadas")


if __name__ == "__main__":
    main()
