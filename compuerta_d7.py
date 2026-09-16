"""Compuerta D7: trigger + pruebas sobre copia del registro.

Crea un trigger en la tabla tarea que exige:
  verificada_por LIKE 'IA:07-verificador:%' cuando se establece (non-NULL).

Prueba sobre copia (sqlite3 .backup): valida que el trigger rechaza actores
no-07 y acepta actores 07. NO escribe en el registro vivo.

El lead ejecuta el trigger en producción tras revisar la salida.

    python3 compuerta_d7.py --db ~/sypnose-f1/registry.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:*');
END;
"""

TRIGGER_SQL_CLEAN = TRIGGER_SQL.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Compuerta D7: prueba trigger sobre copia")
    ap.add_argument("--db", required=True, help="ruta a registry.db (se hace .backup, no se toca)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-test.db", delete=False) as tmp:
        copia = Path(tmp.name)

    print(f"[backup] copiando {db_path} → {copia}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copia))
    src.backup(dst)
    src.close()
    dst.close()

    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[trigger] creando trigger compuerta_d7_verificador...")
    conn.executescript(TRIGGER_SQL)
    print("[trigger] OK")

    tarea_test = conn.execute(
        "SELECT id, agente, verificada_por FROM tarea WHERE progreso IN ('pendiente','trabajando') LIMIT 1"
    ).fetchone()
    if not tarea_test:
        print("[WARN] no hay tareas pendiente/trabajando para probar; creo una temporal")
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
            "VALUES ('TEST-PLAN', 'R1', 'test-compuerta', 'pendiente', 'IA:03-datos-rag:claude-opus-5')"
        )
        tarea_test = conn.execute("SELECT id, agente, verificada_por FROM tarea WHERE plan_id='TEST-PLAN'").fetchone()
    tid, agente, ver = tarea_test
    print(f"[test] tarea {tid}, agente={agente}")

    print("\n--- TEST 1: verificada_por = actor 05 (DEBE FALLAR) ---")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:05-arquitecto-sypnose:claude-opus-4-6' WHERE id=?",
            (tid,),
        )
        print("[FALLO] trigger NO rechazó verificada_por=05 ← BUG en trigger")
        sys.exit(1)
    except sqlite3.IntegrityError as e:
        print(f"[OK] trigger rechazó: {e}")

    print("\n--- TEST 2: verificada_por = actor 03 (DEBE FALLAR) ---")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:03-datos-rag:claude-opus-5' WHERE id=?",
            (tid,),
        )
        print("[FALLO] trigger NO rechazó verificada_por=03 ← BUG en trigger")
        sys.exit(1)
    except sqlite3.IntegrityError as e:
        print(f"[OK] trigger rechazó: {e}")

    print("\n--- TEST 3: verificada_por = actor 07 (DEBE PASAR) ---")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:07-verificador:claude-opus-4-6' WHERE id=?",
            (tid,),
        )
        print("[OK] trigger aceptó verificada_por=07-verificador:claude-opus-4-6")
    except sqlite3.IntegrityError as e:
        print(f"[FALLO] trigger rechazó actor 07 válido: {e}")
        sys.exit(1)

    print("\n--- TEST 4: verificada_por = segundo 07 (DEBE PASAR) ---")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por='IA:07-verificador:claude-opus-5' WHERE id=?",
            (tid,),
        )
        print("[OK] trigger aceptó verificada_por=07-verificador:claude-opus-5")
    except sqlite3.IntegrityError as e:
        print(f"[FALLO] trigger rechazó segundo verificador 07: {e}")
        sys.exit(1)

    print("\n--- TEST 5: verificada_por = NULL (DEBE PASAR, reset) ---")
    try:
        conn.execute(
            "UPDATE tarea SET verificada_por=NULL WHERE id=?",
            (tid,),
        )
        print("[OK] trigger aceptó verificada_por=NULL (reset)")
    except sqlite3.IntegrityError as e:
        print(f"[FALLO] trigger rechazó NULL: {e}")
        sys.exit(1)

    conn.close()
    copia.unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON")
    print("=" * 60)
    print("\nSQL para que el lead ejecute en producción:")
    print("-" * 60)
    print(TRIGGER_SQL_CLEAN)
    print("-" * 60)


if __name__ == "__main__":
    main()
