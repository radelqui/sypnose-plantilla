"""Corrección X6: añadir fuentes con formato fichero/commit a evidencia de T06 y T09.

T06 (code reviews): 07-verificador/VERIFICACION.md@<sha> con sha del plantilla HEAD.
T09 (git): git:commit:<sha> para cada commit firmado (Chat: trailer) en rag-banking-agent.

Guardia de idempotencia: si el evento 'correccion_evidencia_t06_t09' ya existe, aborta.

    python3 historico/corregir_evidencia_t06_t09.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import subprocess
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/historico/corregir_evidencia_t06_t09.py"
REPO_RAG = PLANTILLA_DIR.parent / "rag-banking-agent"
EVENTO_GUARDIA = "correccion_evidencia_t06_t09"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    ya = conn.execute(
        "SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA,)
    ).fetchone()
    if ya:
        print(f"[idempotente] evento {EVENTO_GUARDIA} ya existe. 0 cambios.")
        conn.close()
        return

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    plantilla_sha = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()

    # T06: evidence with @sha format
    t06_fuentes = []
    t06_base = "07-verificador/VERIFICACION.md"
    t06_fuente_sha = f"{t06_base}@{plantilla_sha[:12]}"
    t06_fuentes.append((
        "PLAN-CS-T06",
        t06_fuente_sha,
        f"07-verificador verificaciones de código (VERIFICACION.md del repo plantilla, sha {plantilla_sha[:12]})",
    ))

    # T09: git:commit:<sha> for each signed commit in rag-banking-agent
    t09_fuentes = []
    if REPO_RAG.exists():
        r = subprocess.run(
            ["git", "-C", str(REPO_RAG), "log", "--all", "--format=%H %s"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(" ", 1)
                sha = parts[0]
                msg = parts[1] if len(parts) > 1 else ""
                has_trailer = subprocess.run(
                    ["git", "-C", str(REPO_RAG), "log", "-1", "--format=%(trailers:key=Chat,valueonly)", sha],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip()
                if has_trailer:
                    t09_fuentes.append((
                        "PLAN-CS-T09",
                        f"git:commit:{sha[:12]}",
                        f"commit firmado (Chat: {has_trailer}): {msg[:100]}",
                    ))

    all_entries = t06_fuentes + t09_fuentes
    print(f"[T06] {len(t06_fuentes)} entradas")
    print(f"[T09] {len(t09_fuentes)} entradas (commits firmados)")

    if args.dry_run:
        for plan_id, fuente, dice in all_entries:
            print(f"  [dry-run] {plan_id}: {fuente} → {dice[:80]}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "evid-t06t09")

    conn.execute("BEGIN IMMEDIATE")
    try:
        insertados = 0
        for plan_id, fuente, dice in all_entries:
            rc = conn.execute(
                "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?,?,?)",
                (plan_id, fuente, dice),
            ).rowcount
            if rc == 1:
                insertados += 1
                print(f"  [+] {plan_id}: {fuente}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ahora(), ACTOR, EVENTO_GUARDIA,
             f"T06: {len(t06_fuentes)} entradas, T09: {len(t09_fuentes)} commits firmados, {insertados} insertados"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {insertados} evidencias insertadas (T06+T09)")


if __name__ == "__main__":
    main()
