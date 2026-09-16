"""Actualiza afirmaciones commit de rag-banking-agent al SHA de origin/main.

Las afirmaciones commit de ficheros de rag-banking-agent apuntan al HEAD
local viejo (a582cb2b); origin/main va por delante (a612c1fe). Este script
marca las viejas vigente=0 e inserta nuevas con el SHA correcto.

    python3 actualizar_commit_rag.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
RAG_REPO = PLANTILLA_DIR.parent / "rag-banking-agent"
OLD_SHA = "a582cb2b20ca1c7a0787a0dd0410c6985a340166"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_origin_main_sha(repo: Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "origin/main"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] no se pudo resolver origin/main en {repo}")
    return r.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    if not RAG_REPO.exists():
        sys.exit(f"[FALLO] repo rag-banking-agent no encontrado en {RAG_REPO}")

    new_sha = get_origin_main_sha(RAG_REPO)
    print(f"[rag-banking-agent] origin/main = {new_sha[:12]}")
    print(f"[old] = {OLD_SHA[:12]}")

    if new_sha == OLD_SHA:
        print("[OK] no hay cambio de SHA")
        return

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    rows = conn.execute(
        "SELECT id, nodo_id, campo, valor, certeza, fuente, actor_id "
        "FROM afirmacion WHERE campo='commit' AND valor=? AND vigente=1",
        (OLD_SHA,),
    ).fetchall()

    if not rows:
        print("[OK] no hay afirmaciones con el SHA viejo")
        return

    print(f"\n[afirmaciones a actualizar] {len(rows)}:")
    for row in rows:
        print(f"  {row[1]} campo={row[2]} valor={row[3][:12]}...")

    for _, nodo_id, _, _, _, _, _ in rows:
        parts = nodo_id.split(":")
        if "rag-banking-agent" in nodo_id:
            path = ":".join(parts[3:]) if len(parts) > 3 else ""
            if path:
                r = subprocess.run(
                    ["git", "-C", str(RAG_REPO), "cat-file", "-e", f"{new_sha}:{path}"],
                    capture_output=True, timeout=10,
                )
                if r.returncode != 0:
                    print(f"  [WARN] {path} no existe en {new_sha[:12]}")

    if not args.dry_run:
        backup_registro(conn, db_path, "commit-rag-sha")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        retired = 0
        inserted = 0

        for aid, nodo_id, campo, valor, certeza, fuente, actor_id in rows:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            retired += 1

            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nodo_id, campo, new_sha, certeza,
                 "plantilla/actualizar_commit_rag.py", ACTOR, ts),
            )
            inserted += 1

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'commit_sha_corregido', ?, NULL, ?)",
            (ts, ACTOR, "sol:coforge:rag-banking-agent",
             f"{retired} afirmaciones commit actualizadas: {OLD_SHA[:12]} → {new_sha[:12]} "
             f"(origin/main tras git fetch)"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] retiradas: {retired} · nuevas: {inserted}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")

    conn.close()


if __name__ == "__main__":
    main()
