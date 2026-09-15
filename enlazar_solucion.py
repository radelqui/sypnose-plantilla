"""TRASPASO-4 A2: crea nodo solución, relaciones cubre, plan_objetivo, afirmaciones para la vista.

    python3 enlazar_solucion.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/enlazar_solucion.py"
COLECCION = "plantilla-microservicio-ia"
NODO_PLANTILLA = "plantilla:microservicio-ia"
SOL_ID = "sol:coforge:rag-banking-agent"
SOL_NOMBRE = "rag-banking-agent (Coforge/Santander)"
PROY_ID = "proy:vmi3211028:rag-banking-agent"
OFERTA_TITULO = "Python Developer + IA · Coforge / Santander"
REPO_URL = "https://github.com/radelqui/rag-banking-agent"


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


REPO_RAG = Path.home() / "rag-banking-agent"

NODO_A_RUTA = {
    "dir:": lambda nid: nid.split(":", 3)[-1] if nid.count(":") >= 3 else None,
    "mod:": lambda nid: nid.split(":", 3)[-1] if nid.count(":") >= 3 else None,
}

AGENTE_A_RAMA = {
    "IA:00-lead": "main",
    "IA:01-git-cicd": "chat/01-git-cicd",
    "IA:02-backend-api": "chat/02-backend-api",
    "IA:03-datos-rag": "chat/03-datos-rag",
    "IA:04-agentes": "chat/04-agentes",
    "IA:05-arquitecto-sypnose": "chat/05-arquitecto-sypnose",
    "IA:06-frontend": "chat/06-frontend",
}


def nodo_id_a_ruta(nodo_id: str):
    for prefijo, fn in NODO_A_RUTA.items():
        if nodo_id.startswith(prefijo):
            return fn(nodo_id)
    return None


def agente_a_rama(agente: str) -> str:
    for prefijo, rama in AGENTE_A_RAMA.items():
        if agente.startswith(prefijo):
            return rama
    return "main"


def obtener_commit_fichero(ruta: str, rama: str) -> str | None:
    if not REPO_RAG.exists():
        return None
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_RAG), "log", "-1", "--format=%H", rama, "--", ruta],
            capture_output=True, text=True, timeout=10,
        )
        sha = r.stdout.strip()
        return sha if sha else None
    except Exception:
        return None


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

    verificar_repo_limpio()

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
    avisos = []

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

        if afirmar(conn, args.actor, SOL_ID, "tecnico:repo_url", REPO_URL):
            altas.append(f"afirmacion tecnico:repo_url={REPO_URL}")
        else:
            existian.append("afirmacion tecnico:repo_url")

        if afirmar(conn, args.actor, NODO_PLANTILLA, "oferta_titulo", OFERTA_TITULO):
            altas.append(f"afirmacion oferta_titulo en {NODO_PLANTILLA}")
        else:
            existian.append(f"afirmacion oferta_titulo en {NODO_PLANTILLA}")

        if afirmar(conn, args.actor, SOL_ID, "oferta_titulo", OFERTA_TITULO):
            altas.append(f"afirmacion oferta_titulo en {SOL_ID}")
        else:
            existian.append(f"afirmacion oferta_titulo en {SOL_ID}")

        planes_cs = conn.execute(
            "SELECT id FROM plan WHERE id LIKE 'PLAN-CS-T%' ORDER BY id"
        ).fetchall()
        for (plan_id,) in planes_cs:
            sufijo = plan_id.replace("PLAN-CS-T", "")
            linea_id = f"linea:coforge:T{sufijo}"
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (linea_id,)).fetchone():
                avisos.append(f"plan_objetivo: {linea_id} no existe, se omite {plan_id}")
                continue
            rc = conn.execute(
                "INSERT OR IGNORE INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                (plan_id, linea_id),
            ).rowcount
            if rc == 1:
                altas.append(f"plan_objetivo {plan_id} → {linea_id}")
            else:
                existian.append(f"plan_objetivo {plan_id} → {linea_id}")

        if planes_cs:
            evento(conn, args.actor, "plan_objetivo_lineas",
                   f"{len(planes_cs)} PLAN-CS-T enlazados a linea_oferta como objetivo")

        escrito_por = conn.execute(
            "SELECT id, nodo_id, valor FROM afirmacion WHERE campo='escrito_por' AND vigente=1"
        ).fetchall()
        for afirm_id, nodo_id, agente in escrito_por:
            ya_commit = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='commit' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            if ya_commit:
                existian.append(f"commit ya existe para {nodo_id}")
                continue

            ruta = nodo_id_a_ruta(nodo_id)
            if not ruta:
                continue
            rama = agente_a_rama(agente)
            sha = obtener_commit_fichero(ruta, rama)
            if not sha:
                avisos.append(f"commit: sin sha para {ruta} en {rama}")
                continue

            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (nodo_id, "commit", sha, "observado", FUENTE, args.actor, ahora()),
            )
            altas.append(f"commit {sha[:12]} en {nodo_id}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    for a in avisos:
        print(f"  ! {a}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")
        return

    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  nodo solución existe  :", "SÍ" if conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone() else "NO")
    print("  relaciones cubre sol  :", q(f"SELECT COUNT(*) FROM relacion WHERE origen='{SOL_ID}' AND tipo='cubre'"))
    print("  relaciones cubre mod→T01:", q(f"SELECT COUNT(*) FROM relacion WHERE destino='linea:coforge:T01' AND tipo='cubre' AND origen!='{SOL_ID}'"))
    print("  afirmaciones tecnico  :", q(f"SELECT COUNT(*) FROM afirmacion WHERE nodo_id='{SOL_ID}' AND campo LIKE 'tecnico:%' AND vigente=1"))
    print("  plan_objetivo lineas  :", q("SELECT COUNT(*) FROM plan_objetivo WHERE plan_id LIKE 'PLAN-CS-T%' AND nodo_id LIKE 'linea:%'"))
    print("  afirmaciones commit   :", q("SELECT COUNT(*) FROM afirmacion WHERE campo='commit' AND vigente=1"))
    conn.close()


if __name__ == "__main__":
    main()
