"""Corrige fuente de afirmaciones spec que usan sha de plantilla sobre nodo rag.

Las afirmaciones descripcion:T01 y por_que:T01 tienen fuente
spec:specs/T01/spec.md@520f09e37e66 sobre sol:coforge:rag-banking-agent,
pero 520f09e es un commit de plantilla, no de rag-banking-agent.
Retira las viejas e inserta con fuente prefijada plantilla/ para que
la vista no lo enlace al repo equivocado.

    python3 corregir_fuente_spec_plantilla.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
OLD_FUENTE = "spec:specs/T01/spec.md@520f09e37e66"
NEW_FUENTE = "spec:plantilla/specs/T01/spec.md@520f09e37e66"


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

    rows = conn.execute(
        "SELECT id, nodo_id, campo, valor, certeza, actor_id "
        "FROM afirmacion WHERE fuente=? AND vigente=1",
        (OLD_FUENTE,),
    ).fetchall()

    if not rows:
        print("[OK] no hay afirmaciones con la fuente vieja")
        conn.close()
        return

    print(f"[afirmaciones a corregir] {len(rows)}:")
    for aid, nodo, campo, val, cert, actor in rows:
        print(f"  {aid}: {nodo} {campo} fuente={OLD_FUENTE}")

    if not args.dry_run:
        backup_registro(conn, db_path, "fuente-spec-plantilla")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        retired = 0
        inserted = 0

        for aid, nodo_id, campo, valor, certeza, actor_id in rows:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            retired += 1
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nodo_id, campo, valor, certeza, NEW_FUENTE, ACTOR, ts),
            )
            inserted += 1

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'fuente_spec_corregida', 'sol:coforge:rag-banking-agent', NULL, ?)",
            (ts, ACTOR,
             f"{retired} afirmaciones: fuente {OLD_FUENTE} → {NEW_FUENTE} "
             f"(520f09e es commit de plantilla, no de rag-banking-agent)"),
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
