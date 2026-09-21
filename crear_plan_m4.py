"""Crea PLAN-CS-M4 (opciones del banco preparadas).

Fase 6: terraform y observabilidad del esqueleto.
R0 spec (arquitecto), R1 terraform (01), R2 observabilidad (02). R1/R2 bloqueadas tras R0.

    python3 crear_plan_m4.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:08-caparazon:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_m4.py"

PLAN_ID = "PLAN-CS-M4"
SOL_ID = "sol:coforge:rag-banking-agent"

REQUISITOS = [
    {
        "ref": "R0",
        "titulo": "Spec EARS: terraform y observabilidad del esqueleto",
        "ears": (
            "Cuando se ejecute python microservicio/comprobar_m4.py desde el worktree, "
            "DEBE pasar R1 (terraform/ existe con README y comprobar_terraform.py 3 passed) "
            "y R2 (X-Request-Id, log JSON, GET /metrics 200, tests)."
        ),
        "comprobacion": "python microservicio/comprobar_m4.py",
    },
    {
        "ref": "R1",
        "titulo": "terraform/ preparado en microservicio/esqueleto con README y comprobar_terraform.py",
        "ears": (
            "Cuando se ejecute comprobar_terraform.py, "
            "DEBE verificar que terraform/ contiene main.tf, variables.tf y README "
            "con instrucciones de despliegue en EKS/AKS."
        ),
        "comprobacion": "python microservicio/comprobar_terraform.py",
    },
    {
        "ref": "R2",
        "titulo": "Observabilidad mínima del esqueleto: X-Request-Id, log JSON, GET /metrics, tests",
        "ears": (
            "Cuando se ejecute pytest tests/test_observability.py, "
            "DEBE verificar que toda respuesta lleva X-Request-Id, "
            "que los logs son JSON estructurado y que GET /metrics devuelve 200."
        ),
        "comprobacion": "pytest tests/test_observability.py -q",
    },
]

TAREAS = [
    {
        "req_ref": "R0",
        "titulo": "Spec EARS: terraform y observabilidad del esqueleto",
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R1",
        "titulo": "terraform/ preparado en microservicio/esqueleto con README y comprobar_terraform.py",
        "agente": "IA:01-git-cicd:claude-sonnet-5",
    },
    {
        "req_ref": "R2",
        "titulo": "Observabilidad mínima del esqueleto: X-Request-Id, log JSON, GET /metrics, tests",
        "agente": "IA:02-backend-api:claude-sonnet-5",
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

    verificar_canonicos_registrados(conn)

    if not args.dry_run:
        backup_registro(conn, db, "pre-m4")

    plan_exists = conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
    if not plan_exists:
        if not args.dry_run:
            conn.execute(
                "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
                "VALUES (?, 'mantener', "
                "'Opciones del banco preparadas: terraform e instrumentación', "
                "'Tener el esqueleto listo para despliegue real en EKS/AKS con observabilidad', "
                "'El banco exige IaC y métricas desde el primer despliegue', "
                "?, 'abierto', ?, 'H:carlos', 'plantilla/wt-M4', ?)",
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

    # Block R1 and R2 behind R0
    if len(tarea_ids) == 3 and not args.dry_run:
        r0_id = tarea_ids[0]
        for blocked_id in tarea_ids[1:]:
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
             f"{len(REQUISITOS)} requisitos, {len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)})"),
        )
        conn.commit()

    conn.close()
    print(f"\n[OK] {PLAN_ID}: {len(REQUISITOS)} req, {len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)})")


if __name__ == "__main__":
    main()
