"""F0.1: registrar justificacion fila a fila + nota sobre tarea 70.

Tarea 70 no se puede vaciar con el trigger actual (quien_ejecuta_no_juzga_u
rechaza NULL verificada_por en espera_firma). Se vacía DESPUÉS de que el lead
aplique D7c. Este script registra la justificacion como nota_lead.

    python3 justificar_y_nota.py --db ~/sypnose-f1/registry.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN_ID = "PLAN-CS-F0"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    justificacion = (
        "F0.1 JUSTIFICACION FILA A FILA — 7 tareas contaminadas por entregar_tarea.py\n"
        "Tarea 17 (T09/R1 Trazabilidad): hecha, vp=NULL (vaciado F0.1). Sin evento verificado. "
        "Firmada ev 23021 por H:carlos delegacion lead 15-sep. Meta-tarea T09 proceso.\n"
        "Tarea 34 (T02/R0 Definir req): hecha, vp=IA:07-verificador:claude-opus-4-6 (corregido F0.1). "
        "Evento verificado 23186 por 07-opus-4-6 posterior a entrega 23175. Coincide.\n"
        "Tarea 38 (T06/R0 Definir req): hecha, vp=NULL (vaciado F0.1). Sin evento verificado. "
        "Firmada ev 23022 por H:carlos delegacion lead 15-sep. Meta-tarea T06 proceso.\n"
        "Tarea 40 (T08/R0 Definir req): hecha, vp=IA:07-verificador:claude-opus-4-6 (corregido F0.1). "
        "Evento verificado 23188 por 07-opus-4-6 posterior a entrega 23173. Coincide.\n"
        "Tarea 41 (T09/R0 Definir req): hecha, vp=NULL (vaciado F0.1). Sin evento verificado. "
        "Firmada ev 23020 por H:carlos delegacion lead 15-sep. Meta-tarea T09 proceso.\n"
        "Tarea 44 (T12/R0 Definir req): hecha, vp=IA:07-verificador:claude-opus-4-6 (corregido F0.1). "
        "Evento verificado 23190 por 07-opus-4-6 posterior a entrega 23174. Coincide.\n"
        "Tarea 70 (M6/R1 Piezas): espera_firma, vp=IA:07-verificador:claude-opus-5 (PENDIENTE VACIAR). "
        "Evento verificado 24951 por 07-opus-5 posterior a entrega 24686. Coincide, pero vp fue "
        "precargado por entregar_tarea.py. Correccion BLOQUEADA: trigger quien_ejecuta_no_juzga_u "
        "rechaza NULL vp en espera_firma. Se vacia DESPUES de aplicar DDL D7c.\n"
        "ANOMALIAS: 17/38/41 hecha sin evento verificado (firmadas por lead pre-F0.1). "
        "Decision lead pendiente: retirar 38/41 si duplicados; verificar 17 si tuvo veredicto T09."
    )

    print(justificacion)

    backup_registro(conn, db, "pre-justificacion-f01")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "nota_lead", PLAN_ID, justificacion),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid = conn.execute("SELECT max(id) FROM evento WHERE accion='nota_lead' AND plan_id=?", (PLAN_ID,)).fetchone()[0]
    print(f"\n[OK] justificacion registrada como evento {eid}")
    print("[PENDIENTE] tarea 70 vp no se puede vaciar hasta que el lead aplique D7c DDL")
    conn.close()


if __name__ == "__main__":
    main()
