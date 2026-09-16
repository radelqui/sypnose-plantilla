"""Convención de datos 2 (16-sep): plan.afecta = id del nodo solución.

Actualiza los 16 planes PLAN-CS-T01..T15 y PLAN-CS-M2 para que
plan.afecta = 'sol:coforge:rag-banking-agent'. Cada UPDATE genera
un evento plan_corregido. Solo INSERT de eventos; el UPDATE se limita
al campo afecta de la tabla plan.

    python3 actualizar_plan_afecta.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/actualizar_plan_afecta.py"
SOL_ID = "sol:coforge:rag-banking-agent"

PLANES = [f"PLAN-CS-T{n:02d}" for n in range(1, 16)] + ["PLAN-CS-M2"]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--actor", default=ACTOR)
    args = p.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not args.dry_run:
        backup_registro(conn, db, "pre-afecta")

    actualizados = 0
    ya_correctos = 0
    no_encontrados = []

    for plan_id in PLANES:
        row = conn.execute("SELECT afecta FROM plan WHERE id=?", (plan_id,)).fetchone()
        if row is None:
            no_encontrados.append(plan_id)
            continue

        afecta_actual = row[0]
        if afecta_actual == SOL_ID:
            ya_correctos += 1
            continue

        if args.dry_run:
            print(f"  [dry-run] {plan_id}: afecta '{afecta_actual}' → '{SOL_ID}'")
            actualizados += 1
            continue

        conn.execute("UPDATE plan SET afecta=? WHERE id=?", (SOL_ID, plan_id))
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), args.actor, "plan_corregido", plan_id,
             f"afecta actualizado: '{afecta_actual}' → '{SOL_ID}'"),
        )
        actualizados += 1
        print(f"  {plan_id}: afecta → {SOL_ID}")

    if not args.dry_run and actualizados > 0:
        conn.commit()

    conn.close()

    print(f"\nResultado: {actualizados} actualizados, {ya_correctos} ya correctos, {len(no_encontrados)} no encontrados")
    if no_encontrados:
        print(f"  No encontrados: {', '.join(no_encontrados)}")
    if actualizados == 0 and not no_encontrados:
        print("Nada que hacer.")


if __name__ == "__main__":
    main()
