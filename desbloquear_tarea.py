"""Desbloquea una tarea (bloqueada → pendiente, bloqueada_por=NULL).

    python3 desbloquear_tarea.py --db ~/sypnose-f1/registry.db --tarea 50
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
    ap = argparse.ArgumentParser(description="Desbloquea una tarea bloqueada")
    ap.add_argument("--db", required=True)
    ap.add_argument("--tarea", type=int, required=True, help="tarea a desbloquear")
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
        "SELECT id, plan_id, req_ref, titulo, progreso, bloqueada_por FROM tarea WHERE id=?",
        (args.tarea,),
    ).fetchone()
    if not t:
        sys.exit(f"[FALLO] tarea {args.tarea} no existe")
    if t[4] != "bloqueada":
        sys.exit(f"[FALLO] tarea {args.tarea} progreso={t[4]}, esperado bloqueada")

    bloqueante = conn.execute(
        "SELECT id, progreso FROM tarea WHERE id=?", (t[5],),
    ).fetchone()
    if bloqueante and bloqueante[1] != "hecha":
        print(f"[WARN] tarea bloqueante {bloqueante[0]} aún no está hecha (progreso={bloqueante[1]})")

    print(f"[desbloquear] tarea {t[0]} ({t[2]}: {t[3]}) — bloqueada_por={t[5]}")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    bk = backup_registro(conn, db_path, "desbloquear")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tarea SET progreso='pendiente', bloqueada_por=NULL WHERE id=?",
            (args.tarea,),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_desbloqueada", t[1],
             f"tarea {args.tarea} ({t[2]}) desbloqueada (bloqueante {t[5]} hecha)"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {args.tarea} → pendiente (desbloqueada)")


if __name__ == "__main__":
    main()
