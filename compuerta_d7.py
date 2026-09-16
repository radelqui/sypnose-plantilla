"""Fase con compuerta D7: migración, pruebas sobre copia, SQL para producción.

Ejecutar sobre el servidor (donde vive registry.db):
    python3 compuerta_d7.py --db ~/sypnose-f1/registry.db

Acciones:
  1. sqlite3 .backup a /tmp (no toca el registro vivo)
  2. Crea trigger compuerta_d7_verificador en la copia
  3. Prueba 7 casos: actores no-07 rechazados, 07 aceptados, NULL aceptado
  4. Replay del incidente: simula eventos 23170 (entrega por 05 de tarea 01)
     y 23173-23175 (entrega por 05 de tareas 03/04) — ambos deben fallar
  5. Prueba barrera Python (verificar_d7_entrega, verificar_d7_verificador)
  6. Imprime SQL de producción y vuelta atrás (DROP TRIGGER)

El lead ejecuta el trigger en producción tras CUMPLE de 07.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

from barrera import (
    actor07_valido,
    extraer_carpeta,
    verificar_d7_entrega,
    verificar_d7_verificador,
)

TRIGGER_SQL = """\
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:*');
END;"""

ROLLBACK_SQL = "DROP TRIGGER IF EXISTS compuerta_d7_verificador;"

ok = 0
fail = 0


def test(nombre: str, passed: bool, detalle: str = "") -> None:
    global ok, fail
    if passed:
        ok += 1
        print(f"  [OK] {nombre}{' — ' + detalle if detalle else ''}")
    else:
        fail += 1
        print(f"  [FALLO] {nombre}{' — ' + detalle if detalle else ''}")


def main() -> None:
    global ok, fail
    ap = argparse.ArgumentParser(description="Fase con compuerta D7")
    ap.add_argument("--db", required=True, help="ruta a registry.db (solo lectura, se hace .backup)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-d7.db", delete=False) as tmp:
        copia = Path(tmp.name)

    print(f"[1/6] backup {db_path} → {copia}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copia))
    src.backup(dst)
    src.close()
    dst.close()
    print(f"  OK ({copia.stat().st_size} bytes)")

    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[2/6] crear trigger compuerta_d7_verificador")
    conn.executescript(TRIGGER_SQL)
    print("  OK")

    print("\n[3/6] tests del trigger (7 casos)")

    tarea_test = conn.execute(
        "SELECT id FROM tarea WHERE progreso IN ('pendiente','trabajando') LIMIT 1"
    ).fetchone()
    if not tarea_test:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
            "VALUES ('TEST-COMPUERTA', 'R1', 'test-d7', 'pendiente', 'IA:03-datos-rag:claude-opus-5')"
        )
        tarea_test = conn.execute("SELECT id FROM tarea WHERE plan_id='TEST-COMPUERTA'").fetchone()
    tid = tarea_test[0]

    for actor_malo, label in [
        ("IA:05-arquitecto-sypnose:claude-opus-4-6", "05-arquitecto"),
        ("IA:03-datos-rag:claude-opus-5", "03-datos-rag"),
        ("IA:01-git-cicd:claude-sonnet-5", "01-git-cicd"),
        ("IA:04-agentes:claude-opus-5", "04-agentes"),
    ]:
        try:
            conn.execute(f"UPDATE tarea SET verificada_por=? WHERE id=?", (actor_malo, tid))
            test(f"trigger rechaza verificada_por={label}", False, "no rechazó")
        except sqlite3.IntegrityError:
            test(f"trigger rechaza verificada_por={label}", True)

    for actor_ok, label in [
        ("IA:07-verificador:claude-opus-4-6", "07 opus-4-6"),
        ("IA:07-verificador:claude-opus-5", "07 opus-5"),
    ]:
        try:
            conn.execute(f"UPDATE tarea SET verificada_por=? WHERE id=?", (actor_ok, tid))
            test(f"trigger acepta verificada_por={label}", True)
        except sqlite3.IntegrityError as e:
            test(f"trigger acepta verificada_por={label}", False, str(e))

    try:
        conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
        test("trigger acepta verificada_por=NULL", True)
    except sqlite3.IntegrityError as e:
        test("trigger acepta verificada_por=NULL", False, str(e))

    print(f"\n[4/6] replay del incidente sobre la copia")

    t39 = conn.execute("SELECT id, agente FROM tarea WHERE id=39").fetchone()
    if t39:
        conn.execute("UPDATE tarea SET progreso='pendiente', verificada_por=NULL WHERE id=39")
        try:
            conn.execute(
                "UPDATE tarea SET verificada_por='IA:05-arquitecto-sypnose:claude-opus-4-6' WHERE id=39"
            )
            test("replay 23170: trigger rechaza 05 como verificador de T07/R0 (tarea 39)", False, "no rechazó")
        except sqlite3.IntegrityError:
            test("replay 23170: trigger rechaza 05 como verificador de T07/R0 (tarea 39)", True)
    else:
        test("replay 23170: tarea 39 no existe en copia", False, "skip")

    for tid_inc, label in [(34, "T02/R0"), (40, "T08/R0"), (44, "T12/R0")]:
        row = conn.execute("SELECT id FROM tarea WHERE id=?", (tid_inc,)).fetchone()
        if row:
            conn.execute("UPDATE tarea SET progreso='pendiente', verificada_por=NULL WHERE id=?", (tid_inc,))
            try:
                conn.execute(
                    "UPDATE tarea SET verificada_por='IA:05-arquitecto-sypnose:claude-opus-4-6' WHERE id=?",
                    (tid_inc,),
                )
                test(f"replay 2317x: trigger rechaza 05 como verificador de {label} (tarea {tid_inc})", False, "no rechazó")
            except sqlite3.IntegrityError:
                test(f"replay 2317x: trigger rechaza 05 como verificador de {label} (tarea {tid_inc})", True)
        else:
            test(f"replay {label}: tarea {tid_inc} no existe", False, "skip")

    print(f"\n[5/6] tests de barrera Python")

    actor05 = "IA:05-arquitecto-sypnose:claude-opus-4-6"
    actor03 = "IA:03-datos-rag:claude-opus-5"
    actor07 = "IA:07-verificador:claude-opus-4-6"

    test("extraer_carpeta 05", extraer_carpeta(actor05) == "05-arquitecto-sypnose")
    test("extraer_carpeta 03", extraer_carpeta(actor03) == "03-datos-rag")
    test("extraer_carpeta 07", extraer_carpeta(actor07) == "07-verificador")

    if t39:
        try:
            verificar_d7_entrega(conn, 39, actor05)
            test("barrera rechaza entrega de T07 (agente=01) por actor 05", False, "no rechazó")
        except SystemExit:
            test("barrera rechaza entrega de T07 (agente=01) por actor 05", True)

    for tid_b, agente_esperado in [(34, "04-agentes"), (40, "03-datos-rag"), (44, "04-agentes")]:
        row = conn.execute("SELECT id FROM tarea WHERE id=?", (tid_b,)).fetchone()
        if row:
            try:
                verificar_d7_entrega(conn, tid_b, actor05)
                test(f"barrera rechaza entrega de tarea {tid_b} (agente={agente_esperado}) por actor 05", False)
            except SystemExit:
                test(f"barrera rechaza entrega de tarea {tid_b} (agente={agente_esperado}) por actor 05", True)

    try:
        verificar_d7_verificador(conn, actor05)
        test("barrera rechaza 05 como verificador", False)
    except SystemExit:
        test("barrera rechaza 05 como verificador", True)

    if actor07_valido(actor07, conn):
        try:
            verificar_d7_verificador(conn, actor07)
            test("barrera acepta 07 ratificado como verificador", True)
        except SystemExit as e:
            test("barrera acepta 07 ratificado como verificador", False, str(e))
    else:
        print("  [SKIP] 07 no ratificado en copia — test de aceptación omitido")

    conn.close()
    copia.unlink(missing_ok=True)

    print(f"\n[6/6] resultado")
    print(f"  {ok} OK, {fail} FALLO")
    if fail > 0:
        print("\n  HAY FALLOS — revisar antes de ejecutar en producción")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON — compuerta lista para producción")
    print("=" * 60)

    print("\n--- SQL PRODUCCIÓN (el lead ejecuta) ---")
    print(TRIGGER_SQL)

    print("\n--- SQL VUELTA ATRÁS ---")
    print(ROLLBACK_SQL)

    print("\n--- BARRERA PYTHON (ya en barrera.py) ---")
    print("verificar_d7_entrega(conn, tarea_id, actor_ejecutor)")
    print("verificar_d7_verificador(conn, verificador)")
    print("\nImportadas por entregar_tarea.py. El caparazón (stop.py) ejecuta")
    print("como el agente de la tarea, así que pasa la compuerta por diseño.")


if __name__ == "__main__":
    main()
