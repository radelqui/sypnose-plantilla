"""Carga evidencia de la segunda solución (como-estoy-hecho) en el registro.

Inserta filas de evidencia con fuentes file@sha del repo como-estoy-hecho,
enlazadas a los planes de las líneas que cubre la segunda solución.

    python3 cargar_evidencia_ceh.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE_SCRIPT = "plantilla/cargar_evidencia_ceh.py"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"
PROYECTO_DIR = PLANTILLA_DIR.parent
SOL2_ID = "sol:coforge:como-estoy-hecho"

EVIDENCIA_MAP = {
    "PLAN-CS-T02": [
        ("app/como_estoy_hecho/router.py", "domain router POST /api/v1/como-estoy-hecho con endpoint agente"),
    ],
    "PLAN-CS-T03": [
        ("app/como_estoy_hecho/router.py", "API REST domain router con auto-mount"),
        ("app/main.py", "FastAPI app con auto-discovery de routers de dominio"),
    ],
    "PLAN-CS-T04": [
        ("app/como_estoy_hecho/static/index.html", "index.html responsive: contiene viewport meta y react placeholder"),
        ("tests/test_integration.py", "test_static_ui verifica GET /como-estoy-hecho/ui/ 200"),
    ],
    "PLAN-CS-T12": [
        ("app/como_estoy_hecho/pii.py", "PII filtering module para como-estoy-hecho"),
        ("app/como_estoy_hecho/oferta.py", "oferta module con datos del microservicio"),
    ],
    "PLAN-CS-T13": [
        ("app/como_estoy_hecho/static/index.html", "React placeholder SPA servida en /como-estoy-hecho/ui/"),
        ("app/como_estoy_hecho/router.py", "domain router monta endpoints del dominio como-estoy-hecho"),
        ("tests/test_integration.py", "integration tests: router + static UI + health"),
    ],
    "PLAN-CS-T14": [
        ("tests/test_integration.py", "tests de integración del segundo microservicio"),
        ("tests/test_autodiscovery.py", "tests de auto-discovery de routers en esqueleto"),
    ],
    "PLAN-CS-T15": [
        ("app/main.py", "esqueleto con auto-discovery: segundo microservicio instanciado desde plantilla"),
        ("tests/test_integration.py", "integration tests demuestran microservicio funcional"),
    ],
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_ceh_commit(repo_path: Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"[FALLO] no se pudo resolver HEAD de como-estoy-hecho en {repo_path}")
    return r.stdout.strip()


def verify_file_at_commit(repo_path: Path, path: str, commit: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(repo_path), "cat-file", "-e", f"{commit}:{path}"],
        capture_output=True, timeout=10,
    )
    return r.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    with open(OFERTA_YAML, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    seg = doc.get("segunda_solucion")
    if not seg:
        sys.exit("[FALLO] oferta.yaml no contiene segunda_solucion")

    repo_name = seg["nombre"]
    repo_path = PROYECTO_DIR / repo_name
    if not repo_path.exists() or not (repo_path / ".git").exists():
        sys.exit(f"[FALLO] repo {repo_name} no encontrado en {repo_path}")

    ceh_sha = get_ceh_commit(repo_path)
    print(f"[como-estoy-hecho] HEAD = {ceh_sha[:12]}")

    for plan_id, entries in EVIDENCIA_MAP.items():
        for path, _ in entries:
            if not verify_file_at_commit(repo_path, path, ceh_sha):
                sys.exit(f"[FALLO] {path} no existe en {repo_name}@{ceh_sha[:12]}")
    print("[verificación] todos los ficheros existen en el commit")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] actor {args.actor} no existe")

    verificar_canonicos_registrados(conn)

    for plan_id in EVIDENCIA_MAP:
        if not conn.execute("SELECT 1 FROM plan WHERE id=?", (plan_id,)).fetchone():
            sys.exit(f"[FALLO] plan {plan_id} no existe en el registro")

    if not args.dry_run:
        backup_registro(conn, db_path, "evidencia-ceh")

    altas = []
    existian = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        for plan_id, entries in sorted(EVIDENCIA_MAP.items()):
            for path, dice in entries:
                fuente = f"como-estoy-hecho:{path}@{ceh_sha}"
                rc = conn.execute(
                    "INSERT OR IGNORE INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?, ?, ?, ?)",
                    (plan_id, SOL2_ID, fuente, dice),
                ).rowcount
                if rc == 1:
                    altas.append(f"{plan_id}: {fuente}")
                else:
                    existian.append(f"{plan_id}: {fuente}")

        if altas:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                (ahora(), args.actor, "evidencia_segunda_solucion",
                 SOL2_ID, None,
                 f"{len(altas)} filas de evidencia como-estoy-hecho@{ceh_sha[:12]}"),
            )

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

    total = conn.execute(
        "SELECT COUNT(*) FROM evidencia WHERE nodo_id=?", (SOL2_ID,)
    ).fetchone()[0]
    print(f"\n[comprobación] evidencia total para {SOL2_ID}: {total} filas")
    conn.close()


if __name__ == "__main__":
    main()
