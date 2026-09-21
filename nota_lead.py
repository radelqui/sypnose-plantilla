"""Registra nota_lead: aparcamientos y deudas señalados a petición del lead.

Precedente: evento 24338 (nota_lead, actor 05, nodo/plan NULL). La nota es
del arquitecto que la escribe; el texto describe la deuda aparcada.

    python3 nota_lead.py --db ~/sypnose-f1/registry.db --detalle "..." [--plan PLAN-CS-M6]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--detalle", required=True)
    ap.add_argument("--plan", default=None)
    args = ap.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    backup_registro(conn, db, "pre-nota-lead")

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
        "VALUES (?, ?, 'nota_lead', NULL, ?, ?)",
        (ahora(), ACTOR, args.plan, args.detalle),
    )
    conn.commit()
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[OK] nota_lead registrada")
    print(f"[evento] {eid}")
    conn.close()


if __name__ == "__main__":
    main()
