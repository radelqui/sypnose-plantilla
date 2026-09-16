"""Crea PLAN-CS2-M (como-estoy-hecho) con sol, requisitos y tareas.

Sprint 16-sep: plan único con tres tareas (60 spec, 61 dominio, 62 medición).
Nodo solución sol:coforge:como-estoy-hecho con relaciones cubre.

    python3 crear_plan_cs2m.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_cs2m.py"
AMBITO = "vmi3211028"

PLAN_ID = "PLAN-CS2-M"
SOL_ID = "sol:coforge:como-estoy-hecho"

LINEAS_CUBRE = ["T02", "T03", "T04", "T11", "T12", "T13", "T14", "T15"]

REQUISITOS = [
    {
        "ref": "R0",
        "titulo": "Spec EARS: R2 diff=0, R3 health motor falso, R3 UI react+viewport",
        "ears": (
            "Cuando se ejecute python microservicio/comprobar_segundo.py desde el worktree, "
            "DEBE pasar R2 (diff esqueleto=0) y R3 (GET /health 200 con motor falso, "
            "GET /como-estoy-hecho/ui 200 con 'react' y 'viewport')."
        ),
        "comprobacion": "python microservicio/comprobar_segundo.py",
    },
    {
        "ref": "R1",
        "titulo": "Endpoint POST /api/v1/como-estoy-hecho con motor falso, X-Customer-Id y máscara PII",
        "ears": (
            "Cuando POST /api/v1/como-estoy-hecho reciba una pregunta con X-Customer-Id, "
            "DEBE responder leyendo /oferta de SYPNOSE con motor falso; "
            "sin X-Customer-Id DEBE devolver 401; datos PII DEBEN estar enmascarados."
        ),
        "comprobacion": "pytest tests/como_estoy_hecho/ -q",
    },
    {
        "ref": "R2",
        "titulo": "Medición: diff fuera de app/como_estoy_hecho y tests/como_estoy_hecho = 0",
        "ears": (
            "Cuando se compare el repo con tag esqueleto-v1, "
            "DEBE haber diff=0 fuera de app/como_estoy_hecho/ y tests/como_estoy_hecho/."
        ),
        "comprobacion": "git diff esqueleto-v1..HEAD -- . ':!app/como_estoy_hecho' ':!tests/como_estoy_hecho' | wc -l",
    },
]

TAREAS = [
    {
        "req_ref": "R0",
        "titulo": "Spec EARS con comprobación literal única",
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R1",
        "titulo": "Endpoint POST /api/v1/como-estoy-hecho con motor falso y tests",
        "agente": "IA:04-agentes:claude-sonnet-5",
    },
    {
        "req_ref": "R2",
        "titulo": "Medición: diff fuera de dominio = 0",
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
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
        backup_registro(conn, db, "pre-cs2m")

    # 1. Solution node
    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone():
        if not args.dry_run:
            conn.execute(
                "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, vitalidad, descubierto_en, descubierto_por) "
                "VALUES (?, 'solucion', 'como-estoy-hecho (Coforge/Santander)', NULL, ?, 'activo', ?, ?)",
                (SOL_ID, AMBITO, ahora(), FUENTE),
            )
        print(f"  [nodo] {SOL_ID} creado")
    else:
        print(f"  [nodo] {SOL_ID} ya existe")

    # 2. Relaciones cubre
    rel_count = 0
    for lid in LINEAS_CUBRE:
        linea_id = f"linea:coforge:{lid}"
        if not args.dry_run:
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', 'propuesto', ?, ?)",
                (SOL_ID, linea_id, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                rel_count += 1
        else:
            print(f"  [dry-run] cubre {SOL_ID} → {linea_id}")
            rel_count += 1
    print(f"  [relaciones] {rel_count} cubre creadas")

    # 3. Plan
    plan_exists = conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
    if not plan_exists:
        if not args.dry_run:
            conn.execute(
                "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
                "VALUES (?, 'mantener', "
                "'Microservicio público como-estoy-hecho que expone /oferta de SYPNOSE', "
                "'Demostrar que la plantilla instancia un segundo servicio funcional', "
                "'Validar reutilización del esqueleto y cubrir T04/T11 con UI React mínima', "
                "?, 'abierto', ?, 'H:carlos', '10-como-estoy-hecho/wt', ?)",
                (SOL_ID, ACTOR, ahora()),
            )
        print(f"  [plan] {PLAN_ID} creado (afecta={SOL_ID})")
    else:
        print(f"  [plan] {PLAN_ID} ya existe")

    # 4. Requisitos
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

    # 5. Tareas
    tarea_ids = []
    for t in TAREAS:
        exists = conn.execute(
            "SELECT id FROM tarea WHERE plan_id=? AND req_ref=? AND progreso IN ('pendiente','trabajando')",
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
            print(f"  [tarea] {cur.lastrowid} creada: {PLAN_ID}/{t['req_ref']} → {t['agente']}")
        else:
            print(f"  [dry-run] tarea: {PLAN_ID}/{t['req_ref']} → {t['agente']}")

    # 6. Evento resumen
    if not args.dry_run:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), ACTOR, "plan_creado", PLAN_ID,
             f"plan {PLAN_ID} con sol {SOL_ID}, {rel_count} cubre, "
             f"{len(REQUISITOS)} requisitos, {len(TAREAS)} tareas ({','.join(str(t) for t in tarea_ids)})"),
        )
        conn.commit()

    conn.close()
    print(f"\n[OK] {PLAN_ID}: {rel_count} cubre, {len(REQUISITOS)} req, {len(TAREAS)} tareas")


if __name__ == "__main__":
    main()
