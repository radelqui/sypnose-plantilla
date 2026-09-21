"""Corrige commit afirmaciones de specs y crea nodo T10 spec.

El repo radelqui/sypnose-plantilla se acaba de empujar a GitHub.
Los commit afirmaciones de los spec nodos apuntaban a 6e83c74 (bulk);
este script carga el SHA del commit real de cada spec en main.

También crea mod:plantilla:specs/T10/spec.md (no existía).

    python3 corregir_commits_specs.py --db ~/sypnose-f1/registry.db [--dry-run]
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
FUENTE = "plantilla/corregir_commits_specs.py"
AMBITO = "vmi3211028"

SPECS = {
    "specs/T01/spec.md": "111454bf87cc41ade2ee982beef532d4559568e8",
    "specs/T02/spec.md": "cddfbc46244dd07454227d5349a6710e686483de",
    "specs/T03/spec.md": "98ada51ef86012a662af92abb9632db50504d91e",
    "specs/T10/spec.md": "19eac3404c29c82c817f4f2a8cbfa8945b393e23",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    for path, sha in SPECS.items():
        r = subprocess.run(
            ["git", "-C", str(PLANTILLA_DIR), "cat-file", "-e", f"{sha}:{path}"],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            sys.exit(f"[FALLO] {path} no existe en commit {sha[:12]}")
    print(f"[OK] {len(SPECS)} specs verificados en sus commits")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not args.dry_run:
        backup_registro(conn, db_path, "commits-specs")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        nodos_nuevos = 0
        commits_actualizados = 0
        repos_nuevos = 0

        for path, sha in SPECS.items():
            nodo_id = f"mod:plantilla:{path}"
            nombre = path.split("/")[-1]

            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
                conn.execute(
                    "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, descubierto_en, descubierto_por) "
                    "VALUES (?, 'modulo', ?, ?, ?, ?, ?)",
                    (nodo_id, nombre, path, AMBITO, ts, ACTOR),
                )
                nodos_nuevos += 1
                print(f"  [nodo] {nodo_id}")

            existing = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='commit' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            if existing and existing[1] == sha:
                print(f"  [skip] {path} commit ya es {sha[:12]}")
                continue
            if existing:
                conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (existing[0],))
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                "VALUES (?, 'commit', ?, 'observado', ?, ?, ?, 1)",
                (nodo_id, sha, FUENTE, ACTOR, ts),
            )
            commits_actualizados += 1
            print(f"  [commit] {path}: {sha[:12]}")

            repo_existing = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='repo' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            repo_url = "https://github.com/radelqui/sypnose-plantilla"
            if not repo_existing or repo_existing[1] != repo_url:
                if repo_existing:
                    conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (repo_existing[0],))
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                    "VALUES (?, 'repo', ?, 'observado', ?, ?, ?, 1)",
                    (nodo_id, repo_url, FUENTE, ACTOR, ts),
                )
                repos_nuevos += 1

        if nodos_nuevos or commits_actualizados:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'commits_specs_corregidos', NULL, NULL, ?)",
                (ts, ACTOR,
                 f"{commits_actualizados} commits de spec actualizados al SHA real de main, "
                 f"{nodos_nuevos} nodos spec nuevos (T10), {repos_nuevos} repo afirmaciones. "
                 f"Repo radelqui/sypnose-plantilla creado y empujado a GitHub"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] nodos={nodos_nuevos} commits={commits_actualizados} repos={repos_nuevos}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
