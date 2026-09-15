"""Crea una tarea en el registro SYPNOSE con barrera y backup.

Validaciones: plan abierto, requisito existe, agente en actor con rol correcto
(roles_por_linea), idempotencia (no duplica pendiente/trabajando), aviso si
hay tareas en espera_firma/hecha para el mismo req_ref.

    python3 crear_tarea.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T01 --ref R1 \
        --titulo "Ejecutar la comprobación de R1 y entregar por el caparazón" \
        --agente IA:02-backend-api:claude-sonnet-5
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Crea tarea en el registro")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--plan", required=True, help="plan_id, ej. PLAN-CS-T01")
    ap.add_argument("--ref", required=True, help="req_ref, ej. R1")
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--agente", required=True, help="agente asignado (debe existir en actor)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    # 1. Plan debe estar abierto
    plan_row = conn.execute(
        "SELECT estado FROM plan WHERE id=?", (args.plan,),
    ).fetchone()
    if not plan_row:
        sys.exit(f"[FALLO] plan {args.plan} no existe")
    if plan_row[0] != "abierto":
        sys.exit(f"[FALLO] plan {args.plan} no está abierto (estado={plan_row[0]})")

    # Requisito debe existir
    req = conn.execute(
        "SELECT 1 FROM requisito WHERE plan_id=? AND ref=?",
        (args.plan, args.ref),
    ).fetchone()
    if not req:
        sys.exit(f"[FALLO] requisito {args.plan}/{args.ref} no existe")

    # 2. Agente debe existir en actor con rol correcto
    actor_row = conn.execute(
        "SELECT clase, rol FROM actor WHERE id=?", (args.agente,),
    ).fetchone()
    if not actor_row:
        sys.exit(f"[FALLO] agente {args.agente} no existe en la tabla actor")

    datos = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    plan_por_linea = datos.get("plan_por_linea", {})
    roles_por_linea = datos.get("roles_por_linea", {})

    sigla = plan_por_linea.get(args.plan)
    if not sigla:
        sys.exit(f"[FALLO] {args.plan} no encontrado en plan_por_linea de oferta.yaml")

    rol_esperado = roles_por_linea.get(sigla, {}).get("rol")
    if not rol_esperado:
        sys.exit(f"[FALLO] sigla {sigla} no tiene rol en roles_por_linea")

    actor_rol = actor_row[1]
    if actor_rol != rol_esperado:
        sys.exit(
            f"[FALLO] agente {args.agente} tiene rol={actor_rol}, "
            f"pero roles_por_linea exige {rol_esperado} para {sigla}"
        )
    print(f"[agente] {args.agente} (rol={actor_rol}) OK para {sigla}")

    # 3. Idempotencia: no duplicar si ya hay pendiente/trabajando
    existente = conn.execute(
        "SELECT id, progreso FROM tarea "
        "WHERE plan_id=? AND req_ref=? AND titulo=? AND agente=? AND progreso IN ('pendiente','trabajando')",
        (args.plan, args.ref, args.titulo, args.agente),
    ).fetchone()
    if existente:
        print(f"[idempotente] tarea {existente[0]} ya existe ({existente[1]}). 0 cambios.")
        conn.close()
        return

    # 4. Aviso si hay tareas en espera_firma/hecha
    firmables = conn.execute(
        "SELECT id, progreso FROM tarea WHERE plan_id=? AND req_ref=? AND progreso IN ('espera_firma','hecha')",
        (args.plan, args.ref),
    ).fetchall()
    if firmables:
        ids = ", ".join(f"tarea {t[0]} ({t[1]})" for t in firmables)
        print(f"[WARN] {args.plan}/{args.ref} ya tiene tareas firmables: {ids}")

    if args.dry_run:
        print(f"[dry-run] INSERT tarea: plan={args.plan} ref={args.ref} agente={args.agente}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "tarea")

    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
            (args.plan, args.ref, args.titulo, "pendiente", args.agente),
        )
        tarea_id = cur.lastrowid

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), ACTOR, "tarea_creada", args.plan, f"tarea {tarea_id}: {args.titulo} (agente {args.agente})"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] tarea {tarea_id} creada: {args.plan}/{args.ref} → {args.agente}")


if __name__ == "__main__":
    main()
