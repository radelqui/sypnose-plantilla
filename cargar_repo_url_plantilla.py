"""Carga tecnico:repo_url sobre sol:coforge:sypnose-plantilla.

    python3 cargar_repo_url_plantilla.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
NODO_ID = "sol:coforge:sypnose-plantilla"
CAMPO = "tecnico:repo_url"
VALOR = "https://github.com/radelqui/sypnose-plantilla"


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

    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (NODO_ID,)).fetchone():
        sys.exit(f"[FALLO] nodo {NODO_ID} no existe")

    existing = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
        (NODO_ID, CAMPO),
    ).fetchone()
    if existing:
        print(f"[OK] ya existe: {existing[0]}")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "repo-url-plantilla")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
            "VALUES (?, ?, ?, 'observado', 'plantilla/cargar_repo_url_plantilla.py', ?, ?)",
            (NODO_ID, CAMPO, VALOR, ACTOR, ts),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'repo_url_cargado', ?, NULL, ?)",
            (ts, ACTOR, NODO_ID, f"tecnico:repo_url = {VALOR}"),
        )
        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"[OK] {NODO_ID} → {CAMPO} = {VALOR}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
