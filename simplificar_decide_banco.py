"""Simplifica decide_banco: flag booleano + texto solo cuando hay alternativas.

El lead pide: si es un flag, decide_banco_pendiente=true/false y el texto
solo cuando hay algo concreto. Las 16 entradas "N/A (...)" pasan a false
sin texto; las 25 con alternativas reales pasan a true con texto intacto.

    python3 simplificar_decide_banco.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/simplificar_decide_banco.py"


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
        "SELECT id, nodo_id, campo, valor, certeza FROM afirmacion "
        "WHERE campo='decide_banco' AND vigente=1 AND nodo_id LIKE 'tec:coforge:%'"
    ).fetchall()

    if not rows:
        print("[OK] no hay afirmaciones decide_banco vigentes")
        conn.close()
        return

    na_rows = [(r[0], r[1], r[3], r[4]) for r in rows if r[3].startswith("N/A")]
    real_rows = [(r[0], r[1], r[3], r[4]) for r in rows if not r[3].startswith("N/A")]

    print(f"[decide_banco] {len(rows)} totales: {len(na_rows)} N/A, {len(real_rows)} con alternativas reales")

    existing_flags = conn.execute(
        "SELECT nodo_id, valor FROM afirmacion WHERE campo='decide_banco_pendiente' AND vigente=1"
    ).fetchall()
    flag_map = {r[0]: r[1] for r in existing_flags}

    if not args.dry_run:
        backup_registro(conn, db_path, "simplificar-decide-banco")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        retired_text = 0
        new_flags = 0

        for aid, nodo_id, valor, certeza in na_rows:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            retired_text += 1
            if flag_map.get(nodo_id) != "false":
                if nodo_id in flag_map:
                    conn.execute(
                        "UPDATE afirmacion SET vigente=0 WHERE nodo_id=? AND campo='decide_banco_pendiente' AND vigente=1",
                        (nodo_id,),
                    )
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                    "VALUES (?, 'decide_banco_pendiente', 'false', ?, ?, ?, ?, 1)",
                    (nodo_id, certeza, FUENTE, ACTOR, ts),
                )
                new_flags += 1

        for aid, nodo_id, valor, certeza in real_rows:
            if flag_map.get(nodo_id) != "true":
                if nodo_id in flag_map:
                    conn.execute(
                        "UPDATE afirmacion SET vigente=0 WHERE nodo_id=? AND campo='decide_banco_pendiente' AND vigente=1",
                        (nodo_id,),
                    )
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                    "VALUES (?, 'decide_banco_pendiente', 'true', ?, ?, ?, ?, 1)",
                    (nodo_id, certeza, FUENTE, ACTOR, ts),
                )
                new_flags += 1

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'decide_banco_simplificado', NULL, NULL, ?)",
            (ts, ACTOR,
             f"decide_banco_pendiente: {new_flags} flags insertados; "
             f"{retired_text} textos N/A retirados (vigente=0); "
             f"{len(real_rows)} con alternativas reales conservan texto decide_banco"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {new_flags} flags decide_banco_pendiente, {retired_text} textos N/A retirados")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
