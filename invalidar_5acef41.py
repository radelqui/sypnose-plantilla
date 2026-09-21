"""Invalida evidencias que citan el SHA 5acef41 (amend perdido) y las rehace con 7153f24.

El SHA 5acef41 fue un amend en rag-banking-agent que ya no existe en ningún repo público.
Su reemplazo en main es 7153f24 (verificado con gh api).

Camino legal: marcador INVALIDA:rowid:<n> + evento evidencia_invalidada por cada fila.
Luego inserta nuevas filas con el SHA corregido.

    python3 invalidar_5acef41.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/invalidar_5acef41.py"
SHA_VIEJO = "5acef41"
SHA_NUEVO = "7153f24"
SHA_NUEVO_LARGO = "7153f2467f1a99450f0c92def6f28cfffc28381e"


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
        "SELECT rowid, plan_id, nodo_id, fuente, dice FROM evidencia "
        "WHERE dice LIKE ? OR fuente LIKE ?",
        (f"%{SHA_VIEJO}%", f"%{SHA_VIEJO}%"),
    ).fetchall()

    if not rows:
        print("[OK] no hay evidencias con 5acef41")
        conn.close()
        return

    print(f"[invalidar] {len(rows)} evidencias citan {SHA_VIEJO}")
    for r in rows:
        print(f"  rowid={r[0]} plan={r[1]} fuente={r[3][:60]}")

    if args.dry_run:
        print("--dry-run: sin cambios")
        conn.close()
        return

    backup_registro(conn, db_path, "invalidar-5acef41")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        invalidadas = 0
        rehechas = 0

        for rowid, plan_id, nodo_id, fuente_orig, dice_orig in rows:
            marker_dice = f"INVALIDA:rowid:{rowid}"
            marker_fuente = FUENTE

            existing_marker = conn.execute(
                "SELECT 1 FROM evidencia WHERE plan_id=? AND fuente=? AND dice=?",
                (plan_id, marker_fuente, marker_dice),
            ).fetchone()
            if existing_marker:
                print(f"  [skip] marker ya existe para rowid={rowid}")
                continue

            conn.execute(
                "INSERT INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?, ?, ?, ?)",
                (plan_id, nodo_id, marker_fuente, marker_dice),
            )

            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'evidencia_invalidada', ?, ?, ?)",
                (ts, ACTOR, nodo_id, plan_id,
                 f"Evidencia rowid={rowid} invalidada: SHA {SHA_VIEJO} fue amend perdido, "
                 f"no existe en ningún repo público. Reemplazo: {SHA_NUEVO} (verificado con gh api). "
                 f"Fuente original: {fuente_orig[:80]}"),
            )
            invalidadas += 1

            dice_nuevo = dice_orig.replace(SHA_VIEJO, SHA_NUEVO)
            fuente_nueva = fuente_orig.replace(SHA_VIEJO, SHA_NUEVO)
            if dice_nuevo != dice_orig or fuente_nueva != fuente_orig:
                existing_new = conn.execute(
                    "SELECT 1 FROM evidencia WHERE plan_id=? AND fuente=? AND dice=?",
                    (plan_id, fuente_nueva, dice_nuevo),
                ).fetchone()
                if not existing_new:
                    conn.execute(
                        "INSERT INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?, ?, ?, ?)",
                        (plan_id, nodo_id, fuente_nueva, dice_nuevo),
                    )
                    rehechas += 1
                    print(f"  [rehecha] rowid={rowid} → fuente={fuente_nueva[:60]}")
                else:
                    print(f"  [skip] evidencia corregida ya existe para rowid={rowid}")

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {invalidadas} evidencias invalidadas, {rehechas} rehechas con {SHA_NUEVO}")
    conn.close()


if __name__ == "__main__":
    main()
