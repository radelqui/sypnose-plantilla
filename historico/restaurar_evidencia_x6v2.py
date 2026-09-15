"""Restaurar evidencia X6v2: reinserta filas 190-194 eliminadas por error y emite evento restauracion_evidencia.

(1) Reinserta rows 190-194 (PLAN-CS-T06) eliminadas por rectificar_x6v2.py — violaba regla no-DELETE.
    Valores byte a byte de registry-backup-20260915-170429-rect-x6v2.db.
(2) Evento 'restauracion_evidencia' con rowids restaurados y backup de referencia (cubre también 173/109/129).

Guardia idempotente: evento 'restaurar_evidencia_x6v2'.

    python3 historico/restaurar_evidencia_x6v2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
EVENTO_GUARDIA = "restaurar_evidencia_x6v2"

ROWS_RESTORE = [
    (190, "PLAN-CS-T06", "evento:22376", "evidencia_07: 07-verificador/VERIFICACION.md"),
    (191, "PLAN-CS-T06", "evento:22377", "evidencia_07: 07-verificador/VERIFICACION.md#C2"),
    (192, "PLAN-CS-T06", "evento:22456", "evidencia_07: 07-verificador/VERIFICACION.md#APL-26fd5fb"),
    (193, "PLAN-CS-T06", "evento:22458", "verificado: archivos_por_linea (26fd5fb): NO CUMPLE (reconciliacion y certeza de cubre modulo->linea)"),
    (194, "PLAN-CS-T06", "evento:22464", "evidencia_07: 07-verificador/VERIFICACION.md#APL-e935f02"),
]

BACKUP_REF_173 = "registry-backup-20260915-165057-x6v2.db"
BACKUP_REF_109_129 = "registry-backup-20260915-165652-ci-green.db"
BACKUP_REF_190_194 = "registry-backup-20260915-170429-rect-x6v2.db"


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

    ya = conn.execute("SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA,)).fetchone()
    if ya:
        print(f"[idempotente] evento {EVENTO_GUARDIA} ya existe. 0 cambios.")
        conn.close()
        return

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    if args.dry_run:
        for rid, plan, fuente, dice in ROWS_RESTORE:
            print(f"[dry-run] INSERT rowid={rid} {plan} {fuente}")
        print("[dry-run] evento restauracion_evidencia")
        conn.close()
        return

    b = backup_registro(conn, db_path, "rest-ev-x6v2")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        insertados = 0

        for rid, plan_id, fuente, dice in ROWS_RESTORE:
            existing = conn.execute("SELECT 1 FROM evidencia WHERE rowid=?", (rid,)).fetchone()
            if existing:
                print(f"  [skip] rowid={rid} ya existe")
                continue
            conn.execute(
                "INSERT INTO evidencia (rowid, plan_id, fuente, dice) VALUES (?,?,?,?)",
                (rid, plan_id, fuente, dice),
            )
            insertados += 1
            print(f"  [+] rowid={rid} {plan_id} {fuente}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ts, ACTOR, EVENTO_GUARDIA,
             f"Restauradas {insertados} filas eliminadas por error (190-194) desde {BACKUP_REF_190_194}. "
             f"Filas 173 (desde {BACKUP_REF_173}), 109/129 (desde {BACKUP_REF_109_129}) ya restauradas "
             "por rectificar_x6v2 (evento 22623). La eliminación de 190-194 violaba la regla no-DELETE."),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {insertados} filas reinsertadas, evento restauracion_evidencia emitido")


if __name__ == "__main__":
    main()
