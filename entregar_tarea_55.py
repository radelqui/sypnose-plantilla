"""Entrega la tarea 55 (instanciar_microservicio.py + comprobar_esqueleto.py).

    python3 entregar_tarea_55.py --db ~/sypnose-f1/registry.db

Registra tarea_entregada con los commits relevantes.
07 verificará y pondrá verificada_por + espera_firma (trigger D7).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN_ID = "PLAN-CS-M2"
TAREA_ID = 55


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Entregar tarea 55")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute(
        "SELECT id, plan_id, progreso, agente FROM tarea WHERE id=?",
        (TAREA_ID,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {TAREA_ID} no existe")
    tid, plan_id, progreso, agente = row

    if plan_id != PLAN_ID:
        sys.exit(f"[FALLO] tarea {tid} pertenece a {plan_id}, no a {PLAN_ID}")
    if agente != ACTOR:
        sys.exit(f"[FALLO] tarea {tid} agente={agente}, no soy yo ({ACTOR})")
    if progreso != "trabajando":
        sys.exit(f"[FALLO] tarea {tid} progreso={progreso}, esperaba trabajando")

    print(f"[tarea] {tid}: progreso={progreso}")
    print(f"[agente] {agente}")
    print(f"[entregable] microservicio/instanciar_microservicio.py (commit 9033432)")
    print(f"[entregable] microservicio/comprobar_esqueleto.py (commit 4646eca)")
    print(f"[comprobación] python microservicio/comprobar_esqueleto.py")
    print(f"[nota] espera_firma la pone 07 al verificar (trigger D7)")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "entregar-t55")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_entregada", PLAN_ID,
             f"tarea {TAREA_ID} R1: microservicio/instanciar_microservicio.py (9033432) + "
             f"microservicio/comprobar_esqueleto.py (4646eca); "
             f"comprobación: python microservicio/comprobar_esqueleto.py"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {TAREA_ID} → tarea_entregada (07 verificará)")


if __name__ == "__main__":
    main()
