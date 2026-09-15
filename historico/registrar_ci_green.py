"""Registra evidencia gh:run:34983669221 (CI green) para T07 y T14.

Pipeline main: test success, build-and-push (trivy) success, deploy WAITING.
Autorización lead (delegación Carlos): el techo lo sube un humano.

Guardia idempotente: evento 'ci_green_34983669221'.

    python3 historico/registrar_ci_green.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
EVENTO_GUARDIA = "ci_green_34983669221"
EVENTO_GUARDIA_INV = "ci_green_invalidar_old_run"
GH_RUN = "gh:run:34983669221"
GH_RUN_OLD = "gh:run:34870628891"
PLANES = ["PLAN-CS-T07", "PLAN-CS-T14"]
DICE = "CI main green: test success, build-and-push (trivy) success, deploy WAITING (aprobación humana)"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    ya = conn.execute("SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA,)).fetchone()
    ya_inv = conn.execute("SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA_INV,)).fetchone()
    if ya and ya_inv:
        print(f"[idempotente] eventos {EVENTO_GUARDIA} + {EVENTO_GUARDIA_INV} ya existen. 0 cambios.")
        conn.close()
        return

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    if args.dry_run:
        for p in PLANES:
            if not ya:
                print(f"[dry-run] INSERT evidencia {p}: {GH_RUN}")
            if not ya_inv:
                print(f"[dry-run] INVALIDA {p}: {GH_RUN_OLD}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "ci-green")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        insertados = 0
        if not ya:
            for plan_id in PLANES:
                rc = conn.execute(
                    "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?,?,?)",
                    (plan_id, GH_RUN, DICE),
                ).rowcount
                if rc == 1:
                    insertados += 1
                    print(f"  [+] {plan_id}: {GH_RUN}")
                else:
                    print(f"  [skip] {plan_id}: {GH_RUN} ya existe")
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
                (ts, ACTOR, EVENTO_GUARDIA,
                 f"{insertados} evidencias gh:run:34983669221 (T07, T14) — CI main green, deploy waiting"),
            )

        inv_count = 0
        if not ya_inv:
            for plan_id in PLANES:
                rc_inv = conn.execute(
                    "UPDATE evidencia SET fuente=? WHERE plan_id=? AND fuente=?",
                    (f"INVALIDA:{GH_RUN_OLD}", plan_id, GH_RUN_OLD),
                ).rowcount
                if rc_inv:
                    inv_count += rc_inv
                    print(f"  [inv] {plan_id}: {GH_RUN_OLD} → INVALIDA: (superseded)")
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
                (ts, ACTOR, EVENTO_GUARDIA_INV,
                 f"{inv_count} old run {GH_RUN_OLD} invalidated in T07/T14 — superseded by {GH_RUN}"),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {insertados} evidencias registradas")


if __name__ == "__main__":
    main()
