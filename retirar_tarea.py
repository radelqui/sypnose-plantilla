"""Retira una tarea cuyo plan fue rechazado o cuya línea está vacía por diseño.

Progreso → 'devuelta' (estado legal más cercano a 'retirada'; el CHECK de tarea
no admite 'retirada'). Evento tarea_retirada con motivo.

    python3 retirar_tarea.py --db ~/sypnose-f1/registry.db \
        --tarea 45 --motivo "plan PLAN-CS-T13 rechazado; línea T11 vacía por diseño"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Retira una tarea (progreso → devuelta)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--tarea", type=int, required=True)
    ap.add_argument("--motivo", required=True, help="motivo de la retirada")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute(
        "SELECT id, plan_id, req_ref, titulo, progreso, agente FROM tarea WHERE id=?",
        (args.tarea,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {args.tarea} no existe")
    tid, plan_id, ref, titulo, progreso, agente = row

    if progreso == "devuelta":
        print(f"[INFO] tarea {tid} ya está devuelta")
        conn.close()
        return
    if progreso == "hecha":
        sys.exit(f"[FALLO] tarea {tid} está hecha — retirar requiere decisión humana")

    print(f"[retirar] tarea {tid} ({ref}: {titulo}), progreso={progreso} → devuelta")
    print(f"[motivo] {args.motivo}")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "retirar-tarea")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tarea SET progreso='devuelta', verificada_por=NULL WHERE id=?",
            (args.tarea,),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_retirada", plan_id,
             f"tarea {tid} ({ref}: {titulo}) retirada (devuelta): {args.motivo}"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {tid} → devuelta (retirada: {args.motivo})")


if __name__ == "__main__":
    main()
