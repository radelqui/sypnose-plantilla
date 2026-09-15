"""Abre un plan existente (propuesto → abierto) con dueño humano y worktree.

    python3 abrir_plan.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T07 --dueno H:carlos \
        --worktree "C:/MICD/Coforge Santander/01-git-cicd/wt" \
        --detalle "abierto por 00-lead por delegación de Carlos"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Abre un plan propuesto")
    ap.add_argument("--db", required=True)
    ap.add_argument("--plan", required=True, help="plan_id, ej. PLAN-CS-T07")
    ap.add_argument("--dueno", required=True, help="dueño humano (H:carlos)")
    ap.add_argument("--worktree", required=True, help="ruta worktree del chat")
    ap.add_argument("--detalle", default="", help="texto para el evento plan_abierto")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    if not args.dueno.startswith("H:"):
        sys.exit(f"[FALLO] dueño debe ser humano (H:...); recibido {args.dueno}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute(
        "SELECT id, estado, dueno, worktree FROM plan WHERE id=?", (args.plan,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] plan {args.plan} no existe")
    pid, estado, dueno_actual, wt_actual = row
    if estado == "abierto":
        print(f"[INFO] {pid} ya está abierto (dueño={dueno_actual}, worktree={wt_actual})")
        conn.close()
        return
    if estado != "propuesto":
        sys.exit(f"[FALLO] {pid} estado={estado}, esperado propuesto")

    actor_row = conn.execute(
        "SELECT 1 FROM actor WHERE id=? AND clase='humano'", (args.dueno,),
    ).fetchone()
    if not actor_row:
        sys.exit(f"[FALLO] {args.dueno} no es un actor humano registrado")

    if args.dry_run:
        print(f"[dry-run] abrir {pid}: dueno={args.dueno}, worktree={args.worktree}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "abrir-plan")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE plan SET estado='abierto', dueno=?, worktree=?, abierto_en=? WHERE id=?",
            (args.dueno, args.worktree, ts, args.plan),
        )
        detalle = args.detalle if args.detalle else f"plan abierto con dueño {args.dueno}"
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_abierto", args.plan, detalle),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {args.plan} abierto: dueno={args.dueno}, worktree={args.worktree}")


if __name__ == "__main__":
    main()
