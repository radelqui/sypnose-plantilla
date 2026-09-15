"""TRASPASO-4 A2: crea nodo solución, relaciones cubre solución→linea_oferta y módulos→linea T01.

    python3 enlazar_solucion.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/enlazar_solucion.py"
COLECCION = "plantilla-microservicio-ia"
NODO_PLANTILLA = "plantilla:microservicio-ia"
SOL_ID = "sol:coforge:rag-banking-agent"
SOL_NOMBRE = "rag-banking-agent (Coforge/Santander)"
PROY_ID = "proy:vmi3211028:rag-banking-agent"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-enlaces.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def insertar_si_nuevo(conn, sql, args, etiqueta, altas, existian):
    if conn.execute(sql, args).rowcount == 1:
        altas.append(etiqueta)
        return True
    existian.append(etiqueta)
    return False


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


def afirmar(conn, actor, nodo_id, campo, valor, certeza="observado"):
    ya = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1", (nodo_id, campo)
    ).fetchall()
    if any(v == valor for _, v in ya):
        return False
    for fid, _ in ya:
        conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (fid,))
    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
        (nodo_id, campo, valor, certeza, FUENTE, actor, ahora()),
    )
    evento(conn, actor, "afirmacion_creada", f"{campo} = {valor[:120]}", nodo_id=nodo_id)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] actor {args.actor} no existe")

    lineas = conn.execute(
        "SELECT id FROM nodo WHERE tipo='linea_oferta' ORDER BY id"
    ).fetchall()
    if not lineas:
        sys.exit("[FALLO] no hay nodos linea_oferta; ejecuta cargar_raices.py primero")
    print(f"[registro] {len(lineas)} linea_oferta encontradas")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b} ({b.stat().st_size} bytes)")

    altas = []
    existian = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        insertar_si_nuevo(
            conn,
            "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
            "VALUES (?, 'solucion', ?, 'coforge-santander', 'activo', ?, 'humano')",
            (SOL_ID, SOL_NOMBRE, ahora()),
            f"nodo {SOL_ID}", altas, existian,
        )
        if SOL_ID in [a.split()[-1] for a in altas if "nodo" in a]:
            evento(conn, args.actor, "alta_nodo", f"nodo solución {SOL_ID}", nodo_id=SOL_ID)

        insertar_si_nuevo(
            conn,
            "INSERT OR IGNORE INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
            (COLECCION, SOL_ID),
            f"ancla {SOL_ID}", altas, existian,
        )

        for (linea_id,) in lineas:
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                (SOL_ID, linea_id, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                evento(conn, args.actor, "relacion_cubre", f"{SOL_ID} cubre {linea_id}", nodo_id=SOL_ID)
                altas.append(f"cubre {SOL_ID} → {linea_id}")
            else:
                existian.append(f"cubre {SOL_ID} → {linea_id}")

        modulos_t01 = [
            "dir:vmi3211028:rag-banking-agent:app",
            "mod:vmi3211028:rag-banking-agent:app/api/routes.py",
            "api:vmi3211028:rag-banking-agent:POST:/consultar",
            "api:vmi3211028:rag-banking-agent:GET:/health/live",
            "api:vmi3211028:rag-banking-agent:GET:/health/ready",
        ]
        linea_t01 = "linea:coforge:T01"
        for mod in modulos_t01:
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (mod,)).fetchone():
                print(f"  ! módulo {mod} no existe, se omite")
                continue
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                (mod, linea_t01, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                evento(conn, args.actor, "relacion_cubre", f"{mod} cubre {linea_t01}", nodo_id=mod)
                altas.append(f"cubre {mod} → {linea_t01}")
            else:
                existian.append(f"cubre {mod} → {linea_t01}")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:puerto", "8000"):
            altas.append("afirmacion tecnico:puerto=8000")
        else:
            existian.append("afirmacion tecnico:puerto=8000")

        rutas = "GET /health/live, GET /health/ready, POST /api/v1/consultar"
        if afirmar(conn, args.actor, SOL_ID, "tecnico:rutas", rutas):
            altas.append(f"afirmacion tecnico:rutas={rutas}")
        else:
            existian.append(f"afirmacion tecnico:rutas")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:framework", "FastAPI + LlamaIndex + pgvector"):
            altas.append("afirmacion tecnico:framework")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")
        return

    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  nodo solución existe  :", "SÍ" if conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone() else "NO")
    print("  relaciones cubre sol  :", q(f"SELECT COUNT(*) FROM relacion WHERE origen='{SOL_ID}' AND tipo='cubre'"))
    print("  relaciones cubre mod→T01:", q(f"SELECT COUNT(*) FROM relacion WHERE destino='linea:coforge:T01' AND tipo='cubre' AND origen!='{SOL_ID}'"))
    print("  afirmaciones tecnico  :", q(f"SELECT COUNT(*) FROM afirmacion WHERE nodo_id='{SOL_ID}' AND campo LIKE 'tecnico:%' AND vigente=1"))
    conn.close()


if __name__ == "__main__":
    main()
