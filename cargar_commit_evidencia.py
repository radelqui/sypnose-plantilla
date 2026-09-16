"""Carga afirmación 'commit' sobre cada nodo fichero (mod:*) enlazado por tec→usa→fichero.

Valor = sha de HEAD del repo donde el fichero existe hoy (git cat-file -e).
Certeza = observado. Solo inserta; no toca filas existentes.

    python3 cargar_commit_evidencia.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_commit_evidencia.py"
REPO_RAG = PLANTILLA_DIR.parent / "rag-banking-agent"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_head(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo), text=True).strip()


def file_exists_at_head(repo: Path, path: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "cat-file", "-e", f"HEAD:{path}"],
            cwd=str(repo),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--actor", default=ACTOR)
    args = p.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_canonicos_registrados(conn)

    rows = conn.execute(
        "SELECT DISTINCT n.id, n.nombre "
        "FROM nodo n JOIN relacion r ON r.destino = n.id "
        "WHERE r.tipo = 'usa' AND r.origen LIKE 'tec:coforge:%' AND n.tipo = 'modulo' "
        "ORDER BY n.id"
    ).fetchall()

    if not rows:
        sys.exit("[FALLO] no hay nodos fichero enlazados por tec→usa→fichero")

    head_plantilla = get_head(PLANTILLA_DIR)
    head_rag = get_head(REPO_RAG)

    if not args.dry_run:
        backup_registro(conn, db, "pre-commit-evidencia")

    insertados = 0
    existian = 0
    no_existe = 0

    for nodo_id, nombre in rows:
        if nodo_id.startswith("mod:plantilla:"):
            repo = PLANTILLA_DIR
            sha = head_plantilla
            path = nodo_id.replace("mod:plantilla:", "", 1)
        elif nodo_id.startswith("mod:vmi3211028:rag-banking-agent:"):
            repo = REPO_RAG
            sha = head_rag
            path = nodo_id.replace("mod:vmi3211028:rag-banking-agent:", "", 1)
        else:
            print(f"  [skip] {nodo_id}: prefijo no reconocido")
            continue

        if not file_exists_at_head(repo, path):
            print(f"  [miss] {nodo_id}: no existe en HEAD ({sha[:8]})")
            no_existe += 1
            continue

        if args.dry_run:
            print(f"  [dry-run] {nodo_id}: commit={sha[:12]}")
            insertados += 1
            continue

        rc = conn.execute(
            "INSERT OR IGNORE INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, evidencia, vigente) "
            "VALUES (?, 'commit', ?, 'observado', ?, ?, ?, ?, 1)",
            (nodo_id, sha, FUENTE, args.actor, ahora(), f"git cat-file -e HEAD:{path}"),
        ).rowcount
        if rc == 1:
            insertados += 1
            print(f"  [ok] {nodo_id}: commit={sha[:12]}")
        else:
            existian += 1

    if not args.dry_run and insertados > 0:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ahora(), args.actor, "commit_evidencia_cargado",
             f"{insertados} afirmaciones commit insertadas, {existian} existían, {no_existe} ficheros no en HEAD"),
        )
        conn.commit()

    conn.close()
    print(f"\nResultado: {insertados} insertadas, {existian} existían, {no_existe} no en HEAD")


if __name__ == "__main__":
    main()
