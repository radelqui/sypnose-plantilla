"""Recalcula estado de verificación de una línea a partir de sus tareas y eventos.

Remate 5 de la auditoría de restauración: T06 y T09 muestran 'verificada/firmada'
en la portada pero tienen tareas devueltas con NO CUMPLE posterior a la firma.

    python3 calcular_certeza.py --db ~/sypnose-f1/registry.db [--dry-run]
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
APROBACION = "aprobado por 00-lead, auditoría de restauración 21-sep"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def recalcular_linea(conn, plan_id, linea_nodo, ts):
    """Recalcula el estado de verificación para una línea."""
    tareas = conn.execute(
        "SELECT id, req_ref, progreso, agente, verificada_por FROM tarea WHERE plan_id=?",
        (plan_id,),
    ).fetchall()
    if not tareas:
        print(f"  [SKIP] {plan_id}: sin tareas")
        return

    devueltas = [(t[0], t[1], t[3]) for t in tareas if t[2] == "devuelta"]
    hechas = [(t[0], t[1], t[3]) for t in tareas if t[2] == "hecha"]
    otras = [(t[0], t[1], t[2]) for t in tareas if t[2] not in ("hecha", "devuelta")]

    print(f"  {plan_id}: {len(hechas)} hecha, {len(devueltas)} devuelta, {len(otras)} otras")

    if not devueltas and not otras:
        print(f"  [SKIP] {plan_id}: todas las tareas hechas, nada que recalcular")
        return

    ultimo_no_cumple = conn.execute(
        "SELECT id, detalle FROM evento WHERE plan_id=? AND accion='verificado' "
        "AND detalle LIKE '%: NO CUMPLE%' ORDER BY id DESC LIMIT 1",
        (plan_id,),
    ).fetchone()

    ultimo_devuelta = conn.execute(
        "SELECT id, detalle FROM evento WHERE plan_id=? AND accion='tarea_devuelta' "
        "ORDER BY id DESC LIMIT 1",
        (plan_id,),
    ).fetchone()

    partes = []
    for tid, ref, agente in devueltas:
        partes.append(f"tarea {tid} ({ref}) devuelta")
    if ultimo_no_cumple:
        partes.append(f"último NO CUMPLE: evento {ultimo_no_cumple[0]}")
    if ultimo_devuelta:
        partes.append(f"última devolución: evento {ultimo_devuelta[0]}")
    for tid, ref, agente in hechas:
        partes.append(f"tarea {tid} ({ref}) hecha")

    estado_valor = "en revisión: " + "; ".join(partes)

    existing = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='estado_verificacion' AND vigente=1",
        (linea_nodo,),
    ).fetchone()

    if existing:
        if existing[1] == estado_valor:
            print(f"  [SKIP] {linea_nodo}: estado_verificacion ya actual")
            return
        conn.execute(
            "UPDATE afirmacion SET vigente=0 WHERE id=?", (existing[0],)
        )
        print(f"  [UPDATE] {linea_nodo}: anterior estado_verificacion (id {existing[0]}) → vigente=0")

    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (linea_nodo, "estado_verificacion", estado_valor, "observado",
         f"calcular_certeza.py, eventos {plan_id}", ACTOR, ts),
    )

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "certeza_recalculada", plan_id,
         f"Recalculado estado de {linea_nodo}: {estado_valor}. "
         f"Firmas históricas no tocadas. {APROBACION}."),
    )

    print(f"  [OK] {linea_nodo}: {estado_valor}")
    return True


def main():
    ap = argparse.ArgumentParser(description="Recalcular certeza de líneas con tareas devueltas")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-certeza")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        print("[REMATE 5] Recalcular certeza T06 y T09")
        recalcular_linea(conn, "PLAN-CS-T06", "linea:coforge:T06", ts)
        recalcular_linea(conn, "PLAN-CS-T09", "linea:coforge:T09", ts)

        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[dry-run] transaccion deshecha")
        else:
            conn.execute("COMMIT")
            last_ev = conn.execute("SELECT MAX(id) FROM evento").fetchone()[0]
            print(f"\n[OK] Certeza recalculada. último evento: {last_ev}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
