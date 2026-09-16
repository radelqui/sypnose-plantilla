"""Degrada estado de nodos que dicen implementado sin verificado_en.

mcp-sypnose, mcp-kb y kb-lecciones tienen estado=implementado pero
verificado_en vacío. Este script retira la afirmación implementado
(vigente=0) dejando declarado-sin-evidencia como estado vigente.

    python3 degradar_estado_sin_verificar.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
NODOS = [
    "tec:coforge:mcp-sypnose",
    "tec:coforge:mcp-kb",
    "tec:coforge:kb-lecciones",
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

    to_retire = []
    for nodo_id in NODOS:
        rows = conn.execute(
            "SELECT id, valor FROM afirmacion "
            "WHERE nodo_id=? AND campo='estado' AND valor='implementado' AND vigente=1",
            (nodo_id,),
        ).fetchall()
        verif = conn.execute(
            "SELECT valor FROM afirmacion "
            "WHERE nodo_id=? AND campo='verificado_en' AND vigente=1 AND valor != ''",
            (nodo_id,),
        ).fetchall()
        if rows and not verif:
            for aid, val in rows:
                to_retire.append((aid, nodo_id))
                print(f"  [retirar] afirmacion {aid}: {nodo_id} estado={val} (sin verificado_en)")
        elif not rows:
            print(f"  [skip] {nodo_id}: no tiene estado=implementado vigente")
        else:
            print(f"  [skip] {nodo_id}: tiene verificado_en, no degradar")

    if not to_retire:
        print("[OK] nada que degradar")
        conn.close()
        return

    print(f"\n{len(to_retire)} afirmaciones a retirar")

    if not args.dry_run:
        backup_registro(conn, db_path, "degradar-estado")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        retired = 0
        for aid, nodo_id in to_retire:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            retired += 1

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'estado_degradado', NULL, NULL, ?)",
            (ts, ACTOR,
             f"{retired} afirmaciones estado=implementado retiradas por verificado_en vacío: "
             + ", ".join(n for _, n in to_retire)
             + "; estado vigente queda declarado-sin-evidencia"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] retiradas: {retired}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
