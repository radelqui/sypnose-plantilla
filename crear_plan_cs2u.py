"""Crea PLAN-CS2-U (interfaz real del agente como-estoy-hecho).

T04/T11 se firmaron sobre un placeholder (texto sin React ni fetch).
R0 spec (04), R1 interfaz React real (04). R1 bloqueada tras R0.

    python3 crear_plan_cs2u.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_sin_delete

ACTOR = "IA:08-caparazon:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_cs2u.py"

PLAN_ID = "PLAN-CS2-U"
SOL_ID = "sol:coforge:como-estoy-hecho"

REQUISITOS = [
    {
        "ref": "R0",
        "titulo": "Spec EARS: interfaz React real de como-estoy-hecho",
        "ears": (
            "Cuando se ejecute python -m pytest tests/como_estoy_hecho/test_ui.py -q, "
            "DEBE pasar: el HTML servido contiene 'react', 'fetch(' y '/api/v1/como-estoy-hecho', "
            "y el motor falso responde a través de la UI."
        ),
        "comprobacion": "python -m pytest tests/como_estoy_hecho/test_ui.py -q",
    },
    {
        "ref": "R1",
        "titulo": "Interfaz React real: CDN, X-Customer-Id, streaming, ficheros citados, responsive",
        "ears": (
            "Cuando se sirva la interfaz de como-estoy-hecho, "
            "DEBE cargar React/ReactDOM desde CDN, mostrar campo X-Customer-Id y textarea de pregunta, "
            "hacer fetch al POST /api/v1/como-estoy-hecho con lectura en streaming, "
            "renderizar la respuesta y los ficheros citados como enlaces, ser responsive, "
            "y el test DEBE comprobar en el HTML servido las cadenas 'react', 'fetch(' "
            "y '/api/v1/como-estoy-hecho' y que el motor falso responde a través de la UI."
        ),
        "comprobacion": "python -m pytest tests/como_estoy_hecho/test_ui.py -q",
    },
]

TAREAS = [
    {
        "req_ref": "R0",
        "titulo": "Spec EARS: interfaz React real de como-estoy-hecho (specs/CEH-UI/spec.md)",
        "agente": "IA:04-agentes:claude-sonnet-5",
    },
    {
        "req_ref": "R1",
        "titulo": "Interfaz React real: React/ReactDOM CDN, X-Customer-Id, textarea, fetch streaming, ficheros citados, responsive, test UI",
        "agente": "IA:04-agentes:claude-sonnet-5",
    },
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not args.dry_run:
        backup_registro(conn, db, "pre-cs2u")

    plan_exists = conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
    if not plan_exists:
        if not args.dry_run:
            conn.execute(
                "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
                "VALUES (?, 'mantener', "
                "'Interfaz real del agente como-estoy-hecho (reemplaza placeholder)', "
                "'Que la UI sirva React con fetch streaming al endpoint real', "
                "'T04/T11 se firmaron sobre un placeholder sin React ni fetch — 07 lo descubrió (23939-23942)', "
                "?, 'abierto', ?, 'H:carlos', '04-agentes/wt-ceh', ?)",
                (PLAN_ID, SOL_ID, ACTOR, ahora()),
            )
        print(f"  [plan] {PLAN_ID} creado (afecta={SOL_ID})")
    else:
        print(f"  [plan] {PLAN_ID} ya existe")

    for req in REQUISITOS:
        exists = conn.execute(
            "SELECT 1 FROM requisito WHERE plan_id=? AND ref=?",
            (PLAN_ID, req["ref"]),
        ).fetchone()
        if exists:
            print(f"  [req] {PLAN_ID}/{req['ref']} ya existe")
            continue
        if not args.dry_run:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (PLAN_ID, req["ref"], req["ears"], req["comprobacion"]),
            )
        print(f"  [req] {PLAN_ID}/{req['ref']} creado")

    tarea_ids = []
    for t in TAREAS:
        exists = conn.execute(
            "SELECT id FROM tarea WHERE plan_id=? AND req_ref=? AND progreso IN ('pendiente','trabajando','bloqueada')",
            (PLAN_ID, t["req_ref"]),
        ).fetchone()
        if exists:
            print(f"  [tarea] {PLAN_ID}/{t['req_ref']} ya existe (id={exists[0]})")
            tarea_ids.append(exists[0])
            continue
        if not args.dry_run:
            cur = conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (PLAN_ID, t["req_ref"], t["titulo"], "pendiente", t["agente"]),
            )
            tarea_ids.append(cur.lastrowid)
            print(f"  [tarea] {cur.lastrowid} creada: {PLAN_ID}/{t['req_ref']} -> {t['agente']}")
        else:
            print(f"  [dry-run] tarea: {PLAN_ID}/{t['req_ref']} -> {t['agente']}")

    # Block R1 behind R0
    if len(tarea_ids) == 2 and not args.dry_run:
        r0_id = tarea_ids[0]
        blocked_id = tarea_ids[1]
        prog = conn.execute("SELECT progreso FROM tarea WHERE id=?", (blocked_id,)).fetchone()
        if prog and prog[0] == "pendiente":
            conn.execute(
                "UPDATE tarea SET progreso='bloqueada', bloqueada_por=? WHERE id=?",
                (r0_id, blocked_id),
            )
            print(f"  [bloqueo] tarea {blocked_id} bloqueada tras {r0_id}")

    if not args.dry_run:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), ACTOR, "plan_creado", PLAN_ID,
             f"plan {PLAN_ID} afecta {SOL_ID}, "
             f"{len(REQUISITOS)} requisitos, {len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)}). "
             f"Motivado por hallazgo 07 (23939-23942): UI placeholder sin React ni fetch"),
        )
        conn.commit()

    conn.close()
    print(f"\n[OK] {PLAN_ID}: {len(REQUISITOS)} req, {len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)})")


if __name__ == "__main__":
    main()
