"""Cierra o rechaza un plan abierto (abierto → cerrado/rechazado).

    python3 cerrar_plan.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T01 \
        --detalle "cerrado por 00-lead por delegación explícita de Carlos; línea firmada 22755"

    python3 cerrar_plan.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T13 --estado rechazado \
        --detalle "abierto por error; la línea T11 está vacía por diseño"
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
    ap = argparse.ArgumentParser(description="Cierra o rechaza un plan abierto")
    ap.add_argument("--db", required=True)
    ap.add_argument("--plan", required=True, help="plan_id, ej. PLAN-CS-T01")
    ap.add_argument("--estado", choices=("cerrado", "rechazado"), default="cerrado",
                    help="estado destino (por defecto cerrado)")
    ap.add_argument("--detalle", required=True, help="texto para el evento")
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
        "SELECT id, estado, dueno FROM plan WHERE id=?", (args.plan,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] plan {args.plan} no existe")
    pid, estado, dueno = row
    if estado == args.estado:
        print(f"[INFO] {pid} ya está {args.estado}")
        conn.close()
        return
    if estado != "abierto":
        sys.exit(f"[FALLO] {pid} estado={estado}, esperado abierto")

    pendientes = conn.execute(
        "SELECT COUNT(*) FROM tarea WHERE plan_id=? AND progreso NOT IN ('hecha','devuelta','retirada')",
        (args.plan,),
    ).fetchone()[0]
    if pendientes > 0:
        print(f"[WARN] {pid} tiene {pendientes} tareas no terminadas")

    if args.dry_run:
        print(f"[dry-run] {args.estado} {pid}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "cerrar-plan")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE plan SET estado=?, cerrado_en=? WHERE id=?",
            (args.estado, ts, args.plan),
        )
        accion = "plan_cerrado" if args.estado == "cerrado" else "plan_rechazado"
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, accion, args.plan, args.detalle),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {args.plan} {args.estado} a las {ts}")


if __name__ == "__main__":
    main()
