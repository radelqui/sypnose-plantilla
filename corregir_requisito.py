"""Corrige la comprobación de un requisito existente.

    python3 corregir_requisito.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-M5 --ref R1 \
        --comprobacion 'python microservicio/demo/comprobar_compose.py' \
        --motivo 'docker ausente en el PC de los chats; validación docker real en el 67'
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--comprobacion", required=True)
    ap.add_argument("--motivo", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    row = conn.execute(
        "SELECT comprobacion FROM requisito WHERE plan_id=? AND ref=?",
        (args.plan, args.ref),
    ).fetchone()
    if not row:
        print(f"[ERROR] requisito {args.plan}/{args.ref} no encontrado")
        raise SystemExit(1)

    old = row[0]
    if old == args.comprobacion:
        print(f"[skip] comprobación ya es: {old}")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "corregir-req")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        conn.execute(
            "UPDATE requisito SET comprobacion=? WHERE plan_id=? AND ref=?",
            (args.comprobacion, args.plan, args.ref),
        )
        print(f"  [update] {args.plan}/{args.ref}: {old!r} → {args.comprobacion!r}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'plan_corregido', NULL, ?, ?)",
            (ts, ACTOR, args.plan, f"{args.ref} comprobación cambiada: {args.motivo}"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {args.plan}/{args.ref} comprobación corregida")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
