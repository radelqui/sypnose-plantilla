"""Restaura estado=implementado y carga verificado_en en mcp-sypnose, mcp-kb, kb-lecciones.

La degradación anterior fue incorrecta: estas tecnologías SÍ tienen
verificación real (X4 evento 22737, X5 evento 22637). Este script
re-inserta estado=implementado y carga verificado_en con los eventos.

    python3 restaurar_implementado_verificado.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"

NODOS_VERIFICACION = {
    "tec:coforge:mcp-sypnose": "22737",
    "tec:coforge:mcp-kb": "22737",
    "tec:coforge:kb-lecciones": "22637",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    for nodo_id, ev_id in NODOS_VERIFICACION.items():
        if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
            sys.exit(f"[FALLO] nodo {nodo_id} no existe")
        if not conn.execute("SELECT 1 FROM evento WHERE id=?", (ev_id,)).fetchone():
            sys.exit(f"[FALLO] evento {ev_id} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "restaurar-implementado")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        altas_estado = []
        altas_verif = []
        verif_ya = []

        for nodo_id, ev_id in NODOS_VERIFICACION.items():
            impl = conn.execute(
                "SELECT 1 FROM afirmacion WHERE nodo_id=? AND campo='estado' "
                "AND valor='implementado' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            if not impl:
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                    "VALUES (?, 'estado', 'implementado', 'observado', "
                    "'plantilla/restaurar_implementado_verificado.py', ?, ?)",
                    (nodo_id, ACTOR, ts),
                )
                altas_estado.append(nodo_id)
                print(f"  [estado] {nodo_id} → implementado")
            else:
                print(f"  [skip] {nodo_id} ya tiene estado=implementado vigente")

            verif_existing = conn.execute(
                "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='verificado_en' "
                "AND vigente=1 AND valor != ''",
                (nodo_id,),
            ).fetchone()
            if verif_existing:
                verif_ya.append(f"{nodo_id} = {verif_existing[0]}")
                print(f"  [skip] {nodo_id} verificado_en ya tiene valor: {verif_existing[0]}")
                continue

            empty_verifs = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='verificado_en' "
                "AND vigente=1 AND valor=''",
                (nodo_id,),
            ).fetchall()
            for (aid,) in empty_verifs:
                conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))

            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                "VALUES (?, 'verificado_en', ?, 'observado', "
                "'plantilla/restaurar_implementado_verificado.py', ?, ?)",
                (nodo_id, ev_id, ACTOR, ts),
            )
            altas_verif.append(f"{nodo_id} → evento {ev_id}")
            print(f"  [verificado_en] {nodo_id} → {ev_id}")

        if altas_estado or altas_verif:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'estado_restaurado', NULL, NULL, ?)",
                (ts, ACTOR,
                 f"Corrige degradación errónea: {len(altas_estado)} estado=implementado restaurados, "
                 f"{len(altas_verif)} verificado_en cargados (X4=22737, X5=22637). "
                 f"Las verificaciones existían (07); la degradación anterior fue un error"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas estado: {len(altas_estado)} · verificado_en: {len(altas_verif)} · ya tenían: {len(verif_ya)}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
