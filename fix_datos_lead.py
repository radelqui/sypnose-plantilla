"""Correcciones de datos pedidas por el lead (evento 25014, examen de la vista).

(1) portada_pregunta_09 (afirmación 33161): coste observado 1.054,95 → 92,79 USD
(2) tec:coforge:prometheus-observability: añadir commit y repo

    python3 fix_datos_lead.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
APROBACION = "orden del lead, evento 25014 (examen de la vista)"

PROMETHEUS_SHA = "987bd2f4d9a180e9d841a25dc98a1c669ff56ccd"
PROMETHEUS_REPO = "https://github.com/radelqui/sypnose-plantilla"
PROMETHEUS_NODO = "tec:coforge:prometheus-observability"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fix_pregunta_09(conn, ts):
    """Fix coste observado en portada_pregunta_09: 1054.95 → 92.79 USD."""
    row = conn.execute(
        "SELECT id, nodo_id, valor FROM afirmacion WHERE id=33161 AND vigente=1"
    ).fetchone()
    if not row:
        print("  [SKIP] afirmación 33161 no vigente o no existe")
        return

    old_valor = json.loads(row[2])
    old_respuesta = old_valor["respuesta"]

    if "92,79" in old_respuesta:
        print("  [SKIP] ya corregido (92,79 presente)")
        return

    if "1.054,95" not in old_respuesta:
        print(f"  [WARN] texto inesperado, no contiene 1.054,95: {old_respuesta[:80]}")
        return

    new_respuesta = old_respuesta.replace("1.054,95", "92,79")
    new_valor = dict(old_valor)
    new_valor["respuesta"] = new_respuesta
    new_valor_json = json.dumps(new_valor, ensure_ascii=False)

    conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=33161")

    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (row[1], "portada_pregunta_09", new_valor_json, "observado",
         f"corregido desde 33161, {APROBACION}", ACTOR, ts),
    )

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "dato_corregido", None,
         f"portada_pregunta_09 (afirmación 33161→vigente=0): coste observado "
         f"1.054,95→92,79 USD. Cifra verificada por SQL. {APROBACION}."),
    )
    print("  [OK] portada_pregunta_09: 1.054,95 → 92,79 USD")


def fix_prometheus(conn, ts):
    """Add commit and repo afirmaciones to tec:coforge:prometheus-observability."""
    existing_commit = conn.execute(
        "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='commit' AND vigente=1",
        (PROMETHEUS_NODO,),
    ).fetchone()
    existing_repo = conn.execute(
        "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='repo' AND vigente=1",
        (PROMETHEUS_NODO,),
    ).fetchone()

    if existing_commit and existing_repo:
        print(f"  [SKIP] {PROMETHEUS_NODO} ya tiene commit y repo")
        return

    if not existing_commit:
        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
            "VALUES (?,?,?,?,?,?,?,1)",
            (PROMETHEUS_NODO, "commit", PROMETHEUS_SHA, "observado",
             f"GitHub API 200, {APROBACION}", ACTOR, ts),
        )
        print(f"  [OK] commit={PROMETHEUS_SHA[:12]}...")

    if not existing_repo:
        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
            "VALUES (?,?,?,?,?,?,?,1)",
            (PROMETHEUS_NODO, "repo", PROMETHEUS_REPO, "observado",
             f"GitHub API 200, {APROBACION}", ACTOR, ts),
        )
        print(f"  [OK] repo={PROMETHEUS_REPO}")

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, ACTOR, "dato_corregido", None,
         f"{PROMETHEUS_NODO}: añadidos commit={PROMETHEUS_SHA[:12]} y "
         f"repo=sypnose-plantilla. Verificado con GitHub API (200). {APROBACION}."),
    )


def main():
    ap = argparse.ArgumentParser(description="Fix datos lead (evento 25014)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-fix-datos-lead")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        print("[1/2] Fix portada_pregunta_09 coste")
        fix_pregunta_09(conn, ts)

        print("\n[2/2] Fix prometheus-observability commit/repo")
        fix_prometheus(conn, ts)

        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[dry-run] transacción deshecha")
        else:
            conn.execute("COMMIT")
            last_ev = conn.execute("SELECT MAX(id) FROM evento").fetchone()[0]
            print(f"\n[OK] Datos corregidos. último evento: {last_ev}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
