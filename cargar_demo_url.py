"""Carga afirmación demo_url en las dos soluciones.

Tarea 65: tras despliegue en el 67, registrar las URLs de demo.

    python3 cargar_demo_url.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_demo_url.py"

DEMO_URLS = [
    ("sol:coforge:rag-banking-agent", "https://coforge.sypnose.cloud/demo/rag/api/v1/health/live"),
    ("sol:coforge:como-estoy-hecho", "https://coforge.sypnose.cloud/demo/ceh/como-estoy-hecho/ui/"),
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

    if not args.dry_run:
        backup_registro(conn, db_path, "demo-url")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        inserted = 0

        for nodo_id, url in DEMO_URLS:
            existing = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='demo_url' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            if existing and existing[1] == url:
                print(f"  [skip] {nodo_id} ya tiene demo_url={url}")
                continue
            if existing:
                conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (existing[0],))
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                "VALUES (?, 'demo_url', ?, 'observado', ?, ?, ?, 1)",
                (nodo_id, url, FUENTE, ACTOR, ts),
            )
            inserted += 1
            print(f"  [demo_url] {nodo_id} → {url}")

        if inserted:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'demo_url_cargada', NULL, NULL, ?)",
                (ts, ACTOR,
                 f"{inserted} demo_url afirmaciones: rag-banking-agent en /demo/rag, "
                 f"como-estoy-hecho en /demo/ceh, proxy nginx en 7104 via coforge.sypnose.cloud"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {inserted} demo_url cargadas")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
