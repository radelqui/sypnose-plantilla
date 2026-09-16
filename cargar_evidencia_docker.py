"""Carga evidencia de validación docker compose en el 67 para tarea 63.

    python3 cargar_evidencia_docker.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN = "PLAN-CS-M5"


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
        backup_registro(conn, db_path, "evidencia-docker")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        fuente = "prueba_docker_67"
        dice = (
            "docker compose -f microservicio/demo/docker-compose.demo.yml config --quiet → exit 0 "
            "(YAML válido, servicios: rag-api, rag-db, como-estoy-hecho). "
            "Demo viva en el 67: RAG en :8080 (docker, healthy), CEH en :8010 (python). "
            "curl localhost:8080/api/v1/health/live → {\"status\":\"alive\"}. "
            "Comprobación R1 corregida a python microservicio/demo/comprobar_compose.py "
            "(docker ausente en PC chats). Commit cb6b5fc."
        )

        rc = conn.execute(
            "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?, ?, ?)",
            (PLAN, fuente, dice),
        ).rowcount
        if rc:
            print(f"  [evidencia] {fuente}: {dice[:80]}...")
        else:
            print(f"  [skip] evidencia {fuente} ya existe")

        if rc:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'evidencia_docker_67', NULL, ?, ?)",
                (ts, ACTOR, PLAN, f"docker compose config exit 0 en /tmp/t63-compose@cb6b5fc; demo viva RAG:8080+CEH:8010"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] evidencia {'cargada' if rc else 'ya existía'}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
