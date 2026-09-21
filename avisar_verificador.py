"""Registra aviso_verificador: la spec/entrega de un plan pasa a juicio de 07.

    python3 avisar_verificador.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-M6 --detalle "R1: comprobar_m6.py CUMPLE exit 0; tarea 70"
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
    ap.add_argument("--plan", required=True)
    ap.add_argument("--detalle", required=True)
    args = ap.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    backup_registro(conn, db, "pre-aviso-verificador")

    ts = ahora()
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
        "VALUES (?, ?, 'aviso_verificador', NULL, ?, ?)",
        (ts, ACTOR, args.plan, args.detalle),
    )
    conn.commit()
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[OK] aviso_verificador para {args.plan}")
    print(f"[evento] {eid}")
    conn.close()


if __name__ == "__main__":
    main()
