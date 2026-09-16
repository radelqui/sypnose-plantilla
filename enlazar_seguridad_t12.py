"""Crea nodos de fichero y evidencia para los controles de seguridad de T12.

app/security/pii.py, guardrails.py, identity.py existen como carpeta pero
no como ficheros individuales. Este script crea los nodos mod: y añade
evidencia file@sha sobre PLAN-CS-T12.

    python3 enlazar_seguridad_t12.py --db ~/sypnose-f1/registry.db [--dry-run]
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
AMBITO = "vmi3211028"
REPO_NAME = "rag-banking-agent"
RAG_REPO = PLANTILLA_DIR.parent / REPO_NAME
PLAN_ID = "PLAN-CS-T12"
SOL_ID = "sol:coforge:rag-banking-agent"
DIR_NODO = f"dir:{AMBITO}:{REPO_NAME}:app/security"

FILES = [
    ("app/security/pii.py", "PII filtering: enmascara datos personales en respuestas del agente"),
    ("app/security/guardrails.py", "Guardrails: validación de entrada y límites de consulta"),
    ("app/security/identity.py", "Identity: gestión de X-Customer-Id desde la pasarela"),
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_remote_sha(repo: Path) -> str:
    for ref in ("origin/main", "github/main"):
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", ref],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    sys.exit(f"[FALLO] no se resolvió remote/main en {repo}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    sha = get_remote_sha(RAG_REPO)
    print(f"[rag-banking-agent] remote/main = {sha[:12]}")

    for path, _ in FILES:
        r = subprocess.run(
            ["git", "-C", str(RAG_REPO), "cat-file", "-e", f"{sha}:{path}"],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            sys.exit(f"[FALLO] {path} no existe en {sha[:12]}")
    print("[OK] todos los ficheros existen")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        sys.exit(f"[FALLO] plan {PLAN_ID} no existe")
    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (DIR_NODO,)).fetchone():
        sys.exit(f"[FALLO] nodo directorio {DIR_NODO} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "seguridad-t12")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        nodos_creados = []
        evidencia_creada = []

        for path, desc in FILES:
            nodo_id = f"mod:{AMBITO}:{REPO_NAME}:{path}"

            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
                conn.execute(
                    "INSERT INTO nodo (id, tipo, nombre) VALUES (?, 'mod', ?)",
                    (nodo_id, path.split("/")[-1]),
                )
                conn.execute(
                    "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'contiene', 'observado', ?, ?)",
                    (DIR_NODO, nodo_id, "enlazar_seguridad_t12.py", ts),
                )
                nodos_creados.append(nodo_id)
                print(f"  [nodo] {nodo_id}")

            fuente = f"{path}@{sha}"
            rc = conn.execute(
                "INSERT OR IGNORE INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?, ?, ?, ?)",
                (PLAN_ID, SOL_ID, fuente, desc),
            ).rowcount
            if rc:
                evidencia_creada.append(f"{PLAN_ID}: {fuente}")
                print(f"  [evidencia] {fuente}")

        if nodos_creados or evidencia_creada:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'seguridad_ficheros_t12', ?, ?, ?)",
                (ts, ACTOR, SOL_ID, PLAN_ID,
                 f"{len(nodos_creados)} nodos fichero + {len(evidencia_creada)} evidencia: "
                 f"pii.py, guardrails.py, identity.py @ {sha[:12]}"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\nnodos: {len(nodos_creados)} · evidencia: {len(evidencia_creada)}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
