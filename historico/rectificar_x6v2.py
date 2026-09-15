"""Rectificación X6v2: restaura filas de evidencia modificadas en sitio.

(1) Restaura evidencia 173 (T06): fuente 'INVALIDA:07-verificador/...' → original.
(2) Restaura gh:run:34870628891 en T07 y T14: quita prefijo INVALIDA:.
(3) [RETIRADO] El DELETE de filas 190-194 era incorrecto — violaba la regla no-DELETE.
    Las filas fueron reinsertadas por restaurar_evidencia_x6v2.py.
    El filtro de evento:<id> en validar_fuente ya descarta las no cualificadas.
(4) Evento de rectificación sobre el 22597 (texto "07 la invalida" incorrecto).

Guardia idempotente: evento 'rectificar_x6v2'.

    python3 historico/rectificar_x6v2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
EVENTO_GUARDIA = "rectificar_x6v2"

EVIDENCIA_173_INVALIDA = "INVALIDA:07-verificador/VERIFICACION.md@c5d232412bce"
EVIDENCIA_173_ORIGINAL = "07-verificador/VERIFICACION.md@c5d232412bce"

GH_RUN_OLD_INVALIDA = "INVALIDA:gh:run:34870628891"
GH_RUN_OLD_ORIGINAL = "gh:run:34870628891"

EVENTO_RECTIFICAR = 22597


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    ya = conn.execute("SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA,)).fetchone()
    if ya:
        print(f"[idempotente] evento {EVENTO_GUARDIA} ya existe. 0 cambios.")
        conn.close()
        return

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    if args.dry_run:
        print(f"[dry-run] restaurar evidencia 173: {EVIDENCIA_173_INVALIDA} → {EVIDENCIA_173_ORIGINAL}")
        print(f"[dry-run] restaurar T07: {GH_RUN_OLD_INVALIDA} → {GH_RUN_OLD_ORIGINAL}")
        print(f"[dry-run] restaurar T14: {GH_RUN_OLD_INVALIDA} → {GH_RUN_OLD_ORIGINAL}")
        print(f"[dry-run] rectificar evento {EVENTO_RECTIFICAR}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "rect-x6v2")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()

        # (1) Restaurar evidencia 173
        rc = conn.execute(
            "UPDATE evidencia SET fuente=? WHERE plan_id='PLAN-CS-T06' AND fuente=?",
            (EVIDENCIA_173_ORIGINAL, EVIDENCIA_173_INVALIDA),
        ).rowcount
        print(f"[restaurada] evidencia 173: {rc} filas → {EVIDENCIA_173_ORIGINAL}")

        # (2) Restaurar gh:run:34870628891 en T07 y T14
        for plan in ("PLAN-CS-T07", "PLAN-CS-T14"):
            rc2 = conn.execute(
                "UPDATE evidencia SET fuente=? WHERE plan_id=? AND fuente=?",
                (GH_RUN_OLD_ORIGINAL, plan, GH_RUN_OLD_INVALIDA),
            ).rowcount
            print(f"[restaurada] {plan}: {rc2} filas → {GH_RUN_OLD_ORIGINAL}")

        # (3) [RETIRADO — DELETE era incorrecto; filas reinsertadas por restaurar_evidencia_x6v2.py]

        # (4) Rectificación del evento 22597
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "rectificacion", "PLAN-CS-T06",
             f"Rectificación evento {EVENTO_RECTIFICAR}: texto '07 la invalida' incorrecto. "
             "05 no puede atribuir acciones a otro actor ni modificar filas de evidencia en sitio. "
             "La invalidación de la evidencia 173 la debe hacer 07 con INVALIDA:rowid:173 + su evento."),
        )
        print(f"[rectificacion] evento {EVENTO_RECTIFICAR}")

        # Evento guardia
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ts, ACTOR, EVENTO_GUARDIA,
             f"restaurada ev173 + gh:run T07/T14, eliminados {eliminados} evento: no cualificados T06, rectificado ev{EVENTO_RECTIFICAR}"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("[OK] rectificación X6v2 aplicada")


if __name__ == "__main__":
    main()
