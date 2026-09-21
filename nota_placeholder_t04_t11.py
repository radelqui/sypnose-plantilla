"""Registra nota_arquitecto sobre firmas provisionales de T04/T11.

La UI verificada en evento 57 de como-estoy-hecho era un placeholder.
Las firmas de T04/T11 son provisionales hasta que PLAN-CS2-U (interfaz
real por 04-agentes) reciba CUMPLE de 07.

    python3 nota_placeholder_t04_t11.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
LINEAS = ["linea:coforge:T04", "linea:coforge:T11"]
DETALLE = (
    "firma de líneas T04/T11 provisional: la UI verificada en 57 era placeholder; "
    "se re-firmará tras el CUMPLE de PLAN-CS2-U (interfaz real por 04)"
)


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

    for linea in LINEAS:
        if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (linea,)).fetchone():
            sys.exit(f"[FALLO] nodo {linea} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "nota-placeholder-t04-t11")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        for linea in LINEAS:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'nota_arquitecto', ?, 'PLAN-CS2-U', ?)",
                (ts, ACTOR, linea, DETALLE),
            )
            print(f"  [evento] nota_arquitecto → {linea}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {len(LINEAS)} eventos nota_arquitecto registrados")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
