"""Carga afirmación repo (URL pública) en todos los nodos fichero/carpeta.

Hallazgo de Carlos: requirements.txt de rag-banking-agent se enlaza bajo
el repo de como-estoy-hecho → 404. La vista usa repoDe(idsSol[0]) que
toma el primer repo alfabéticamente. Con una afirmación repo por nodo
fichero, la vista puede resolver el repo correcto por fichero.

    python3 cargar_repo_ficheros.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_repo_ficheros.py"

REPO_MAP = [
    ("mod:vmi3211028:rag-banking-agent:%", "https://github.com/radelqui/rag-banking-agent"),
    ("dir:vmi3211028:rag-banking-agent:%", "https://github.com/radelqui/rag-banking-agent"),
    ("mod:coforge-santander:como-estoy-hecho:%", "https://github.com/radelqui/como-estoy-hecho"),
    ("dir:coforge-santander:como-estoy-hecho:%", "https://github.com/radelqui/como-estoy-hecho"),
    ("mod:plantilla:%", "https://github.com/radelqui/sypnose-plantilla"),
]

CEH_MISPLACED = {
    "mod:vmi3211028:rag-banking-agent:como-estoy-hecho:app/como_estoy_hecho/router.py":
        "https://github.com/radelqui/como-estoy-hecho",
    "mod:vmi3211028:rag-banking-agent:como-estoy-hecho:app/como_estoy_hecho/static/index.html":
        "https://github.com/radelqui/como-estoy-hecho",
}


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

    nodos = []
    for pattern, repo_url in REPO_MAP:
        rows = conn.execute(
            "SELECT id FROM nodo WHERE id LIKE ? AND tipo IN ('modulo','carpeta')",
            (pattern,),
        ).fetchall()
        for (nid,) in rows:
            actual_repo = CEH_MISPLACED.get(nid, repo_url)
            nodos.append((nid, actual_repo))

    print(f"[repo] {len(nodos)} nodos fichero/carpeta a procesar")

    if not nodos:
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "repo-ficheros")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        inserted = 0
        skipped = 0

        for nid, repo_url in nodos:
            existing = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='repo' AND vigente=1",
                (nid,),
            ).fetchone()
            if existing and existing[1] == repo_url:
                skipped += 1
                continue
            if existing:
                conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (existing[0],))
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                "VALUES (?, 'repo', ?, 'observado', ?, ?, ?, 1)",
                (nid, repo_url, FUENTE, ACTOR, ts),
            )
            inserted += 1

        if inserted:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'repo_ficheros_cargado', NULL, NULL, ?)",
                (ts, ACTOR,
                 f"{inserted} afirmaciones repo en nodos fichero/carpeta "
                 f"(rag-banking-agent, como-estoy-hecho, plantilla); "
                 f"{skipped} ya tenían el valor correcto"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {inserted} repo insertados, {skipped} ya correctos")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
