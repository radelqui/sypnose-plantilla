"""Bloquea una tarea detrás de otra (pendiente → bloqueada, bloqueada_por=<id>).

    python3 bloquear_tarea.py --db ~/sypnose-f1/registry.db --tarea 15 --detras-de 39
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
    ap = argparse.ArgumentParser(description="Bloquea una tarea detrás de otra")
    ap.add_argument("--db", required=True)
    ap.add_argument("--tarea", type=int, required=True, help="tarea a bloquear")
    ap.add_argument("--detras-de", type=int, required=True, help="tarea bloqueante")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    t = conn.execute(
        "SELECT id, plan_id, req_ref, titulo, progreso FROM tarea WHERE id=?",
        (args.tarea,),
    ).fetchone()
    if not t:
        sys.exit(f"[FALLO] tarea {args.tarea} no existe")
    if t[4] not in ("pendiente",):
        sys.exit(f"[FALLO] tarea {args.tarea} progreso={t[4]}, esperado pendiente")

    b = conn.execute(
        "SELECT id, plan_id, req_ref, titulo, progreso FROM tarea WHERE id=?",
        (args.detras_de,),
    ).fetchone()
    if not b:
        sys.exit(f"[FALLO] tarea bloqueante {args.detras_de} no existe")
    if t[1] != b[1]:
        sys.exit(f"[FALLO] tareas en planes distintos: {t[1]} vs {b[1]}")

    print(f"[bloquear] tarea {t[0]} ({t[2]}: {t[3]}) detrás de tarea {b[0]} ({b[2]}: {b[3]})")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    bk = backup_registro(conn, db_path, "bloquear")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tarea SET progreso='bloqueada', bloqueada_por=? WHERE id=?",
            (args.detras_de, args.tarea),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_bloqueada", t[1],
             f"tarea {args.tarea} ({t[2]}) bloqueada por tarea {args.detras_de} ({b[2]})"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {args.tarea} → bloqueada (detrás de {args.detras_de})")


if __name__ == "__main__":
    main()
