"""Fase D7b: D7 es por ROL — tareas de 07 las verifica un humano.

Ejecutar sobre el servidor (donde vive registry.db):
    python3 compuerta_d7b.py --db ~/sypnose-f1/registry.db

Acciones:
  1. sqlite3 .backup a /tmp
  2. DROP trigger D7a, crear trigger D7b (acepta IA:07-verificador:% y H:%)
  3. Crear trigger anti-autoverificación (agente 07 + verificada_por 07 → rechazar)
  4. Tests: actores válidos/inválidos + caso clave agente-07-auto-verifica
  5. Barrera Python (verificar_d7_verificador acepta H:*, verificar_d7_auto_verificacion)
  6. SQL de producción y vuelta atrás
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
    verificar_d7_auto_verificacion,
    verificar_d7_entrega,
    verificar_d7_verificador,
)

TRIGGER_D7B_SQL = """\
DROP TRIGGER IF EXISTS compuerta_d7_verificador;
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
  AND NEW.verificada_por NOT LIKE 'H:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:* o H:*');
END;"""

TRIGGER_D7B_AUTO_SQL = """\
CREATE TRIGGER IF NOT EXISTS compuerta_d7_auto_verificacion
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por LIKE 'IA:07-verificador:%'
  AND OLD.agente LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7b compuerta: mismo rol 07 no puede auto-verificarse');
