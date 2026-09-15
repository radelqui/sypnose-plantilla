"""TRASPASO-4 A1: carga 15 raíces linea_oferta desde el texto crudo.

    python3 cargar_raices.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from parser_oferta import extraer_lineas

from barrera import OFERTA_PATH, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/cargar_raices.py"
COLECCION = "plantilla-microservicio-ia"
NODO_PLANTILLA = "plantilla:microservicio-ia"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-raices.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    if not OFERTA_PATH.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_PATH}")
    texto = OFERTA_PATH.read_text(encoding="utf-8")
    lineas = extraer_lineas(texto)
    if not lineas:
        sys.exit("[FALLO] no se encontraron líneas en el texto crudo")
    print(f"[parser] {len(lineas)} líneas extraídas del texto crudo")

    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] el actor {args.actor} no existe en 'actor'")
    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (NODO_PLANTILLA,)).fetchone():
        sys.exit(f"[FALLO] el nodo {NODO_PLANTILLA} no existe; ejecuta cargar_molde.py primero")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b} ({b.stat().st_size} bytes)")

    altas = []
    existian = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        for l in lineas:
            nodo_id = f"linea:coforge:{l['id']}"
            ts = ahora()

            rc = conn.execute(
                "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                "VALUES (?, 'linea_oferta', ?, 'plantilla', 'activo', ?, ?)",
                (nodo_id, l["texto"], ts, "parser_oferta.py"),
            ).rowcount
            if rc == 1:
                conn.execute(
                    "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                    (ts, args.actor, "alta_linea_oferta", nodo_id, f"{l['id']} [{l['seccion']}] {l['texto'][:120]}"),
                )
                altas.append(f"nodo {nodo_id}")
            else:
                existian.append(f"nodo {nodo_id}")

            rc = conn.execute(
                "INSERT OR IGNORE INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
                (COLECCION, nodo_id),
            ).rowcount
            if rc == 1:
                conn.execute(
                    "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                    (ahora(), args.actor, "ancla_creada", nodo_id, f"ancla {COLECCION} -> {nodo_id}"),
                )
                altas.append(f"ancla {nodo_id}")
            else:
                existian.append(f"ancla {nodo_id}")

            afirm_seccion = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='seccion' AND vigente=1", (nodo_id,)
            ).fetchone()
            if not afirm_seccion:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                    (nodo_id, "seccion", l["seccion"], "observado", FUENTE, args.actor, ahora()),
                )
                conn.execute(
                    "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                    (ahora(), args.actor, "afirmacion_creada", nodo_id, f"seccion = {l['seccion']}"),
                )
                altas.append(f"afirmacion seccion={l['seccion']} en {nodo_id}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha, nada escrito")
        return

    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  nodos linea_oferta    :", q("SELECT COUNT(*) FROM nodo WHERE tipo='linea_oferta'"))
    print("  anclas a plantilla    :", q(f"SELECT COUNT(*) FROM ancla WHERE coleccion_id='{COLECCION}'"))
    conn.close()


if __name__ == "__main__":
    main()
