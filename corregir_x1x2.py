"""Correcciones X1/X2 del 07-verificador (TRASPASO-4).

5 correcciones en orden:
1) Planes PLAN-T-01..12 → objetivo sol:coforge, prefijo [coforge-santander], plantilla_origen, plan_linea en solución
2) (raiz.py se reescribe aparte)
3) (raiz.py se reescribe aparte)
4) retirar: vitalidad='inactivo_por_diseno' + afirmación estado_raiz='derogada' (se corrige en raiz.py)
5) T04/T11 cubre → certeza='propuesto' + evento 'creada_por_error'; ancla errónea → evento + ancla correcta

    python3 corregir_x1x2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/corregir_x1x2.py"
SOL_ID = "sol:coforge:rag-banking-agent"
PLANTILLA_ID = "plantilla:microservicio-ia"
COL_MOLDE = "plantilla-microservicio-ia"
COL_COFORGE = "coforge-santander"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-correccion.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    cambios = []

    try:
        # ─── CORRECCIÓN 1: planes al lado de la solución ───
        planes = conn.execute(
            "SELECT plan_id FROM plan_objetivo WHERE plan_id LIKE 'PLAN-T-%' AND nodo_id=?",
            (PLANTILLA_ID,),
        ).fetchall()
        print(f"[1] {len(planes)} planes PLAN-T apuntan a plantilla. Redirigiendo a solución...")

        for (pid,) in planes:
            conn.execute(
                "UPDATE plan_objetivo SET nodo_id=? WHERE plan_id=? AND nodo_id=?",
                (SOL_ID, pid, PLANTILLA_ID),
            )
            evento(conn, ACTOR, "plan_objetivo_redirigido",
                   f"{pid}: {PLANTILLA_ID} → {SOL_ID}", nodo_id=SOL_ID, plan_id=pid)
            cambios.append(f"plan_objetivo {pid} → {SOL_ID}")

        # Prefijo [coforge-santander] en plan.que
        planes_que = conn.execute(
            "SELECT id, que FROM plan WHERE id LIKE 'PLAN-T-%' AND que LIKE '[plantilla-microservicio-ia]%'"
        ).fetchall()
        for pid, que in planes_que:
            nuevo_que = que.replace("[plantilla-microservicio-ia]", f"[{COL_COFORGE}]", 1)
            conn.execute("UPDATE plan SET que=? WHERE id=?", (nuevo_que, pid))
            cambios.append(f"plan.que {pid}: prefijo → [{COL_COFORGE}]")
        if planes_que:
            evento(conn, ACTOR, "planes_prefijo_actualizado",
                   f"{len(planes_que)} planes: prefijo que → [{COL_COFORGE}]", nodo_id=SOL_ID)

        # plantilla_origen como afirmación en la solución (una sola, aplica a todos)
        ya = conn.execute(
            "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='plantilla_origen' AND vigente=1",
            (SOL_ID,),
        ).fetchone()
        if not ya:
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (SOL_ID, "plantilla_origen", COL_MOLDE, "observado", FUENTE, ACTOR, ahora()),
            )
            evento(conn, ACTOR, "afirmacion_creada",
                   f"plantilla_origen = {COL_MOLDE}", nodo_id=SOL_ID)
            cambios.append(f"afirmacion plantilla_origen en {SOL_ID}")

        # plan_linea: invalidar las del nodo plantilla, crear nuevas en solución
        old_pl = conn.execute(
            "SELECT id, campo, valor FROM afirmacion WHERE nodo_id=? AND campo LIKE 'plan_linea:%' AND vigente=1",
            (PLANTILLA_ID,),
        ).fetchall()
        print(f"[1] {len(old_pl)} afirmaciones plan_linea en plantilla → mover a solución")
        for aid, campo, valor in old_pl:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (SOL_ID, campo, valor, "observado", FUENTE, ACTOR, ahora()),
            )
            cambios.append(f"plan_linea {campo} → {SOL_ID}")
        if old_pl:
            evento(conn, ACTOR, "plan_linea_trasladada",
                   f"{len(old_pl)} plan_linea de {PLANTILLA_ID} → {SOL_ID}", nodo_id=SOL_ID)

        # plantilla_origen por plan (afirmación en la solución, campo plantilla_origen:PLAN-T-XX)
        for (pid,) in planes:
            ya_po = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                (SOL_ID, f"plantilla_origen:{pid}"),
            ).fetchone()
            if not ya_po:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                    (SOL_ID, f"plantilla_origen:{pid}", COL_MOLDE, "observado", FUENTE, ACTOR, ahora()),
                )
                cambios.append(f"plantilla_origen:{pid} en {SOL_ID}")

        # ─── CORRECCIÓN 5: T04/T11 cubre → propuesto + evento; ancla errónea ───
        errores_cubre = [("linea:coforge:T04", "no hay frontend/QA en la solución"),
                         ("linea:coforge:T11", "no hay frontend React/TS en la solución")]
        for destino, motivo in errores_cubre:
            rc = conn.execute(
                "UPDATE relacion SET certeza='propuesto' WHERE origen=? AND destino=? AND tipo='cubre' AND certeza!='propuesto'",
                (SOL_ID, destino),
            ).rowcount
            if rc:
                evento(conn, ACTOR, "creada_por_error",
                       f"cubre {SOL_ID}→{destino} marcada propuesto: {motivo}", nodo_id=SOL_ID)
                cambios.append(f"cubre→{destino} → certeza=propuesto")

        # Ancla errónea: sol en colección del molde. Crear ancla correcta en coforge-santander.
        ancla_ok = conn.execute(
            "SELECT 1 FROM ancla WHERE coleccion_id=? AND nodo_id=?", (COL_COFORGE, SOL_ID)
        ).fetchone()
        if not ancla_ok:
            conn.execute(
                "INSERT INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)", (COL_COFORGE, SOL_ID)
            )
            evento(conn, ACTOR, "ancla_creada",
                   f"ancla correcta: {COL_COFORGE} → {SOL_ID}", nodo_id=SOL_ID)
            cambios.append(f"ancla {COL_COFORGE} → {SOL_ID}")

        # Registrar evento sobre ancla errónea (no se puede borrar sin OK Carlos)
        evento(conn, ACTOR, "creada_por_error",
               f"ancla {COL_MOLDE}→{SOL_ID} es error (solución no pertenece al molde); pendiente OK Carlos para borrar",
               nodo_id=SOL_ID)
        cambios.append(f"evento: ancla errónea {COL_MOLDE}→{SOL_ID} documentada")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[resumen] {len(cambios)} cambios:")
    for c in cambios:
        print(f"  + {c}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")

    # Verificación post-commit
    if not args.dry_run:
        print("\n[verificación]")
        r = conn.execute("SELECT nodo_id FROM plan_objetivo WHERE plan_id='PLAN-T-01'").fetchone()
        print(f"  plan_objetivo PLAN-T-01 → {r[0] if r else 'NO EXISTE'}")
        r = conn.execute("SELECT que FROM plan WHERE id='PLAN-T-01'").fetchone()
        print(f"  plan.que PLAN-T-01 → {r[0][:80] if r else 'N/A'}")
        c = conn.execute(
            "SELECT COUNT(*) FROM afirmacion WHERE nodo_id=? AND campo LIKE 'plan_linea:%' AND vigente=1",
            (SOL_ID,),
        ).fetchone()[0]
        print(f"  plan_linea vigentes en solución: {c}")
        c2 = conn.execute(
            "SELECT COUNT(*) FROM afirmacion WHERE nodo_id=? AND campo LIKE 'plan_linea:%' AND vigente=1",
            (PLANTILLA_ID,),
        ).fetchone()[0]
        print(f"  plan_linea vigentes en plantilla: {c2} (debe ser 0)")
        r = conn.execute(
            "SELECT certeza FROM relacion WHERE origen=? AND destino='linea:coforge:T04' AND tipo='cubre'",
            (SOL_ID,),
        ).fetchone()
        print(f"  cubre→T04 certeza: {r[0] if r else 'no existe'}")
        r = conn.execute(
            "SELECT certeza FROM relacion WHERE origen=? AND destino='linea:coforge:T11' AND tipo='cubre'",
            (SOL_ID,),
        ).fetchone()
        print(f"  cubre→T11 certeza: {r[0] if r else 'no existe'}")
        r = conn.execute("SELECT coleccion_id FROM ancla WHERE nodo_id=?", (SOL_ID,)).fetchall()
        print(f"  anclas de solución: {[c[0] for c in r]}")

    conn.close()


if __name__ == "__main__":
    main()
