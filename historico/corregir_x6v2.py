"""Corrección X6v2: invalida evidencia 173, añade evento: para T06, retira 30304/30305 al nodo sol.

(1) Invalida evidencia 173 (07-verificador/VERIFICACION.md@c5d232412bce) — fichero inexistente.
(2) Añade fuentes evento:<id> para T06 (eventos de 07 verificador ratificado).
(3) Retira afirmaciones 30304/30305 (descripcion/por_que en linea:coforge:T01) → vigente=0.
(4) Escribe descripcion:T01 y por_que:T01 en sol:coforge:rag-banking-agent.

Guardia idempotente: evento 'correccion_x6v2'.

    python3 historico/corregir_x6v2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
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
EVENTO_GUARDIA = "correccion_x6v2"
SOL_ID = "sol:coforge:rag-banking-agent"
FUENTE_SCRIPT = "plantilla/historico/corregir_x6v2.py"

EVIDENCIA_INVALIDA = "07-verificador/VERIFICACION.md@c5d232412bce"

EVENTOS_T06 = [22376, 22377, 22456, 22458, 22464, 22465]

AFIRMACIONES_RETIRAR = [30304, 30305]


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

    # Read values from afirmaciones to migrate
    desc_row = conn.execute(
        "SELECT nodo_id, campo, valor, certeza, fuente, actor_id FROM afirmacion WHERE id=30304 AND vigente=1"
    ).fetchone()
    porque_row = conn.execute(
        "SELECT nodo_id, campo, valor, certeza, fuente, actor_id FROM afirmacion WHERE id=30305 AND vigente=1"
    ).fetchone()

    if args.dry_run:
        print(f"[dry-run] invalidar evidencia: {EVIDENCIA_INVALIDA}")
        print(f"[dry-run] añadir {len(EVENTOS_T06)} fuentes evento: para PLAN-CS-T06")
        if desc_row:
            print(f"[dry-run] retirar 30304 ({desc_row[1]}) de {desc_row[0]}")
            print(f"[dry-run] escribir descripcion:T01 en {SOL_ID}")
        if porque_row:
            print(f"[dry-run] retirar 30305 ({porque_row[1]}) de {porque_row[0]}")
            print(f"[dry-run] escribir por_que:T01 en {SOL_ID}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "x6v2")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        # (1) Invalidar evidencia 173
        conn.execute(
            "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?,?,?)",
            ("PLAN-CS-T06", f"INVALIDA:{EVIDENCIA_INVALIDA}",
             "fichero inexistente en plantilla y rag-banking-agent; sha no corresponde a rag"),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "evidencia_invalidada", "PLAN-CS-T06",
             f"INVALIDA:{EVIDENCIA_INVALIDA}"),
        )
        print(f"[invalidada] {EVIDENCIA_INVALIDA}")

        # (2) Añadir fuentes evento:<id> para T06
        insertados = 0
        for eid in EVENTOS_T06:
            row = conn.execute("SELECT accion, substr(detalle,1,100) FROM evento WHERE rowid=?", (eid,)).fetchone()
            if not row:
                print(f"  [WARN] evento {eid} no encontrado, se omite")
                continue
            dice = f"{row[0]}: {row[1]}"
            rc = conn.execute(
                "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?,?,?)",
                ("PLAN-CS-T06", f"evento:{eid}", dice),
            ).rowcount
            if rc == 1:
                insertados += 1
                print(f"  [+] PLAN-CS-T06: evento:{eid}")
        print(f"[T06] {insertados} fuentes evento: añadidas")

        # (3) Retirar 30304/30305 de linea:coforge:T01
        for aid in AFIRMACIONES_RETIRAR:
            rc = conn.execute(
                "UPDATE afirmacion SET vigente=0 WHERE id=? AND vigente=1", (aid,)
            ).rowcount
            if rc == 1:
                print(f"[retirada] afirmacion {aid} → vigente=0")
            else:
                print(f"[skip] afirmacion {aid} ya era vigente=0")

        # (4) Escribir descripcion:T01 y por_que:T01 en sol node
        if desc_row:
            existente = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='descripcion:T01' AND vigente=1",
                (SOL_ID,),
            ).fetchone()
            if not existente or existente[1] != desc_row[2]:
                if existente:
                    conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (existente[0],))
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                    "VALUES (?,?,?,?,?,?,?,1)",
                    (SOL_ID, "descripcion:T01", desc_row[2], desc_row[3], desc_row[4], ACTOR, ts),
                )
                print(f"[insert] {SOL_ID}.descripcion:T01")
            else:
                print(f"[idempotente] descripcion:T01 ya coincide en {SOL_ID}")

        if porque_row:
            existente = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='por_que:T01' AND vigente=1",
                (SOL_ID,),
            ).fetchone()
            if not existente or existente[1] != porque_row[2]:
                if existente:
                    conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (existente[0],))
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                    "VALUES (?,?,?,?,?,?,?,1)",
                    (SOL_ID, "por_que:T01", porque_row[2], porque_row[3], porque_row[4], ACTOR, ts),
                )
                print(f"[insert] {SOL_ID}.por_que:T01")
            else:
                print(f"[idempotente] por_que:T01 ya coincide en {SOL_ID}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ts, ACTOR, EVENTO_GUARDIA,
             f"invalida evidencia 173, {insertados} evento: T06, retira 30304/30305, migra desc/porque a {SOL_ID}"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("[OK] corrección X6v2 aplicada")


if __name__ == "__main__":
    main()
