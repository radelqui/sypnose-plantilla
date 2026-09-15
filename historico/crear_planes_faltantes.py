"""Crea PLAN-CS-T13, T14, T15 (planes faltantes) + rectifica evento 22186.

Lead 15-sep-2026: los 3 planes cubren líneas T11/T14/T15 respectivamente.
R0 bootstrap + tarea por cada uno. Agentes de roles_por_linea (oferta.yaml).
Evento 22186: actor incorrecto y fecha no-ISO → rectificación (eventos son inmutables).

    python3 crear_planes_faltantes.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import PLANTILLA_DIR, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/historico/crear_planes_faltantes.py"
SOL_ID = "sol:coforge:rag-banking-agent"
COL_COFORGE = "coforge-santander"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"

PLANES_NUEVOS = {
    "PLAN-CS-T13": {
        "linea": "T11",
        "que": "[coforge-santander] Knowledge or experience in React or front-end technologies (React, vue, JavaScript...)",
    },
    "PLAN-CS-T14": {
        "linea": "T14",
        "que": "[coforge-santander] Experience with CI/CD tools",
    },
    "PLAN-CS-T15": {
        "linea": "T15",
        "que": "[coforge-santander] Knowledge of microservices architecture",
    },
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-planes-faltantes.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


def cargar_roles():
    if not OFERTA_YAML.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_YAML}")
    data = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    mapping = data.get("roles_por_linea")
    if not mapping:
        sys.exit("[FALLO] oferta.yaml no tiene roles_por_linea")
    return {lid: (v["rol"], v["modelo"]) for lid, v in mapping.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    roles = cargar_roles()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    ya = conn.execute(
        "SELECT 1 FROM plan WHERE id='PLAN-CS-T13' LIMIT 1"
    ).fetchone()
    if ya:
        print("[INFO] PLAN-CS-T13 ya existe. Los planes faltantes ya fueron creados.")
        rectificar_evento(conn, args)
        return

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    cambios = []

    try:
        for plan_id, info in PLANES_NUEVOS.items():
            lid = info["linea"]
            que = info["que"]

            if lid not in roles:
                sys.exit(f"[FALLO] línea {lid} sin entrada en roles_por_linea")
            rol, modelo = roles[lid]
            agente = f"IA:{rol}:{modelo}"

            conn.execute(
                "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor) VALUES (?,?,?,?,?,?,?,?)",
                (plan_id, "investigar", que, f"linea:coforge:{lid}",
                 "línea deseable de la oferta (plan_por_linea)", rol, "propuesto", ACTOR),
            )
            cambios.append(f"plan {plan_id}")

            conn.execute(
                "INSERT INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                (plan_id, SOL_ID),
            )
            cambios.append(f"plan_objetivo {plan_id} → {SOL_ID}")

            ears_r0 = (f"Antes de escribir código para esta línea, el rol {rol} "
                       f"DEBE registrar el requisito comprobable de su solución (R1+) "
                       f"con su comprobación ejecutable")
            comprobacion_r0 = f"SELECT COUNT(*) FROM requisito WHERE plan_id='{plan_id}' AND ref<>'R0' → ≥1"

            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, "R0", ears_r0, comprobacion_r0),
            )
            conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (plan_id, "R0", "Definir requisito y comprobación de la línea", "pendiente", agente),
            )
            cambios.append(f"R0 + tarea en {plan_id} (agente {agente})")

            evento(conn, ACTOR, "plan_creado",
                   f"{plan_id}: {que[:100]} (R0 + tarea)", nodo_id=SOL_ID, plan_id=plan_id)

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[planes] {len(cambios)} cambios:")
    for c in cambios:
        print(f"  + {c}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    else:
        print("\n[verificación planes]")
        for pid in PLANES_NUEVOS:
            r = conn.execute("SELECT estado FROM plan WHERE id=?", (pid,)).fetchone()
            print(f"  {pid}: {r[0] if r else 'NO EXISTE'}")
        c = conn.execute("SELECT COUNT(*) FROM requisito WHERE plan_id LIKE 'PLAN-CS-T1%' AND ref='R0'").fetchone()[0]
        print(f"  R0 en planes T1x: {c}")

    rectificar_evento(conn, args)

    conn.close()


def rectificar_evento(conn, args):
    ya = conn.execute(
        "SELECT 1 FROM evento WHERE accion='rectificacion_evento' AND detalle LIKE '%22186%' LIMIT 1"
    ).fetchone()
    if ya:
        print("\n[evento 22186] Ya rectificado.")
        return

    evt = conn.execute("SELECT id, cuando, actor, accion, detalle FROM evento WHERE id=22186").fetchone()
    if not evt:
        print("\n[evento 22186] No existe, se omite rectificación.")
        return

    print(f"\n[evento 22186] Original: actor={evt[2]}, cuando={evt[1]}")

    if not args.dry_run:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                (ahora(), ACTOR, "rectificacion_evento",
                 None,
                 f"Rectifica evento id=22186: actor correcto es '{ACTOR}' (no 'IA:05-arquitecto-sypnose:claude-opus-4-6'); "
                 f"fecha original no era ISO 8601. Evento original inmutable (C8)."),
            )
            conn.execute("COMMIT")
            print("  + evento de rectificación insertado")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    else:
        print("  --dry-run: rectificación no escrita")


if __name__ == "__main__":
    main()
