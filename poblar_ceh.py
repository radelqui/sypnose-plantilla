"""Puebla sol:coforge:como-estoy-hecho con descripcion, contiene y commits.

La vista muestra que_es=null, componentes=[], produjo=[]: falta
descripcion, relaciones contiene a ficheros, y afirmaciones commit.

    python3 poblar_ceh.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
SOL_ID = "sol:coforge:como-estoy-hecho"
AMBITO = "coforge-santander"
REPO_NAME = "como-estoy-hecho"
CEH_REPO = PLANTILLA_DIR.parent / REPO_NAME

DESCRIPCION = (
    "como-estoy-hecho es un microservicio FastAPI de introspección: "
    "expone la arquitectura, la evidencia y el estado del proyecto como API REST "
    "(/api/v1/como-estoy-hecho) con filtrado PII y una interfaz web. "
    "Cubre T04 (UI), T11 (frontend React), T02 (API), T03 (Python backend), "
    "T12 (seguridad), T13 (CI/CD), T14 (testing) y T15 (mejora continua)."
)

POR_QUE = (
    "El banco pide interfaz web (T04/T11) y el agente RAG no la tiene; "
    "como-estoy-hecho la proporciona como segundo microservicio independiente, "
    "con el mismo esqueleto SYPNOSE (PII, health checks, tests ≥85%)."
)

ARCHIVOS = [
    ("app/main.py", "Entry point FastAPI, monta routers"),
    ("app/como_estoy_hecho/router.py", "Router: /api/v1/como-estoy-hecho + static UI"),
    ("app/como_estoy_hecho/oferta.py", "Lee oferta SYPNOSE del registro"),
    ("app/como_estoy_hecho/pii.py", "Filtrado PII en respuestas"),
    ("app/como_estoy_hecho/static/index.html", "SPA React (interfaz web)"),
    ("app/api/health/routes.py", "Health checks /live /ready"),
    ("app/core/config.py", "Configuración por entorno (pydantic-settings)"),
    ("app/security/middleware.py", "Middleware de seguridad"),
]

DIRECTORIOS = [
    "app",
    "app/como_estoy_hecho",
    "app/como_estoy_hecho/static",
    "app/api",
    "app/api/health",
    "app/core",
    "app/security",
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_sha(repo: Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] no se pudo obtener HEAD de {repo}")
    return r.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    sha = get_sha(CEH_REPO)
    print(f"[como-estoy-hecho] HEAD = {sha[:12]}")

    for path, _ in ARCHIVOS:
        r = subprocess.run(
            ["git", "-C", str(CEH_REPO), "cat-file", "-e", f"{sha}:{path}"],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            sys.exit(f"[FALLO] {path} no existe en {sha[:12]}")
    print(f"[OK] {len(ARCHIVOS)} ficheros verificados")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone():
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "poblar-ceh")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        stats = {"afirm": 0, "nodos": 0, "contiene": 0, "commits": 0}

        # 1. descripcion + por_que
        for campo, valor in [("descripcion", DESCRIPCION), ("por_que", POR_QUE)]:
            existing = conn.execute(
                "SELECT 1 FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                (SOL_ID, campo),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                    "VALUES (?, ?, ?, 'observado', 'plantilla/poblar_ceh.py', ?, ?)",
                    (SOL_ID, campo, valor, ACTOR, ts),
                )
                stats["afirm"] += 1
                print(f"  [afirm] {campo}")
            else:
                print(f"  [skip] {campo} ya existe")

        # 2. nodos directorio + contiene desde solucion
        for dirpath in DIRECTORIOS:
            dir_id = f"dir:{AMBITO}:{REPO_NAME}:{dirpath}"
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (dir_id,)).fetchone():
                conn.execute(
                    "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, descubierto_en, descubierto_por) "
                    "VALUES (?, 'carpeta', ?, ?, ?, ?, ?)",
                    (dir_id, dirpath.split("/")[-1], dirpath, AMBITO, ts, ACTOR),
                )
                stats["nodos"] += 1
                print(f"  [nodo:dir] {dir_id}")
            if not conn.execute(
                "SELECT 1 FROM relacion WHERE origen=? AND destino=? AND tipo='contiene'",
                (SOL_ID, dir_id),
            ).fetchone():
                conn.execute(
                    "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'contiene', 'observado', 'plantilla/poblar_ceh.py', ?)",
                    (SOL_ID, dir_id, ts),
                )
                stats["contiene"] += 1

        # 3. nodos fichero + contiene desde solucion + commit
        for path, desc in ARCHIVOS:
            mod_id = f"mod:{AMBITO}:{REPO_NAME}:{path}"
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (mod_id,)).fetchone():
                conn.execute(
                    "INSERT INTO nodo (id, tipo, nombre, ruta, ambito, descubierto_en, descubierto_por) "
                    "VALUES (?, 'modulo', ?, ?, ?, ?, ?)",
                    (mod_id, path.split("/")[-1], path, AMBITO, ts, ACTOR),
                )
                stats["nodos"] += 1
                print(f"  [nodo:mod] {mod_id}")
            if not conn.execute(
                "SELECT 1 FROM relacion WHERE origen=? AND destino=? AND tipo='contiene'",
                (SOL_ID, mod_id),
            ).fetchone():
                conn.execute(
                    "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'contiene', 'observado', 'plantilla/poblar_ceh.py', ?)",
                    (SOL_ID, mod_id, ts),
                )
                stats["contiene"] += 1

            # commit afirmacion on each file nodo
            existing_commit = conn.execute(
                "SELECT 1 FROM afirmacion WHERE nodo_id=? AND campo='commit' AND valor=? AND vigente=1",
                (mod_id, sha),
            ).fetchone()
            if not existing_commit:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                    "VALUES (?, 'commit', ?, 'observado', 'plantilla/poblar_ceh.py', ?, ?)",
                    (mod_id, sha, ACTOR, ts),
                )
                stats["commits"] += 1

        # 4. contiene relations from parent dirs to children
        for path, _ in ARCHIVOS:
            parent = "/".join(path.split("/")[:-1])
            parent_id = f"dir:{AMBITO}:{REPO_NAME}:{parent}"
            mod_id = f"mod:{AMBITO}:{REPO_NAME}:{path}"
            if not conn.execute(
                "SELECT 1 FROM relacion WHERE origen=? AND destino=? AND tipo='contiene'",
                (parent_id, mod_id),
            ).fetchone():
                conn.execute(
                    "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'contiene', 'observado', 'plantilla/poblar_ceh.py', ?)",
                    (parent_id, mod_id, ts),
                )

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
            "VALUES (?, ?, 'solucion_poblada', ?, NULL, ?)",
            (ts, ACTOR, SOL_ID,
             f"descripcion + por_que + {stats['nodos']} nodos + {stats['contiene']} contiene "
             f"+ {stats['commits']} commits @ {sha[:12]}"),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\nafirm: {stats['afirm']} · nodos: {stats['nodos']} · contiene: {stats['contiene']} · commits: {stats['commits']}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
