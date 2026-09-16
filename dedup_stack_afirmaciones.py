"""Marca vigente=0 las afirmaciones duplicadas del stack tecnológico.

cargar_stack.py se ejecutó 6 veces sin check de idempotencia, creando 6 copias
de cada afirmación por (nodo_id, campo, valor). Este script conserva la más
reciente (MAX(id)) de cada grupo y retira las demás con vigente=0.

    python3 dedup_stack_afirmaciones.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
CAMPOS_STACK = ("para_que", "por_que", "grupo", "estado", "decide_banco",
                "que_cambia", "equipo", "hecho_por", "verificado_en")


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

    placeholders = ",".join("?" for _ in CAMPOS_STACK)
    dupes = conn.execute(f"""
        SELECT nodo_id, campo, valor, COUNT(*) c, MAX(id) keep_id
        FROM afirmacion
        WHERE vigente = 1
          AND campo IN ({placeholders})
          AND nodo_id LIKE 'tec:coforge:%'
        GROUP BY nodo_id, campo, valor
        HAVING c > 1
    """, CAMPOS_STACK).fetchall()

    if not dupes:
        print("[OK] no hay duplicados en afirmaciones del stack")
        conn.close()
        return

    total_retire = sum(row[3] - 1 for row in dupes)
    print(f"[dedup] {len(dupes)} grupos con duplicados, {total_retire} filas a retirar")

    if not args.dry_run:
        backup_registro(conn, db_path, "dedup-stack")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        retired = 0
        for nodo_id, campo, valor, count, keep_id in dupes:
            ids_to_retire = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo=? AND valor=? AND vigente=1 AND id!=?",
                (nodo_id, campo, valor, keep_id),
            ).fetchall()
            for (aid,) in ids_to_retire:
                conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
                retired += 1

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'dedup_afirmaciones', NULL, NULL, ?)",
            (ts, ACTOR,
             f"Retiradas {retired} afirmaciones duplicadas del stack (6 ejecuciones de cargar_stack.py "
             f"sin idempotencia); conservada la más reciente de cada (nodo_id, campo, valor)"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {retired} afirmaciones retiradas (vigente=0)")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
