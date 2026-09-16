"""Entrega la tarea 52 (R0 spec M2) de PLAN-CS-M2.

    python3 entregar_spec_m2.py --db ~/sypnose-f1/registry.db

La spec ya está escrita y commiteada (specs/M2/spec.md, commit e33aef9).
Este script formaliza la entrega: pendiente → trabajando + evento tarea_entregada.
07 verificará y pondrá verificada_por + espera_firma (trigger D7 lo requiere).
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
TAREA_ID = 52


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Entregar tarea 52 (spec M2)")
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
        "SELECT id, plan_id, req_ref, progreso, agente FROM tarea WHERE id=?",
        (TAREA_ID,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {TAREA_ID} no existe")
    tid, plan_id, req_ref, progreso, agente = row

    if plan_id != PLAN_ID:
        sys.exit(f"[FALLO] tarea {tid} pertenece a {plan_id}, no a {PLAN_ID}")
    if agente != ACTOR:
        sys.exit(f"[FALLO] tarea {tid} agente={agente}, no soy yo ({ACTOR})")
    if progreso not in ("pendiente", "trabajando"):
        sys.exit(f"[FALLO] tarea {tid} progreso={progreso}, esperaba pendiente o trabajando")

    print(f"[tarea] {tid}: {req_ref} {progreso} → trabajando + entregada")
    print(f"[agente] {agente}")
    print(f"[spec] plantilla/specs/M2/spec.md (commit e33aef9)")
    print(f"[nota] espera_firma la pone 07 al verificar (trigger D7)")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "entregar-spec-m2")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if progreso == "pendiente":
            conn.execute(
                "UPDATE tarea SET progreso='trabajando' WHERE id=?", (TAREA_ID,),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "tarea_trabajando", PLAN_ID,
                 f"tarea {TAREA_ID} pendiente → trabajando"),
            )

        ts2 = ahora()
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts2, ACTOR, "tarea_entregada", PLAN_ID,
             f"tarea {TAREA_ID} R0: spec EARS en plantilla/specs/M2/spec.md "
             f"(commit e33aef9); R0 instanciar genera repo con make test en verde, "
             f"R1 0 ficheros fuera del dominio"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {TAREA_ID} → trabajando + tarea_entregada (07 verificará)")


if __name__ == "__main__":
    main()
