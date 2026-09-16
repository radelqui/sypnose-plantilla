"""Añade relaciones cubre de ficheros de seguridad a linea:coforge:T12.

Los ficheros de app/security y tests/test_pii.py/test_guardrails.py cubren T12.

    python3 cubre_ficheros_t12.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cubre_ficheros_t12.py"
LINEA = "linea:coforge:T12"

FICHEROS = [
    "mod:vmi3211028:rag-banking-agent:app/security/pii.py",
    "mod:vmi3211028:rag-banking-agent:app/security/guardrails.py",
    "mod:vmi3211028:rag-banking-agent:app/security/identity.py",
    "mod:vmi3211028:rag-banking-agent:tests/test_pii.py",
    "mod:vmi3211028:rag-banking-agent:tests/test_guardrails.py",
]


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

    missing = [f for f in FICHEROS if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (f,)).fetchone()]
    if missing:
        print(f"[WARN] nodos no encontrados (se crearán): {missing}")

    if not args.dry_run:
        backup_registro(conn, db_path, "cubre-t12")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        inserted = 0

        for nodo_id in FICHEROS:
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
                nombre = nodo_id.split(":")[-1].split("/")[-1]
                ruta = nodo_id.split(":", 3)[-1]
                conn.execute(
                    "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, descubierto_en, descubierto_por) "
                    "VALUES (?, 'modulo', ?, ?, 'vmi3211028', ?, ?)",
                    (nodo_id, nombre, ruta, ts, ACTOR),
                )
                print(f"  [nodo] {nodo_id}")

            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                (nodo_id, LINEA, FUENTE, ts),
            ).rowcount
            if rc:
                inserted += 1
                print(f"  [cubre] {nodo_id.split(':')[-1]} → T12")
            else:
                print(f"  [skip] {nodo_id.split(':')[-1]} → T12 (ya existe)")

        if inserted:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'cubre_ficheros_t12', NULL, NULL, ?)",
                (ts, ACTOR, f"{inserted} relaciones cubre fichero→T12 (seguridad: pii, guardrails, identity, tests)"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {inserted} cubre insertados")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
