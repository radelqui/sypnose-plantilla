"""Crea y abre PLAN-CS-VISTA (vista pública, afecta sol plantilla).

Plan destino para los veredictos del segundo verificador sobre la vista,
separado de PLAN-CS-T01.

    python3 crear_plan_vista.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_vista.py"

PLAN_ID = "PLAN-CS-VISTA"
CLASE = "mantener"
QUE = "Vista pública"
PARA = "Recoger los veredictos del segundo verificador sobre la vista pública de la oferta"
PORQUE = "Los exámenes de la vista no deben colgar de PLAN-CS-T01 (línea 1); necesitan su propio plan sobre la plantilla"
AFECTA = "sol:coforge:sypnose-plantilla"
DUENO = "H:carlos"
WORKTREE = "plantilla/wt-VISTA"


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

    existing = conn.execute("SELECT id, estado FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
    if existing:
        print(f"[skip] {PLAN_ID} ya existe (estado={existing[1]})")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "plan-vista")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
            "VALUES (?, ?, ?, ?, ?, ?, 'abierto', ?, ?, ?, ?)",
            (PLAN_ID, CLASE, QUE, PARA, PORQUE, AFECTA, ACTOR, DUENO, WORKTREE, ts),
        )
        print(f"  [plan] {PLAN_ID} creado y abierto (afecta {AFECTA})")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'plan_creado_abierto', NULL, ?, ?)",
            (ts, ACTOR, PLAN_ID, f"PLAN-CS-VISTA: vista pública, afecta sol plantilla, para veredictos del segundo verificador"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {PLAN_ID} abierto")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
