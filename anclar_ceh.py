"""Inserta ancla de sol:coforge:como-estoy-hecho en colección coforge-santander.

La vista /oferta usa v_alcance que empieza en ancla; sin ancla los componentes
y produjo de la solución quedan vacíos.

    python3 anclar_ceh.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
SOL_ID = "sol:coforge:como-estoy-hecho"
COLECCION = "coforge-santander"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone():
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe")

    existing = conn.execute(
        "SELECT 1 FROM ancla WHERE coleccion_id=? AND nodo_id=?",
        (COLECCION, SOL_ID),
    ).fetchone()
    if existing:
        print(f"[OK] ancla ({COLECCION}, {SOL_ID}) ya existe")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "anclar-ceh")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        conn.execute(
            "INSERT INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
            (COLECCION, SOL_ID),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'ancla_registrada', ?, NULL, ?)",
            (ts, ACTOR, SOL_ID,
             f"ancla ({COLECCION}, {SOL_ID}) para que v_alcance incluya componentes en /oferta"),
        )
        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"[OK] ancla ({COLECCION}, {SOL_ID}) insertada")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
