"""TRASPASO-4 A1: carga 15 raíces linea_oferta desde el texto crudo y retira los PLAN-T-xx como molde.

Los PLAN-T-xx pasan a ser planes de la solución Coforge: reciben afirmación `plantilla_origen`
apuntando a su linea_oferta correspondiente. No se borra nada (C8). Los linea_oferta no tienen
requisito propio; las EARS quedan en los PLAN-T-xx (ahora planes de solución).

    python3 cargar_raices.py --db ~/sypnose-f1/registry.db --txt oferta-coforge.txt [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from parser_oferta import extraer_lineas

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


def similitud(a: str, b: str) -> float:
    a_norm = a.lower().rstrip(".").strip()
    b_norm = b.lower().rstrip(".").strip()
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--txt", required=True, help="fichero de texto crudo de la oferta")
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--umbral", type=float, default=0.85, help="umbral de similitud para emparejar PLAN-T con línea")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser()
    texto = Path(args.txt).read_text(encoding="utf-8")
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

    planes_t = conn.execute(
        "SELECT id, para FROM plan WHERE id LIKE 'PLAN-T-%' ORDER BY id"
    ).fetchall()
    print(f"[registro] {len(planes_t)} planes PLAN-T-xx existentes")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b} ({b.stat().st_size} bytes)")

    altas = []
    existian = []
    avisos = []
    mapeo = []

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

        for plan_id, para_texto in planes_t:
            if not para_texto:
                avisos.append(f"{plan_id}: sin texto 'para', no se puede emparejar")
                continue
            mejor = max(lineas, key=lambda l: similitud(para_texto, l["texto"]))
            score = similitud(para_texto, mejor["texto"])
            nodo_linea = f"linea:coforge:{mejor['id']}"
            if score < args.umbral:
                avisos.append(f"{plan_id}: mejor match '{mejor['id']}' score={score:.2f} < umbral {args.umbral}")
                continue

            ya = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='plantilla_origen' AND vigente=1",
                (NODO_PLANTILLA,)
            ).fetchone()

            plan_nodo = plan_id
            existente = conn.execute(
                "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='plantilla_origen' AND vigente=1",
                (plan_nodo,)
            ).fetchone()

            if not existente:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                    (NODO_PLANTILLA, f"plan_linea:{mejor['id']}", plan_id, "observado", FUENTE, args.actor, ahora()),
                )
                conn.execute(
                    "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                    (ahora(), args.actor, "plantilla_origen_enlazada", nodo_linea, plan_id,
                     f"{plan_id} cubre {mejor['id']} (score={score:.2f})"),
                )
                altas.append(f"plantilla_origen {plan_id} → {mejor['id']}")
            else:
                existian.append(f"plantilla_origen {plan_id}")

            mapeo.append((plan_id, mejor["id"], score))

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    for a in avisos:
        print(f"  ! {a}")
    if mapeo:
        print(f"\n[mapeo PLAN-T → linea_oferta] ({len(mapeo)} pares)")
        for pid, lid, sc in mapeo:
            print(f"  {pid} → {lid} (sim={sc:.2f})")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha, nada escrito")
        return

    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  nodos linea_oferta    :", q("SELECT COUNT(*) FROM nodo WHERE tipo='linea_oferta'"))
    print("  anclas a plantilla    :", q(f"SELECT COUNT(*) FROM ancla WHERE coleccion_id='{COLECCION}'"))
    print("  afirmaciones plan_linea:", q(f"SELECT COUNT(*) FROM afirmacion WHERE nodo_id='{NODO_PLANTILLA}' AND campo LIKE 'plan_linea:%' AND vigente=1"))
    conn.close()


if __name__ == "__main__":
    main()
