"""Corrige ámbito de sol:coforge:como-estoy-hecho a coforge-santander.

El nodo tiene ambito=vmi3211028 pero debería ser coforge-santander
(como rag-banking-agent) para que aparezca en la colección pública.

    python3 corregir_ambito_ceh.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
NODO_ID = "sol:coforge:como-estoy-hecho"
OLD_AMBITO = "vmi3211028"
NEW_AMBITO = "coforge-santander"


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

    row = conn.execute(
        "SELECT ambito FROM nodo WHERE id=?", (NODO_ID,)
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] nodo {NODO_ID} no existe")

    current = row[0]
    if current == NEW_AMBITO:
        print(f"[OK] ambito ya es {NEW_AMBITO}")
        conn.close()
        return

    if current != OLD_AMBITO:
        sys.exit(f"[FALLO] ambito esperado {OLD_AMBITO}, encontrado {current}")

    print(f"[{NODO_ID}] ambito: {current} → {NEW_AMBITO}")

    if not args.dry_run:
        backup_registro(conn, db_path, "ambito-ceh")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        conn.execute(
            "UPDATE nodo SET ambito=? WHERE id=?",
            (NEW_AMBITO, NODO_ID),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'nodo_corregido', ?, NULL, ?)",
            (ts, ACTOR, NODO_ID,
             f"ambito corregido: {OLD_AMBITO} → {NEW_AMBITO} "
             f"(anclar en colección coforge-santander para que /oferta muestre dos soluciones)"),
        )
        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    verify = conn.execute(
        "SELECT id, ambito FROM nodo WHERE tipo='solucion' AND ambito=?",
        (NEW_AMBITO,),
    ).fetchall()
    print(f"\n[OK] soluciones en {NEW_AMBITO}:")
    for nid, amb in verify:
        print(f"  {nid} (ambito={amb})")

    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
