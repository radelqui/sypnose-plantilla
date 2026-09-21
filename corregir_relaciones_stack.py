"""Corregir relaciones de stack (lead item 3, ev 24970).

1. Invalidar tec:coforge:opentelemetry -usa-> mod:plantilla:...observability.py
   (la relacion apunta al esqueleto/plantilla, no al codigo real; el molde la
   reemplaza al instanciar).

2. Subir tec:coforge:prometheus-observability -usa-> mod:vmi3211028:...observability.py
   de certeza='propuesto' a certeza='observado' con evidencia de tarea 61 CUMPLE
   (ev 24019 verificador, ev 24151 firma H:carlos).

    python3 corregir_relaciones_stack.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, procedencia, registrar_evento

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"

REL_INVALIDAR = {
    "origen": "tec:coforge:opentelemetry",
    "destino": "mod:plantilla:microservicio/esqueleto/app/observability.py",
    "tipo": "usa",
}
REL_SUBIR = {
    "origen": "tec:coforge:prometheus-observability",
    "destino": "mod:vmi3211028:rag-banking-agent:microservicio/esqueleto/app/observability.py",
    "tipo": "usa",
    "nueva_certeza": "observado",
    "nueva_fuente": "tarea 61 CUMPLE ev 24019 (07-verificador) + ev 24151 (firma H:carlos)",
}


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(description="Corregir relaciones stack (lead item 3)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    r_inv = conn.execute(
        "SELECT rowid, origen, destino, tipo, certeza, fuente FROM relacion "
        "WHERE origen=? AND destino=? AND tipo=?",
        (REL_INVALIDAR["origen"], REL_INVALIDAR["destino"], REL_INVALIDAR["tipo"]),
    ).fetchone()

    r_sub = conn.execute(
        "SELECT rowid, origen, destino, tipo, certeza, fuente FROM relacion "
        "WHERE origen=? AND destino=? AND tipo=?",
        (REL_SUBIR["origen"], REL_SUBIR["destino"], REL_SUBIR["tipo"]),
    ).fetchone()

    print("=== INVALIDAR (opentelemetry -> plantilla observability.py) ===")
    if r_inv:
        print(f"  row {r_inv[0]}: {r_inv[1]} -{r_inv[3]}-> {r_inv[2]}")
        print(f"  certeza={r_inv[4]} fuente={r_inv[5]}")
        print("  -> DELETE (apunta al esqueleto, no al codigo real)")
    else:
        print("  NO ENCONTRADA")

    print()
    print("=== SUBIR (prometheus-observability -> vmi3211028 observability.py) ===")
    if r_sub:
        print(f"  row {r_sub[0]}: {r_sub[1]} -{r_sub[3]}-> {r_sub[2]}")
        print(f"  certeza={r_sub[4]} fuente={r_sub[5]}")
        if r_sub[4] == "observado":
            print("  ya observado, sin cambios")
            r_sub = None
        else:
            print(f"  -> certeza='{REL_SUBIR['nueva_certeza']}' fuente='{REL_SUBIR['nueva_fuente']}'")
    else:
        print("  NO ENCONTRADA")

    if not r_inv and not r_sub:
        print("\n[OK] sin cambios necesarios")
        conn.close()
        return

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    backup_registro(conn, db_path, "pre-rel-stack")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        detalles = []
        if r_inv:
            conn.execute(
                "DELETE FROM relacion WHERE rowid=?",
                (r_inv[0],),
            )
            detalles.append(
                f"DELETE row {r_inv[0]}: {r_inv[1]} -{r_inv[3]}-> {r_inv[2]} "
                f"(certeza={r_inv[4]}): relacion apuntaba al esqueleto/plantilla, "
                f"no al codigo instanciado; el molde la reemplaza al instanciar"
            )

        if r_sub:
            conn.execute(
                "UPDATE relacion SET certeza=?, fuente=? WHERE rowid=?",
                (REL_SUBIR["nueva_certeza"], REL_SUBIR["nueva_fuente"], r_sub[0]),
            )
            detalles.append(
                f"SUBIR row {r_sub[0]}: {r_sub[1]} -{r_sub[3]}-> {r_sub[2]} "
                f"(certeza {r_sub[4]}->'{REL_SUBIR['nueva_certeza']}'): "
                f"tarea 61 CUMPLE (ev 24019+24151)"
            )

        detalle_completo = " | ".join(detalles)
        registrar_evento(
            conn, ts, ACTOR, "correccion_relacion",
            f"stack relaciones (lead item 3, ev 24970): {detalle_completo}",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid = conn.execute(
        "SELECT max(id) FROM evento WHERE accion='correccion_relacion'"
    ).fetchone()[0]
    print(f"\n[OK] relaciones corregidas, evento {eid}")
    conn.close()


if __name__ == "__main__":
    main()
