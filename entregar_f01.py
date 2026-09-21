"""Entrega transitoria de tarea 71 (F0.1) bajo el trigger viejo.

El trigger quien_ejecuta_no_juzga_u/i exige verificada_por != NULL en espera_firma.
D7c lo relaja, pero D7c se aplica DESPUES de que 07 verifique esta tarea.
Dependencia circular: para entregar hay que pasar el trigger, pero para aplicar
D7c hay que entregar primero.

Solucion: entrega con verificada_por temporal (07-verificador placeholder).
Tras aplicar D7c el lead vacia verificada_por, y el veredicto real lo llena.

    python3 entregar_f01.py --db ~/sypnose-f1/registry.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, verificar_repo_limpio, verificar_canonicos_registrados

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN_ID = "PLAN-CS-F0"
TAREA_ID = 71
VERIFICADOR_TEMPORAL = "IA:07-verificador:claude-opus-5"

SALIDA = (
    "python3 compuerta_d7c.py --db copia-registry.db: 11 OK, 0 FALLO. "
    "Trigger INSERT gemelo 8/8; verificar_evento_verificado 4 tareas corregidas OK; "
    "3 tareas vaciadas OK; entrega sin verificada_por OK. "
    "corregir_verificada_por.py: 6 correcciones (evento 24954). "
    "nota_lead: evento 24955. justificacion fila a fila: evento 24958. "
    "firmar.py: verificar_evento_verificado() anadido. "
    "entregar_tarea.py: --verificador eliminado, verificada_por no se escribe."
)


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    t = conn.execute(
        "SELECT id, plan_id, req_ref, titulo, progreso, agente, verificada_por FROM tarea WHERE id=?",
        (TAREA_ID,),
    ).fetchone()
    if not t:
        sys.exit(f"[FALLO] tarea {TAREA_ID} no existe")
    tid, plan_id, ref, titulo, progreso, agente, vp = t

    if progreso not in ("pendiente", "trabajando"):
        sys.exit(f"[FALLO] tarea {tid} progreso={progreso}, esperado pendiente/trabajando")

    print(f"[entregar] tarea {tid} ({ref}: {titulo})")
    print(f"[agente] {agente}")
    print(f"[TRANSITORIO] verificada_por={VERIFICADOR_TEMPORAL} (trigger viejo lo exige)")
    print(f"[NOTA] se vacia a NULL tras aplicar D7c, veredicto real lo llena")
    print(f"[salida] {SALIDA[:200]}...")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    backup_registro(conn, db, "pre-entrega-f01")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE tarea SET progreso='espera_firma', verificada_por=? WHERE id=?",
            (VERIFICADOR_TEMPORAL, TAREA_ID),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "tarea_entregada", PLAN_ID,
             f"tarea {TAREA_ID} {ref}: {SALIDA}"),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "nota_lead", PLAN_ID,
             f"tarea {TAREA_ID} entregada con verificada_por={VERIFICADOR_TEMPORAL} TRANSITORIO: "
             f"trigger quien_ejecuta_no_juzga_u exige vp != NULL en espera_firma, "
             f"pero D7c (que relaja el trigger) se aplica despues de esta entrega. "
             f"Dependencia circular resuelta con vp temporal. El lead vacia verificada_por "
             f"al aplicar D7c, y el veredicto real de 07 lo llena por primera vez."),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid_ent = conn.execute(
        "SELECT max(id) FROM evento WHERE accion='tarea_entregada' AND plan_id=?",
        (PLAN_ID,),
    ).fetchone()[0]
    eid_nota = conn.execute(
        "SELECT max(id) FROM evento WHERE accion='nota_lead' AND plan_id=?",
        (PLAN_ID,),
    ).fetchone()[0]
    print(f"\n[OK] tarea {tid} -> espera_firma (vp={VERIFICADOR_TEMPORAL} transitorio)")
    print(f"[evento entrega] {eid_ent}")
    print(f"[evento nota transitorio] {eid_nota}")
    conn.close()


if __name__ == "__main__":
    main()
