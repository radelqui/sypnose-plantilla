"""F0.1 complemento: vaciar tarea 70 verificada_por + justificacion fila a fila.

Respuesta a revision del lead 21-sep:
- Tarea 70: verificada_por fue precargado por entregar_tarea.py aunque coincide
  con el verificador real (evento 24951). Bajo D7/F0.1, debe ser NULL hasta que
  el veredicto lo llene. Se vacia.
- Tabla fila a fila: para cada tarea contaminada, documenta el evento verificado
  (o su ausencia), la correccion aplicada y el estado actual.

    python3 corregir_t70_y_justificar.py --db ~/sypnose-f1/registry.db [--dry-run]
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

TAREAS_CONTAMINADAS = [17, 34, 38, 40, 41, 44, 70]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def buscar_entrega(conn, tid):
    row = conn.execute(
        "SELECT id, actor, cuando FROM evento WHERE accion='tarea_entregada' "
        "AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (f"tarea {tid} %",),
    ).fetchone()
    return row


def buscar_verificado(conn, tid):
    row = conn.execute(
        "SELECT id, actor, cuando FROM evento WHERE accion='verificado' "
        "AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (f"%tarea {tid}%",),
    ).fetchone()
    return row


def buscar_firma(conn, tid):
    row = conn.execute(
        "SELECT id, actor, cuando FROM evento WHERE accion='firma_tarea' "
        "AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (f"tarea {tid} %",),
    ).fetchone()
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    lineas = []
    lineas.append("JUSTIFICACION FILA A FILA — 7 tareas contaminadas por entregar_tarea.py")
    lineas.append("=" * 80)
    lineas.append(f"{'ID':>4} | {'Plan':<14} | {'Ref':<4} | {'Prog':<14} | {'vp actual':<35} | Evento verificado | Entrega | Firma | Accion F0.1")
    lineas.append("-" * 180)

    for tid in TAREAS_CONTAMINADAS:
        row = conn.execute(
            "SELECT id, plan_id, req_ref, progreso, agente, verificada_por FROM tarea WHERE id=?",
            (tid,),
        ).fetchone()
        if not row:
            lineas.append(f"  tarea {tid}: NO EXISTE")
            continue

        t_id, t_plan, t_ref, t_prog, t_agente, t_vp = row
        entrega = buscar_entrega(conn, tid)
        verificado = buscar_verificado(conn, tid)
        firma = buscar_firma(conn, tid)

        ev_str = f"ev {verificado[0]} por {verificado[1]} ({verificado[2][:19]})" if verificado else "NINGUNO"
        ent_str = f"ev {entrega[0]} ({entrega[2][:19]})" if entrega else "NINGUNA"
        fir_str = f"ev {firma[0]} por {firma[1]} ({firma[2][:19]})" if firma else "NINGUNA"

        posterior = ""
        if verificado and entrega:
            posterior = " POSTERIOR" if verificado[2] > entrega[2] else " ANTERIOR"

        if tid == 70:
            accion = "VACIAR vp (precargado aunque coincide; bajo D7/F0.1 debe ser NULL hasta veredicto nuevo)"
        elif t_vp and verificado and entrega and verificado[2] > entrega[2] and verificado[1] == t_vp:
            accion = f"OK corregido a {t_vp} (evento {verificado[0]} coincide)"
        elif t_vp is None and not verificado:
            accion = "VACIADO a NULL (sin evento verificado)"
        elif t_vp is None and verificado:
            accion = f"ANOMALIA: vp NULL pero hay verificado ev {verificado[0]}"
        else:
            accion = f"vp={t_vp}"

        lineas.append(
            f"{t_id:>4} | {t_plan:<14} | {t_ref:<4} | {t_prog:<14} | "
            f"{str(t_vp):<35} | {ev_str}{posterior} | {ent_str} | {fir_str} | {accion}"
        )

    lineas.append("")
    lineas.append("ANOMALIAS DETECTADAS:")
    lineas.append("- Tareas 17, 38, 41: hecha con verificada_por=NULL. Firmadas por H:carlos (delegacion lead)")
    lineas.append("  sin evento verificado previo. Son tareas del regimen antiguo (pre-F0.1).")
    lineas.append("  17 (T09/R1 Trazabilidad por commit): tarea de proceso, firmada por lead.")
    lineas.append("  38 (T06/R0 Definir req): meta-tarea de proceso, firmada por lead.")
    lineas.append("  41 (T09/R0 Definir req): meta-tarea de proceso, firmada por lead.")
    lineas.append("  Decision lead: retirar 38/41 si son duplicados; verificar 17 si tuvo veredicto T09.")
    lineas.append("- Tarea 70: verificada_por precargado (coincide con ev 24951) pero bajo F0.1 debe")
    lineas.append("  ser NULL hasta veredicto nuevo. Se vacia en esta correccion.")

    justificacion = "\n".join(lineas)
    print(justificacion)

    print("\n" + "=" * 80)
    print("CORRECCION: vaciar tarea 70 verificada_por")

    t70 = conn.execute(
        "SELECT verificada_por, progreso FROM tarea WHERE id=70"
    ).fetchone()
    if not t70:
        sys.exit("[FALLO] tarea 70 no existe")
    vp_actual = t70[0]
    if vp_actual is None:
        print("  tarea 70 verificada_por ya es NULL, sin cambios")
    else:
        print(f"  tarea 70 verificada_por actual: {vp_actual}")
        print(f"  -> sera vaciado a NULL")

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    if vp_actual is not None:
        backup_registro(conn, db, "pre-correccion-t70")

        ts = ahora()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=70")
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "correccion_verificada_por", PLAN_ID,
                 f"tarea 70: verificada_por={vp_actual} vaciado a NULL. "
                 f"Aunque coincide con el verificador real (evento 24951 de {vp_actual}), "
                 f"el valor fue precargado por entregar_tarea.py al entregar (informe viabilidad "
                 f"JEV §2.2). Bajo D7/F0.1 verificada_por debe ser NULL hasta que el verificador "
                 f"escriba su veredicto. Evento verificado 24951 sigue vigente como evidencia. "
                 f"Correccion solicitada por lead 21-sep."),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "nota_lead", PLAN_ID,
                 f"F0.1 justificacion fila a fila (7 tareas contaminadas): {justificacion[:1500]}"),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        eid1 = conn.execute("SELECT max(id) FROM evento WHERE accion='correccion_verificada_por'").fetchone()[0]
        eid2 = conn.execute("SELECT max(id) FROM evento WHERE accion='nota_lead' AND plan_id=?", (PLAN_ID,)).fetchone()[0]
        print(f"\n[OK] tarea 70 verificada_por -> NULL")
        print(f"[evento correccion] {eid1}")
        print(f"[evento justificacion] {eid2}")
    else:
        ts = ahora()
        backup_registro(conn, db, "pre-justificacion-t70")
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "nota_lead", PLAN_ID,
                 f"F0.1 justificacion fila a fila (7 tareas contaminadas): {justificacion[:1500]}"),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        eid = conn.execute("SELECT max(id) FROM evento WHERE accion='nota_lead' AND plan_id=?", (PLAN_ID,)).fetchone()[0]
        print(f"\n[evento justificacion] {eid}")

    conn.close()


if __name__ == "__main__":
    main()
