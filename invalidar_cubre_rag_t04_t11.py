"""Invalida relaciones cubre de rag-banking-agent sobre T04 y T11.

rag-banking-agent NO tiene interfaz responsive (T04) ni React SPA (T11);
solo como-estoy-hecho las cubre. Inserta marcadores INVALIDA:cubre y evento
sin UPDATE ni DELETE.

    python3 invalidar_cubre_rag_t04_t11.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
SOL_RAG = "sol:coforge:rag-banking-agent"

FILAS_A_INVALIDAR = [
    (15342, SOL_RAG, "linea:coforge:T04", "cubre"),
    (15343, SOL_RAG, "linea:coforge:T11", "cubre"),
]


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

    for rowid, origen, destino, tipo in FILAS_A_INVALIDAR:
        row = conn.execute(
            "SELECT rowid, origen, destino, tipo, certeza FROM relacion WHERE rowid=?",
            (rowid,),
        ).fetchone()
        if not row:
            sys.exit(f"[FALLO] rowid {rowid} no existe en relacion")
        rid, ro, rd, rt, rc = row
        if ro != origen or rd != destino or rt != tipo:
            sys.exit(
                f"[FALLO] rowid {rowid}: esperado ({origen},{destino},{tipo}), "
                f"encontrado ({ro},{rd},{rt})"
            )
        print(f"[verificado] rowid {rowid}: {origen} → {destino} tipo={tipo} certeza={rc}")

    if not args.dry_run:
        backup_registro(conn, db_path, "invalidar-cubre-rag")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        for rowid, origen, destino, tipo in FILAS_A_INVALIDAR:
            marker_tipo = f"INVALIDA:{tipo}"
            existing = conn.execute(
                "SELECT 1 FROM relacion WHERE origen=? AND destino=? AND tipo=?",
                (origen, destino, marker_tipo),
            ).fetchone()
            if existing:
                print(f"[ya existe] marcador {marker_tipo} para {origen}→{destino}")
                continue

            conn.execute(
                "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, ?, 'propuesto', ?, ?)",
                (origen, destino, marker_tipo,
                 f"invalidar_cubre_rag_t04_t11.py: rowid:{rowid} — rag-banking-agent no tiene interfaz",
                 ts),
            )
            print(f"[marcador] {marker_tipo}: {origen} → {destino} (rowid original: {rowid})")

            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'relacion_invalidada', ?, ?, ?)",
                (ts, ACTOR, origen, None,
                 f"INVALIDA:cubre rowid:{rowid} {origen}→{destino}: "
                 f"rag-banking-agent no tiene interfaz responsive ni React SPA; "
                 f"solo como-estoy-hecho cubre T04/T11. Orden del lead 16-sep."),
            )
            print(f"[evento] relacion_invalidada rowid:{rowid}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    if args.dry_run:
        print("\n--dry-run: transacción deshecha")
        return

    print("\n[comprobación] relaciones cubre activas para T04 y T11:")
    for lid in ("linea:coforge:T04", "linea:coforge:T11"):
        rows = conn.execute(
            "SELECT origen, certeza FROM relacion "
            "WHERE destino=? AND tipo='cubre' "
            "AND origen NOT IN ("
            "  SELECT origen FROM relacion WHERE destino=? AND tipo='INVALIDA:cubre'"
            ")",
            (lid, lid),
        ).fetchall()
        for origen, certeza in rows:
            print(f"  {lid} ← {origen} [{certeza}]")

    conn.close()


if __name__ == "__main__":
    main()
