"""F0.4b: test de integridad coste tarea — atribución por eventos.

Verifica que:
(1) Toda tarea con coste>0 tiene al menos un evento coste_actualizado en su plan
(2) plan.coste_real = SUM(tarea.coste) para cada plan con tareas
(3) No hay tarea.coste negativo
(4) Tareas con coste>0 pertenecen a planes reales (no huérfanas)

    python3 test_coste_tarea.py --db copia-registry.db
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path


def test_coste_con_evento(conn):
    """Toda tarea con coste>0 debe tener un evento coste_actualizado o tarea_coste en su plan."""
    tareas = conn.execute(
        "SELECT id, plan_id, coste FROM tarea WHERE coste > 0"
    ).fetchall()
    fallos = []
    for tid, plan_id, coste in tareas:
        ev = conn.execute(
            "SELECT COUNT(*) FROM evento WHERE plan_id=? "
            "AND accion IN ('coste_actualizado','tarea_coste') "
            "AND detalle LIKE ?",
            (plan_id, f"tarea {tid}:%"),
        ).fetchone()[0]
        if ev == 0:
            ev_plan = conn.execute(
                "SELECT COUNT(*) FROM evento WHERE plan_id=? "
                "AND accion IN ('coste_actualizado','tarea_coste')",
                (plan_id,),
            ).fetchone()[0]
            if ev_plan == 0:
                fallos.append(
                    f"tarea {tid} ({plan_id}): coste={coste:.4f} sin evento "
                    f"coste_actualizado/tarea_coste en el plan"
                )
    return tareas, fallos


def test_plan_coste_real(conn):
    """plan.coste_real debe coincidir con SUM(tarea.coste) para cada plan."""
    planes = conn.execute(
        "SELECT p.id, p.coste_real, COALESCE(SUM(t.coste), 0) "
        "FROM plan p LEFT JOIN tarea t ON t.plan_id=p.id "
        "GROUP BY p.id "
        "HAVING ABS(p.coste_real - COALESCE(SUM(t.coste), 0)) > 0.01"
    ).fetchall()
    fallos = []
    for pid, cr, st in planes:
        if cr > 0 or st > 0:
            fallos.append(
                f"{pid}: coste_real={cr:.4f} vs SUM(tarea.coste)={st:.4f} "
                f"(diff={abs(cr - st):.4f})"
            )
    return fallos


def test_coste_no_negativo(conn):
    """Ninguna tarea debe tener coste negativo."""
    negativos = conn.execute(
        "SELECT id, plan_id, coste FROM tarea WHERE coste < 0"
    ).fetchall()
    return [(f"tarea {t[0]} ({t[1]}): coste={t[2]}") for t in negativos]


def test_coste_plan_existe(conn):
    """Tareas con coste>0 deben pertenecer a un plan existente."""
    huerfanas = conn.execute(
        "SELECT t.id, t.plan_id, t.coste FROM tarea t "
        "LEFT JOIN plan p ON p.id=t.plan_id "
        "WHERE t.coste > 0 AND p.id IS NULL"
    ).fetchall()
    return [(f"tarea {t[0]}: plan {t[1]} no existe, coste={t[2]}") for t in huerfanas]


def main():
    ap = argparse.ArgumentParser(description="F0.4b: test integridad coste tarea")
    ap.add_argument("--db", required=True, help="ruta a COPIA de registry.db")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    copia = db_path.parent / "test-copia-coste.db"
    shutil.copy2(db_path, copia)
    try:
        conn = sqlite3.connect(str(copia))
        conn.execute("PRAGMA journal_mode=WAL")

        total_fallos = 0

        print("[1/4] Coste con evento de atribución")
        tareas_coste, fallos1 = test_coste_con_evento(conn)
        if fallos1:
            for f in fallos1:
                print(f"  FALLO: {f}")
            total_fallos += len(fallos1)
        else:
            print(f"  OK: {len(tareas_coste)} tareas con coste>0, todas con evento de atribución")

        print("\n[2/4] plan.coste_real = SUM(tarea.coste)")
        fallos2 = test_plan_coste_real(conn)
        if fallos2:
            for f in fallos2:
                print(f"  FALLO: {f}")
            total_fallos += len(fallos2)
        else:
            print("  OK: coste_real coincide con suma de tareas para todos los planes")

        print("\n[3/4] Coste no negativo")
        fallos3 = test_coste_no_negativo(conn)
        if fallos3:
            for f in fallos3:
                print(f"  FALLO: {f}")
            total_fallos += len(fallos3)
        else:
            print("  OK: 0 tareas con coste negativo")

        print("\n[4/4] Tareas con coste pertenecen a plan")
        fallos4 = test_coste_plan_existe(conn)
        if fallos4:
            for f in fallos4:
                print(f"  FALLO: {f}")
            total_fallos += len(fallos4)
        else:
            print("  OK: 0 tareas huérfanas con coste")

        conn.close()

        print(f"\n{'='*60}")
        if total_fallos:
            print(f"[FALLO] {total_fallos} fallos")
            sys.exit(1)
        else:
            print("[OK] F0.4b — 4 baterías, 0 fallos")

    finally:
        copia.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
