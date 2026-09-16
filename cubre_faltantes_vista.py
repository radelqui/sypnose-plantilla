"""Completa relaciones cubre fichero→línea faltantes para la vista pública.

Añade las relaciones que faltan según oferta.yaml segunda_solucion.archivos_por_linea
y archivos_por_linea (principal) — lo que cubre_ficheros_ceh.py no cubría.

    python3 cubre_faltantes_vista.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cubre_faltantes_vista.py"

CEH_AMBITO = "coforge-santander"
CEH_REPO = "como-estoy-hecho"
CEH_SOL = "sol:coforge:como-estoy-hecho"

RAG_AMBITO = "vmi3211028"
RAG_REPO = "rag-banking-agent"
RAG_SOL = "sol:coforge:rag-banking-agent"

CEH_CUBRE_FALTANTES = [
    ("app/main.py", ["T13", "T15"]),
    ("app/como_estoy_hecho/oferta.py", ["T12"]),
    ("tests/test_integration.py", ["T14", "T15"]),
    ("tests/test_autodiscovery.py", ["T14"]),
]

RAG_CUBRE_FALTANTES = [
    (".github/workflows/ci.yml", ["T14"]),
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def asegurar_nodo(conn, nodo_id, nombre, ruta, ambito, ts):
    if conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
        return False
    conn.execute(
        "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, descubierto_en, descubierto_por) "
        "VALUES (?, 'modulo', ?, ?, ?, ?, ?)",
        (nodo_id, nombre, ruta, ambito, ts, ACTOR),
    )
    return True


def asegurar_contiene(conn, sol_id, nodo_id, ts):
    return conn.execute(
        "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
        "VALUES (?, ?, 'contiene', 'observado', ?, ?)",
        (sol_id, nodo_id, FUENTE, ts),
    ).rowcount == 1


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

    if not args.dry_run:
        backup_registro(conn, db_path, "cubre-faltantes")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        nodos_creados = 0
        cubre_creados = 0
        contiene_creados = 0

        for ruta, lineas in CEH_CUBRE_FALTANTES:
            nodo_id = f"mod:{CEH_AMBITO}:{CEH_REPO}:{ruta}"
            nombre = ruta.split("/")[-1]
            if asegurar_nodo(conn, nodo_id, nombre, ruta, CEH_AMBITO, ts):
                nodos_creados += 1
                print(f"  [nodo] {nodo_id}")
            if asegurar_contiene(conn, CEH_SOL, nodo_id, ts):
                contiene_creados += 1
                print(f"  [contiene] {CEH_SOL} → {ruta}")
            for lid in lineas:
                linea_id = f"linea:coforge:{lid}"
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                    (nodo_id, linea_id, FUENTE, ts),
                ).rowcount
                if rc:
                    cubre_creados += 1
                    print(f"  [cubre] CEH:{ruta} → {lid}")
                else:
                    print(f"  [skip] CEH:{ruta} → {lid} (ya existe)")

        for ruta, lineas in RAG_CUBRE_FALTANTES:
            nodo_id = f"mod:{RAG_AMBITO}:{RAG_REPO}:{ruta}"
            nombre = ruta.split("/")[-1]
            if asegurar_nodo(conn, nodo_id, nombre, ruta, RAG_AMBITO, ts):
                nodos_creados += 1
                print(f"  [nodo] {nodo_id}")
            for lid in lineas:
                linea_id = f"linea:coforge:{lid}"
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                    (nodo_id, linea_id, FUENTE, ts),
                ).rowcount
                if rc:
                    cubre_creados += 1
                    print(f"  [cubre] RAG:{ruta} → {lid}")
                else:
                    print(f"  [skip] RAG:{ruta} → {lid} (ya existe)")

        if cubre_creados or contiene_creados or nodos_creados:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'cubre_faltantes_vista', NULL, NULL, ?)",
                (ts, ACTOR,
                 f"{nodos_creados} nodos, {cubre_creados} cubre, {contiene_creados} contiene — "
                 f"CEH: main.py→T13/T15, oferta.py→T12, test_integration.py→T14/T15, test_autodiscovery.py→T14; "
                 f"RAG: ci.yml→T14"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {nodos_creados} nodos, {cubre_creados} cubre, {contiene_creados} contiene")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