END;"""

ROLLBACK_SQL = """\
DROP TRIGGER IF EXISTS compuerta_d7_verificador;
DROP TRIGGER IF EXISTS compuerta_d7_auto_verificacion;
-- Restaurar trigger D7a original:
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:*');
END;"""

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
    ap = argparse.ArgumentParser(description="Fase D7b: D7 por ROL")
    ap.add_argument("--db", required=True, help="ruta a registry.db (solo lectura, se hace .backup)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-d7b.db", delete=False) as tmp:
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

    print("\n[2/6] drop trigger D7a, crear trigger D7b (acepta IA:07-verificador:% y H:%)")
    conn.executescript(TRIGGER_D7B_SQL)
    print("  OK")

    print("\n[3/6] crear trigger anti-autoverificación")
    conn.executescript(TRIGGER_D7B_AUTO_SQL)
    print("  OK")

    print("\n[4/6] tests de triggers")

    tarea_test = conn.execute(
        "SELECT id FROM tarea WHERE progreso IN ('pendiente','trabajando') "
        "AND agente NOT LIKE 'IA:07-verificador:%' LIMIT 1"
    ).fetchone()
    if not tarea_test:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
            "VALUES ('TEST-D7B', 'R1', 'test-d7b', 'pendiente', 'IA:03-datos-rag:claude-opus-5')"
        )
        tarea_test = conn.execute("SELECT id FROM tarea WHERE plan_id='TEST-D7B'").fetchone()
    tid = tarea_test[0]

    for actor_malo, label in [
        ("IA:05-arquitecto-sypnose:claude-opus-4-6", "05-arquitecto"),
        ("IA:03-datos-rag:claude-opus-5", "03-datos-rag"),
        ("IA:01-git-cicd:claude-sonnet-5", "01-git-cicd"),
        ("IA:04-agentes:claude-opus-5", "04-agentes"),
    ]:
        conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
        try:
            conn.execute("UPDATE tarea SET verificada_por=? WHERE id=?", (actor_malo, tid))
            test(f"trigger rechaza verificada_por={label}", False, "no rechazó")
        except sqlite3.IntegrityError:
            test(f"trigger rechaza verificada_por={label}", True)

    for actor_ok, label in [
        ("IA:07-verificador:claude-opus-4-6", "07 opus-4-6"),
        ("IA:07-verificador:claude-opus-5", "07 opus-5"),
    ]:
        conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
        try:
            conn.execute("UPDATE tarea SET verificada_por=? WHERE id=?", (actor_ok, tid))
            test(f"trigger acepta verificada_por={label} (agente no es 07)", True)
        except sqlite3.IntegrityError as e:
            test(f"trigger acepta verificada_por={label} (agente no es 07)", False, str(e))

    for humano, label in [
        ("H:carlos", "H:carlos"),
        ("H:lead", "H:lead"),
    ]:
        conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
        try:
            conn.execute("UPDATE tarea SET verificada_por=? WHERE id=?", (humano, tid))
            test(f"trigger acepta verificada_por={label}", True)
        except sqlite3.IntegrityError as e:
            test(f"trigger acepta verificada_por={label}", False, str(e))

    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
    try:
        conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
        test("trigger acepta verificada_por=NULL", True)
    except sqlite3.IntegrityError as e:
        test("trigger acepta verificada_por=NULL", False, str(e))

    print("\n  --- caso clave D7b: agente 07 + verificada_por 07 → rechazar ---")

    tarea07 = conn.execute(
        "SELECT id FROM tarea WHERE agente LIKE 'IA:07-verificador:%' LIMIT 1"
    ).fetchone()
    if not tarea07:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
            "VALUES ('TEST-D7B-07', 'R1', 'test-d7b-auto', 'pendiente', 'IA:07-verificador:claude-opus-4-6')"
        )
        tarea07 = conn.execute("SELECT id FROM tarea WHERE plan_id='TEST-D7B-07'").fetchone()
    tid07 = tarea07[0]
    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid07,))

    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:07-verificador:claude-opus-4-6' WHERE id=?",
            (tid07,),
        )
        test("trigger rechaza agente-07 + verificada_por-07 (mismo modelo)", False, "no rechazó")
    except sqlite3.IntegrityError:
        test("trigger rechaza agente-07 + verificada_por-07 (mismo modelo)", True)

    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid07,))
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:07-verificador:claude-opus-5' WHERE id=?",
            (tid07,),
        )
        test("trigger rechaza agente-07 + verificada_por-07 (modelo diferente)", False, "no rechazó")
    except sqlite3.IntegrityError:
        test("trigger rechaza agente-07 + verificada_por-07 (modelo diferente)", True)

    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid07,))
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='H:carlos' WHERE id=?",
            (tid07,),
        )
        test("trigger acepta agente-07 + verificada_por=H:carlos", True)
    except sqlite3.IntegrityError as e:
        test("trigger acepta agente-07 + verificada_por=H:carlos", False, str(e))

    print(f"\n[5/6] tests de barrera Python")

    actor05 = "IA:05-arquitecto-sypnose:claude-opus-4-6"
    actor07 = "IA:07-verificador:claude-opus-4-6"
    actor07b = "IA:07-verificador:claude-opus-5"

    try:
        verificar_d7_verificador(conn, "H:carlos")
        test("barrera acepta H:carlos como verificador", True)
    except SystemExit as e:
        test("barrera acepta H:carlos como verificador", False, str(e))

    try:
        verificar_d7_verificador(conn, actor05)
        test("barrera rechaza 05 como verificador", False, "no rechazó")
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

    try:
        verificar_d7_auto_verificacion(conn, tid07, actor07)
        test("barrera rechaza auto-verificación 07→07 (mismo modelo)", False, "no rechazó")
    except SystemExit:
        test("barrera rechaza auto-verificación 07→07 (mismo modelo)", True)

    try:
        verificar_d7_auto_verificacion(conn, tid07, actor07b)
        test("barrera rechaza auto-verificación 07→07 (diferente modelo)", False, "no rechazó")
    except SystemExit:
        test("barrera rechaza auto-verificación 07→07 (diferente modelo)", True)

    try:
        verificar_d7_auto_verificacion(conn, tid07, "H:carlos")
        test("barrera acepta verificación humana de tarea-07", True)
    except SystemExit as e:
        test("barrera acepta verificación humana de tarea-07", False, str(e))

    try:
        verificar_d7_auto_verificacion(conn, tid, actor07)
        test("barrera acepta 07 como verificador de tarea no-07", True)
    except SystemExit as e:
        test("barrera acepta 07 como verificador de tarea no-07", False, str(e))

    try:
        verificar_d7_entrega(conn, tid, actor05)
        test("barrera rechaza entrega de tarea (agente!=actor) por 05", False, "no rechazó")
    except SystemExit:
        test("barrera rechaza entrega de tarea (agente!=actor) por 05", True)

    conn.close()
    copia.unlink(missing_ok=True)

    print(f"\n[6/6] resultado")
    print(f"  {ok} OK, {fail} FALLO")
    if fail > 0:
        print("\n  HAY FALLOS — revisar antes de ejecutar en producción")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON — D7b lista para producción")
    print("=" * 60)

    print("\n--- SQL PRODUCCIÓN (el lead ejecuta) ---")
    print(TRIGGER_D7B_SQL)
    print()
    print(TRIGGER_D7B_AUTO_SQL)

    print("\n--- SQL VUELTA ATRÁS (restaura D7a) ---")
    print(ROLLBACK_SQL)

    print("\n--- BARRERA PYTHON (ya en barrera.py) ---")
    print("verificar_d7_verificador(conn, verificador)  # acepta IA:07:* y H:*")
    print("verificar_d7_auto_verificacion(conn, tarea_id, verificador)  # rechaza 07→07")


if __name__ == "__main__":
    main()
