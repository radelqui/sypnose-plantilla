"""Entrega una tarea sin caparazon (pendiente/trabajando -> espera_firma).

Registra evento tarea_entregada con la salida de la comprobacion y
progreso=espera_firma. NO escribe verificada_por: D7 exige que ese campo
quede vacio hasta el veredicto real de 07 (informe viabilidad JEV, seccion
2.2; correccion F0.1 PLAN-CS-F0).

    python3 entregar_tarea.py --db ~/sypnose-f1/registry.db \
        --tarea 17 \
        --salida "plantilla: 97 commits, 4 chats distintos\\nCUMPLE"
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
    verificar_d7_entrega,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Entrega tarea sin caparazon")
    ap.add_argument("--db", required=True)
    ap.add_argument("--tarea", type=int, required=True)
    ap.add_argument("--salida", required=True, help="salida real de la comprobacion")
    ap.add_argument("--agente-real", help="corregir agente si difiere del asignado en el molde")
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

    t = conn.execute(
        "SELECT id, plan_id, req_ref, titulo, progreso, agente, verificada_por FROM tarea WHERE id=?",
        (args.tarea,),
    ).fetchone()
    if not t:
        sys.exit(f"[FALLO] tarea {args.tarea} no existe")
    tid, plan_id, ref, titulo, progreso, agente, ver_actual = t

    if progreso not in ("pendiente", "trabajando"):
        sys.exit(f"[FALLO] tarea {tid} progreso={progreso}, esperado pendiente/trabajando")

    agente_final = args.agente_real if args.agente_real else agente

    verificar_d7_entrega(conn, tid, ACTOR)

    if args.agente_real:
        ag = conn.execute("SELECT id FROM actor WHERE id=?", (args.agente_real,)).fetchone()
        if not ag:
            sys.exit(f"[FALLO] agente-real {args.agente_real} no existe como actor")

    print(f"[entregar] tarea {tid} ({ref}: {titulo})")
    print(f"[agente] {agente_final}{' (corregido de ' + agente + ')' if args.agente_real else ''}")
    print(f"[verificada_por] se deja vacio hasta veredicto real de 07 (D7/F0.1)")
    print(f"[salida] {args.salida[:200]}")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    bk = backup_registro(conn, db_path, "entregar")
    print(f"[backup] {bk}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if args.agente_real:
            conn.execute("UPDATE tarea SET agente=? WHERE id=?", (args.agente_real, tid))

        conn.execute(
            "UPDATE tarea SET progreso='espera_firma' WHERE id=?",
            (tid,),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_entregada", plan_id,
             f"tarea {tid} {ref}: {args.salida[:500]}"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {tid} -> espera_firma (verificada_por queda vacio)")


if __name__ == "__main__":
    main()
