"""Re-verifica una tarea cuyo verificada_por viola D7b (mismo rol).

Caso D7b: tarea con agente IA:07-verificador:* fue verificada por IA:07-verificador:*
(mismo rol, diferente modelo). La corrección asigna verificada_por = H:* (humano).

    python3 reverificar_tarea.py --db ~/sypnose-f1/registry.db \
        --tarea 14 --verificador H:carlos --plan PLAN-CS-T06 \
        --detalle "tarea 14 (R1): CUMPLE — verificación humana ..."
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import (
    backup_registro,
    verificar_canonicos_registrados,
    verificar_d7_auto_verificacion,
    verificar_d7_verificador,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-verifica tarea (corrección D7b)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--tarea", type=int, required=True)
    ap.add_argument("--verificador", required=True, help="nuevo verificador (H:carlos)")
    ap.add_argument("--plan", required=True, help="plan_id para el evento")
    ap.add_argument("--detalle", required=True, help="detalle del evento")
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
        "SELECT id, plan_id, agente, verificada_por, progreso FROM tarea WHERE id=?",
        (args.tarea,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {args.tarea} no existe")
    tid, plan_id, agente, verif_actual, progreso = row

    if plan_id != args.plan:
        sys.exit(f"[FALLO] tarea {tid} pertenece a {plan_id}, no a {args.plan}")

    if not (agente and agente.startswith("IA:07-verificador:") and verif_actual and verif_actual.startswith("IA:07-verificador:")):
        sys.exit(
            f"[FALLO] tarea {tid} no es caso D7b: agente={agente}, verificada_por={verif_actual}. "
            f"D7b solo aplica cuando ambos son IA:07-verificador:*"
        )

    verificar_d7_verificador(conn, args.verificador)
    verificar_d7_auto_verificacion(conn, args.tarea, args.verificador)

    print(f"[reverificar] tarea {tid}: verificada_por {verif_actual!r} → {args.verificador!r}")
    print(f"[motivo] D7b: mismo rol 07 no puede auto-verificarse")
    print(f"[progreso] {progreso} (sin cambio)")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "reverificar")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por=? WHERE id=?",
            (args.verificador, args.tarea),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, args.verificador, "verificado", args.plan, args.detalle),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {tid} verificada_por → {args.verificador}")


if __name__ == "__main__":
    main()
