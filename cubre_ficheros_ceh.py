"""Inserta relaciones cubre mod→linea para ficheros de como-estoy-hecho.

La vista construye 'componentes' desde cubre (fichero→línea), no desde
contiene (sol→fichero). Sin estas relaciones la vista muestra componentes=[].

    python3 cubre_ficheros_ceh.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
AMBITO = "coforge-santander"
REPO = "como-estoy-hecho"

CUBRE = [
    ("app/main.py", ["T02", "T03"]),
    ("app/como_estoy_hecho/router.py", ["T02", "T04", "T11"]),
    ("app/como_estoy_hecho/oferta.py", ["T02"]),
    ("app/como_estoy_hecho/pii.py", ["T12"]),
    ("app/como_estoy_hecho/static/index.html", ["T04", "T11"]),
    ("app/api/health/routes.py", ["T02", "T15"]),
    ("app/core/config.py", ["T03"]),
    ("app/security/middleware.py", ["T12"]),
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

    for path, lineas in CUBRE:
        mod_id = f"mod:{AMBITO}:{REPO}:{path}"
        if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (mod_id,)).fetchone():
            sys.exit(f"[FALLO] nodo {mod_id} no existe")
        for lid in lineas:
            linea_id = f"linea:coforge:{lid}"
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (linea_id,)).fetchone():
                sys.exit(f"[FALLO] nodo {linea_id} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "cubre-ficheros-ceh")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        altas = 0
        for path, lineas in CUBRE:
            mod_id = f"mod:{AMBITO}:{REPO}:{path}"
            for lid in lineas:
                linea_id = f"linea:coforge:{lid}"
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'cubre', 'observado', 'plantilla/cubre_ficheros_ceh.py', ?)",
                    (mod_id, linea_id, ts),
                ).rowcount
                if rc == 1:
                    altas += 1
                    print(f"  [cubre] {path} → {lid}")
                else:
                    print(f"  [skip] {path} → {lid} ya existe")

        if altas:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'relaciones_cubre', ?, NULL, ?)",
                (ts, ACTOR, "sol:coforge:como-estoy-hecho",
                 f"{altas} relaciones cubre mod→linea para que /oferta muestre componentes"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {altas} relaciones cubre insertadas")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
