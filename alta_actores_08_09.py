"""Alta de actores 08-caparazon y 09-sypnose-vista en tabla actor.

Detectado: emiten eventos/afirmaciones sin fila en actor.
    python3 alta_actores_08_09.py --db ~/sypnose-f1/registry.db
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/alta_actores_08_09.py"

ACTORES = [
    ("IA:08-caparazon:claude-sonnet-5", "ia", "08-caparazon", "claude-sonnet-5"),
    ("IA:08-caparazon:claude-opus-4-6", "ia", "08-caparazon", "claude-opus-4-6"),
    ("IA:09-sypnose-vista:claude-sonnet-5", "ia", "09-sypnose-vista", "claude-sonnet-5"),
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    verificar_sin_delete()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_canonicos_registrados(conn)

    if not args.dry_run:
        backup_registro(conn, db, "pre-alta-actores-08-09")

    altas = []
    for aid, clase, rol, modelo in ACTORES:
        if args.dry_run:
            print(f"  [dry-run] INSERT OR IGNORE actor {aid}")
            continue
        rc = conn.execute(
            "INSERT OR IGNORE INTO actor (id, clase, rol, modelo) VALUES (?, ?, ?, ?)",
            (aid, clase, rol, modelo),
        ).rowcount
        if rc == 1:
            altas.append(aid)
            print(f"  [alta] {aid}")
        else:
            print(f"  [ya existe] {aid}")

    if not args.dry_run and altas:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?, ?, ?, ?)",
            (ahora(), ACTOR, "alta_actor",
             f"Actores dados de alta: {', '.join(altas)}"),
        )
        conn.commit()
        print(f"\n[OK] {len(altas)} actores dados de alta")
    elif not altas and not args.dry_run:
        print("\n[OK] todos ya existían, sin cambios")

    conn.close()


if __name__ == "__main__":
    main()
