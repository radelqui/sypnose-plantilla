"""Crea PLAN-CS2-R2: corrección R2 medida por 07b (4 ficheros fuera del dominio).

Tareas:
  68 — 05-arquitecto: .gitignore al esqueleto, tag v1.2, resync como-estoy-hecho
  69 — 04-agentes: mover test_integration.py dentro de tests/como_estoy_hecho/

    python3 crear_plan_r2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_r2.py"

PLAN_ID = "PLAN-CS2-R2"
AFECTA = "sol:coforge:como-estoy-hecho"
CLASE = "mantener"
QUE = "Corrección R2: ficheros fuera del dominio tras resync v1.1"
PARA = "Que diff esqueleto..HEAD fuera del dominio sea 0 y comprobar_segundo.py pase"
PORQUE = "07b midió R2 (evento 24253): 4 ficheros fuera del dominio, NO CUMPLE"
DUENO = "H:carlos"
WORKTREE = "plantilla/wt-R2"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    existing = conn.execute("SELECT id, estado FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
    if existing:
        print(f"[skip] {PLAN_ID} ya existe (estado={existing[1]})")
        conn.close()
        return

    if not args.dry_run:
        backup_registro(conn, db_path, "plan-r2")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
            "VALUES (?, ?, ?, ?, ?, ?, 'abierto', ?, ?, ?, ?)",
            (PLAN_ID, CLASE, QUE, PARA, PORQUE, AFECTA, ACTOR, DUENO, WORKTREE, ts),
        )
        print(f"  [plan] {PLAN_ID} creado")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'plan_creado_abierto', NULL, ?, ?)",
            (ts, ACTOR, PLAN_ID,
             f"PLAN-CS2-R2: corrección R2 (07b 24253), afecta {AFECTA}"),
        )

        # --- Requisitos ---
        conn.execute(
            "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?, 'R1', ?, ?)",
            (PLAN_ID,
             "Cuando se ejecute python microservicio/comprobar_segundo.py sobre como-estoy-hecho con el esqueleto v1.2, "
             "DEBE dar exit 0: .gitignore en el esqueleto, tags v1.1/v1.2 en ambos repos, diff fuera del dominio = 0.",
             "python microservicio/comprobar_segundo.py"),
        )
        print("  [requisito] R1: esqueleto + tags + resync")

        conn.execute(
            "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?, 'R2', ?, ?)",
            (PLAN_ID,
             "Cuando se ejecute python -m pytest tests -q sobre como-estoy-hecho, "
             "DEBE pasar: tests/test_integration.py movido a tests/como_estoy_hecho/test_integration.py.",
             "python -m pytest tests -q"),
        )
        print("  [requisito] R2: mover test_integration.py")

        # --- Tarea 68: 05-arquitecto → .gitignore al esqueleto + tags ---
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, agente, progreso) "
            "VALUES (?, 'R1', ?, ?, 'pendiente')",
            (PLAN_ID,
             "Añadir .gitignore al esqueleto, tag v1.2, resync como-estoy-hecho con v1.2 + tags v1.1/v1.2; "
             "comprobación: python microservicio/comprobar_segundo.py exit 0",
             "IA:05-arquitecto-sypnose:claude-opus-4-6"),
        )
        t68_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"  [tarea] {t68_id}: .gitignore + tags + resync (05-arquitecto)")

        # --- Tarea 69: 04-agentes → mover test_integration.py ---
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, agente, progreso, bloqueada_por) "
            "VALUES (?, 'R2', ?, ?, 'pendiente', NULL)",
            (PLAN_ID,
             "Mover tests/test_integration.py a tests/como_estoy_hecho/test_integration.py "
             "sin cambiar contenido salvo imports; comprobación: python -m pytest tests -q",
             "IA:04-agentes:claude-sonnet-5"),
        )
        t69_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"  [tarea] {t69_id}: mover test_integration.py (04-agentes)")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {PLAN_ID} abierto con tareas 68, 69")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
