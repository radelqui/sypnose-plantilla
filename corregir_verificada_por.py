"""F0.1: corrige verificada_por contaminado en 7 tareas.

entregar_tarea.py precargaba verificada_por al entregar, antes de que existiera
ningun evento verificado. El informe de viabilidad JEV (21-sep, seccion 2.2)
lo demuestra con la tarea 70 y documenta las 7 filas afectadas.

Para cada tarea contaminada:
  - Si existe evento verificado con actor que coincide: corrige verificada_por
    al actor real del verificado.
  - Si no existe evento verificado: vacia verificada_por a NULL.
No toca evidencia ni evento (solo INSERT de eventos nuevos).

    python3 corregir_verificada_por.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/corregir_verificada_por.py"
PLAN_ID = "PLAN-CS-F0"

TAREAS_CONTAMINADAS = [70, 17, 41, 34, 38, 40, 44]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def buscar_verificado(conn, tarea_id):
    """Busca el ultimo evento verificado cuyo detalle menciona esta tarea."""
    row = conn.execute(
        "SELECT id, actor, cuando, detalle FROM evento "
        "WHERE accion='verificado' AND detalle LIKE ? "
        "ORDER BY id DESC LIMIT 1",
        (f"tarea {tarea_id} %",),
    ).fetchone()
    if row:
        return {"evento_id": row[0], "actor": row[1], "cuando": row[2], "detalle": row[3]}

    row = conn.execute(
        "SELECT id, actor, cuando, detalle FROM evento "
        "WHERE accion='verificado' AND detalle LIKE ? "
        "ORDER BY id DESC LIMIT 1",
        (f"%tarea {tarea_id}%",),
    ).fetchone()
    if row:
        return {"evento_id": row[0], "actor": row[1], "cuando": row[2], "detalle": row[3]}
    return None


def buscar_entrega(conn, tarea_id):
    """Busca el evento tarea_entregada para esta tarea."""
    row = conn.execute(
        "SELECT id, cuando FROM evento "
        "WHERE accion='tarea_entregada' AND detalle LIKE ? "
        "ORDER BY id DESC LIMIT 1",
        (f"tarea {tarea_id} %",),
    ).fetchone()
    if row:
        return {"evento_id": row[0], "cuando": row[1]}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    for tid in TAREAS_CONTAMINADAS:
        if not conn.execute("SELECT 1 FROM tarea WHERE id=?", (tid,)).fetchone():
            conn.close()
            sys.exit(f"[FALLO] tarea {tid} no existe")

    print(f"[inventario] {len(TAREAS_CONTAMINADAS)} tareas contaminadas")
    print()

    correcciones = []
    for tid in TAREAS_CONTAMINADAS:
        row = conn.execute(
            "SELECT id, plan_id, progreso, agente, verificada_por FROM tarea WHERE id=?",
            (tid,),
        ).fetchone()
        t_id, t_plan, t_prog, t_agente, t_vp = row
        entrega = buscar_entrega(conn, tid)
        verificado = buscar_verificado(conn, tid)

        print(f"  tarea {tid}: progreso={t_prog}, agente={t_agente}, verificada_por={t_vp}")
        if entrega:
            print(f"    entrega: evento {entrega['evento_id']} ({entrega['cuando']})")
        else:
            print(f"    entrega: NO HAY evento tarea_entregada")

        if verificado:
            print(f"    verificado: evento {verificado['evento_id']} por {verificado['actor']} ({verificado['cuando']})")
            if entrega and verificado["cuando"] > entrega["cuando"]:
                if verificado["actor"] != t_vp:
                    correcciones.append({
                        "tarea_id": tid,
                        "accion": "corregir",
                        "viejo": t_vp,
                        "nuevo": verificado["actor"],
                        "motivo": (
                            f"verificada_por apuntaba a {t_vp} (precargado por entregar_tarea.py), "
                            f"pero el verificado real es evento {verificado['evento_id']} por "
                            f"{verificado['actor']} posterior a la entrega"
                        ),
                    })
                    print(f"    -> CORREGIR: {t_vp} -> {verificado['actor']}")
                else:
                    print(f"    -> OK: verificada_por coincide con verificador real")
            elif entrega and verificado["cuando"] <= entrega["cuando"]:
                correcciones.append({
                    "tarea_id": tid,
                    "accion": "vaciar",
                    "viejo": t_vp,
                    "nuevo": None,
                    "motivo": (
                        f"verificada_por={t_vp} precargado por entregar_tarea.py; "
                        f"evento verificado {verificado['evento_id']} es ANTERIOR a la entrega "
                        f"(pertenece a otro ciclo)"
                    ),
                })
                print(f"    -> VACIAR: verificado anterior a entrega")
            else:
                correcciones.append({
                    "tarea_id": tid,
                    "accion": "vaciar",
                    "viejo": t_vp,
                    "nuevo": None,
                    "motivo": (
                        f"verificada_por={t_vp} precargado por entregar_tarea.py; "
                        f"sin evento entrega para comparar"
                    ),
                })
                print(f"    -> VACIAR: sin entrega para comparar")
        else:
            correcciones.append({
                "tarea_id": tid,
                "accion": "vaciar",
                "viejo": t_vp,
                "nuevo": None,
                "motivo": (
                    f"verificada_por={t_vp} precargado por entregar_tarea.py; "
                    f"NO existe evento verificado para esta tarea"
                ),
            })
            print(f"    -> VACIAR: sin evento verificado")
        print()

    if not correcciones:
        print("[OK] ninguna correccion necesaria")
        conn.close()
        return

    print(f"[resumen] {len(correcciones)} correcciones:")
    for c in correcciones:
        if c["accion"] == "corregir":
            print(f"  tarea {c['tarea_id']}: {c['viejo']} -> {c['nuevo']}")
        else:
            print(f"  tarea {c['tarea_id']}: {c['viejo']} -> NULL")

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    backup_registro(conn, db, "pre-correccion-verificada-por")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for c in correcciones:
            tid = c["tarea_id"]
            if c["accion"] == "corregir":
                conn.execute(
                    "UPDATE tarea SET verificada_por=? WHERE id=?",
                    (c["nuevo"], tid),
                )
            else:
                conn.execute(
                    "UPDATE tarea SET verificada_por=NULL WHERE id=?",
                    (tid,),
                )

        detalle_items = []
        for c in correcciones:
            if c["accion"] == "corregir":
                detalle_items.append(
                    f"tarea {c['tarea_id']}: {c['viejo']} -> {c['nuevo']}"
                )
            else:
                detalle_items.append(
                    f"tarea {c['tarea_id']}: {c['viejo']} -> NULL"
                )

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) "
            "VALUES (?, ?, 'correccion_verificada_por', ?, ?)",
            (ts, ACTOR, PLAN_ID,
             f"F0.1 D7: corregido verificada_por en {len(correcciones)} tareas contaminadas "
             f"por entregar_tarea.py que precargaba el verificador al entregar "
             f"(demostrado en informe viabilidad JEV seccion 2.2, tarea 70 como caso principal). "
             f"Correcciones: {'; '.join(detalle_items)}. "
             f"Sin UPDATE/DELETE sobre evidencia ni evento."),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"\n[OK] {len(correcciones)} tareas corregidas")
    print(f"[evento] {eid}")
    conn.close()


if __name__ == "__main__":
    main()
