"""Corrige el worktree registrado de un plan abierto.

    python3 corregir_worktree_plan.py --db ~/sypnose-f1/registry.db \
        --plan PLAN-CS-T11 --worktree "C:/MICD/Coforge Santander/01-git-cicd/wt-T13" \
        --motivo "worktree era wt (general); la línea T13 usa wt-T13"
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
    ap = argparse.ArgumentParser(description="Corrige el worktree de un plan abierto")
    ap.add_argument("--db", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--worktree", required=True, help="nuevo worktree")
    ap.add_argument("--motivo", required=True, help="motivo de la corrección")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute(
        "SELECT id, estado, worktree FROM plan WHERE id=?", (args.plan,),
    ).fetchone()
    if not row:
        sys.exit(f"[FALLO] plan {args.plan} no existe")
    pid, estado, wt_actual = row
    if estado != "abierto":
        sys.exit(f"[FALLO] {pid} estado={estado}, esperado abierto")

    conflicto = conn.execute(
        "SELECT id, estado FROM plan WHERE worktree=? AND id!=?",
        (args.worktree, args.plan),
    ).fetchone()
    if conflicto and conflicto[1] not in ("cerrado", "rechazado"):
        sys.exit(f"[FALLO] el worktree {args.worktree!r} lo tiene {conflicto[0]} ({conflicto[1]})")

    print(f"[corregir] {pid}: worktree {wt_actual!r} → {args.worktree!r}")
    if conflicto:
        print(f"[liberar] {conflicto[0]} ({conflicto[1]}): worktree → NULL")
    print(f"[motivo] {args.motivo}")

    if args.dry_run:
        print("[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "corregir-worktree")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conflicto:
            conn.execute(
                "UPDATE plan SET worktree=NULL WHERE id=?", (conflicto[0],),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "plan_corregido", conflicto[0],
                 f"worktree liberado (plan {conflicto[1]}): cedido a {args.plan}"),
            )
        conn.execute(
            "UPDATE plan SET worktree=? WHERE id=?",
            (args.worktree, args.plan),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_corregido", args.plan,
             f"worktree {wt_actual!r} → {args.worktree!r}: {args.motivo}"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {pid} worktree → {args.worktree}")


if __name__ == "__main__":
    main()
