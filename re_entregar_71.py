"""Re-entrega tarea 71 (D7c v4) con commit de los 4 fixes + tests.

    python3 re_entregar_71.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, verificar_d7_entrega

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
TAREA_ID = 71
PLAN_ID = "PLAN-CS-F0"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(description="Re-entregar tarea 71")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    commit = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], text=True
    ).strip()
    commit_full = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_d7_entrega(conn, TAREA_ID, ACTOR)

    row = conn.execute(
        "SELECT progreso, agente, verificada_por FROM tarea WHERE id=?", (TAREA_ID,)
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {TAREA_ID} no existe")
    print(f"  tarea {TAREA_ID}: progreso={row[0]}, agente={row[1]}, vp={row[2]}")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-reentrega-71")

    ts = ahora()
    detalle = (
        f"tarea {TAREA_ID} R1 D7c v4 re-entrega: commit {commit_full[:12]}. "
        f"Arreglos de los 4 bugs del veredicto NO CUMPLE (ev 24977): "
        f"(1) trigger INSERT D7b auto-verificacion impide que rol 07 se auto-verifique, "
        f"(2) verificar_evento_verificado filtra por plan_id, "
        f"(3) LIKE anclado tarea N espacio evita 7 vs 71, "
        f"(4) NO CUMPLE anchored con ': NO CUMPLE' distingue veredicto de contadores. "
        f"Modo --aplicar con backup previo. comprobar_esquema.py exit 1 si hash difiere. "
        f"18 tests, 0 fallos sobre copia del vivo."
    )

    if args.dry_run:
        print(f"\n[dry-run] evento tarea_entregada:")
        print(f"  actor: {ACTOR}")
        print(f"  plan_id: {PLAN_ID}")
        print(f"  detalle: {detalle}")
        conn.close()
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_entregada", PLAN_ID, detalle),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\n[OK] tarea_entregada para tarea {TAREA_ID}, commit {commit}")


if __name__ == "__main__":
    main()
