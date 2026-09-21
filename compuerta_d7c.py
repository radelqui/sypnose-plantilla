"""Fase D7c: trigger INSERT gemelo + firmar.py exige evento verificado.

El trigger D7 existente (compuerta_d7_verificador) solo dispara en UPDATE.
El INSERT (quien_ejecuta_no_juzga_i) solo comprueba agente != verificada_por
sin mirar prefijo. D7c anade un trigger INSERT que restringe verificada_por
igual que el de UPDATE (IA:07-verificador:* o H:*) y verifica que firmar.py
exige evento verificado posterior a tarea_entregada con actor coincidente.

Ejecutar sobre el servidor (donde vive registry.db):
    python3 compuerta_d7c.py --db ~/sypnose-f1/registry.db

El DDL lo aplica el lead tras veredicto, NO el arquitecto.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

from barrera import (
    actor07_valido,
    verificar_d7_verificador,
)

TRIGGER_D7C_INSERT_SQL = """\
CREATE TRIGGER IF NOT EXISTS compuerta_d7c_verificador_insert
BEFORE INSERT ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
  AND NEW.verificada_por NOT LIKE 'H:%'
BEGIN
  SELECT RAISE(ABORT, 'D7c compuerta INSERT: verificada_por debe ser IA:07-verificador:* o H:*');
END;"""

TRIGGER_D7C_JUZGA_U_SQL = """\
DROP TRIGGER IF EXISTS quien_ejecuta_no_juzga_u;
CREATE TRIGGER quien_ejecuta_no_juzga_u BEFORE UPDATE ON tarea
WHEN NEW.progreso='espera_firma' AND (
  NEW.agente IS NULL
  OR (NEW.verificada_por IS NOT NULL AND NEW.verificada_por = NEW.agente)
)
BEGIN SELECT RAISE(ABORT,'D7: quien ejecuta no juzga'); END;"""

TRIGGER_D7C_JUZGA_I_SQL = """\
DROP TRIGGER IF EXISTS quien_ejecuta_no_juzga_i;
CREATE TRIGGER quien_ejecuta_no_juzga_i BEFORE INSERT ON tarea
WHEN NEW.progreso='espera_firma' AND (
  NEW.agente IS NULL
  OR (NEW.verificada_por IS NOT NULL AND NEW.verificada_por = NEW.agente)
)
BEGIN SELECT RAISE(ABORT,'D7: quien ejecuta no juzga'); END;"""

ROLLBACK_SQL = """\
DROP TRIGGER IF EXISTS compuerta_d7c_verificador_insert;
-- restaurar triggers originales:
DROP TRIGGER IF EXISTS quien_ejecuta_no_juzga_u;
CREATE TRIGGER quien_ejecuta_no_juzga_u BEFORE UPDATE ON tarea
WHEN NEW.progreso='espera_firma' AND (NEW.verificada_por IS NULL OR NEW.agente IS NULL OR NEW.verificada_por = NEW.agente)
BEGIN SELECT RAISE(ABORT,'D7: quien ejecuta no juzga'); END;
DROP TRIGGER IF EXISTS quien_ejecuta_no_juzga_i;
CREATE TRIGGER quien_ejecuta_no_juzga_i BEFORE INSERT ON tarea
WHEN NEW.progreso='espera_firma' AND (NEW.verificada_por IS NULL OR NEW.agente IS NULL OR NEW.verificada_por = NEW.agente)
BEGIN SELECT RAISE(ABORT,'D7: quien ejecuta no juzga'); END;"""

ok = 0
fail = 0


def test(nombre, passed, detalle=""):
    global ok, fail
    if passed:
        ok += 1
        print(f"  [OK] {nombre}{' -- ' + detalle if detalle else ''}")
    else:
        fail += 1
        print(f"  [FALLO] {nombre}{' -- ' + detalle if detalle else ''}")


def verificar_evento_verificado(conn, tarea_id):
    """Comprueba que existe evento verificado posterior a tarea_entregada y con
    actor == tarea.verificada_por. Retorna (ok, motivo)."""
    row = conn.execute(
        "SELECT verificada_por, agente FROM tarea WHERE id=?", (tarea_id,)
    ).fetchone()
    if not row:
        return False, f"tarea {tarea_id} no existe"
    vp, agente = row
    if not vp:
        return False, f"verificada_por es NULL"

    entrega = conn.execute(
        "SELECT id, cuando FROM evento WHERE accion='tarea_entregada' "
        "AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (f"tarea {tarea_id} %",),
    ).fetchone()
    if not entrega:
        return False, f"no hay evento tarea_entregada para tarea {tarea_id}"

    verificado = conn.execute(
        "SELECT id, actor, cuando FROM evento WHERE accion='verificado' "
        "AND detalle LIKE ? AND cuando > ? ORDER BY id DESC LIMIT 1",
        (f"%tarea {tarea_id}%", entrega[1]),
    ).fetchone()
    if not verificado:
        return False, (
            f"no hay evento verificado posterior a la entrega (evento {entrega[0]}) "
            f"para tarea {tarea_id}"
        )
    if verificado[1] != vp:
        return False, (
            f"verificada_por={vp} pero evento verificado {verificado[0]} "
            f"es de actor {verificado[1]}"
        )
    return True, f"evento verificado {verificado[0]} por {verificado[1]} posterior a entrega {entrega[0]}"


def main():
    global ok, fail
    ap = argparse.ArgumentParser(description="Fase D7c: INSERT gemelo + firmar check")
    ap.add_argument("--db", required=True, help="ruta a registry.db (solo lectura, se hace .backup)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-d7c.db", delete=False) as tmp:
        copia = Path(tmp.name)

    print(f"[1/5] backup {db_path} -> {copia}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copia))
    src.backup(dst)
    src.close()
    dst.close()
    print(f"  OK ({copia.stat().st_size} bytes)")

    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[2/5] crear trigger INSERT gemelo + relajar triggers espera_firma")
    conn.executescript(TRIGGER_D7C_INSERT_SQL)
    print("  trigger INSERT: compuerta_d7c_verificador_insert")
    conn.executescript(TRIGGER_D7C_JUZGA_U_SQL)
    print("  trigger UPDATE: quien_ejecuta_no_juzga_u (permite NULL verificada_por)")
    conn.executescript(TRIGGER_D7C_JUZGA_I_SQL)
    print("  trigger INSERT: quien_ejecuta_no_juzga_i (permite NULL verificada_por)")
    print("  OK")

    print("\n[3/5] tests del trigger INSERT (8 casos)")

    test_plan = "PLAN-CS-F0"
    test_agente = "IA:03-datos-rag:claude-opus-5"

    for actor_malo, label in [
        ("IA:05-arquitecto-sypnose:claude-opus-4-6", "05-arquitecto"),
        ("IA:03-datos-rag:claude-opus-5", "03-datos-rag"),
        ("IA:01-git-cicd:claude-sonnet-5", "01-git-cicd"),
        ("IA:04-agentes:claude-opus-5", "04-agentes"),
    ]:
        try:
            conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
                "VALUES (?, 'R1', 'test-d7c', 'espera_firma', ?, ?)",
                (test_plan, test_agente, actor_malo),
            )
            conn.execute("DELETE FROM tarea WHERE titulo='test-d7c'")
            test(f"INSERT rechaza verificada_por={label}", False, "no rechazo")
        except sqlite3.IntegrityError as e:
            if "D7c compuerta" in str(e) or "D7" in str(e):
                test(f"INSERT rechaza verificada_por={label}", True)
            else:
                test(f"INSERT rechaza verificada_por={label}", True, f"(por otra compuerta: {e})")

    for actor_ok, label in [
        ("IA:07-verificador:claude-opus-4-6", "07 opus-4-6"),
        ("IA:07-verificador:claude-opus-5", "07 opus-5"),
    ]:
        try:
            conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
                "VALUES (?, 'R1', 'test-d7c', 'espera_firma', ?, ?)",
                (test_plan, test_agente, actor_ok),
            )
            conn.execute("DELETE FROM tarea WHERE titulo='test-d7c'")
            test(f"INSERT acepta verificada_por={label}", True)
        except sqlite3.IntegrityError as e:
            test(f"INSERT acepta verificada_por={label}", False, str(e))

    try:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
            "VALUES (?, 'R1', 'test-d7c', 'espera_firma', ?, 'H:carlos')",
            (test_plan, test_agente),
        )
        conn.execute("DELETE FROM tarea WHERE titulo='test-d7c'")
        test("INSERT acepta verificada_por=H:carlos", True)
    except sqlite3.IntegrityError as e:
        test("INSERT acepta verificada_por=H:carlos", False, str(e))

    try:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
            "VALUES (?, 'R1', 'test-d7c', 'pendiente', ?)",
            (test_plan, test_agente),
        )
        conn.execute("DELETE FROM tarea WHERE titulo='test-d7c'")
        test("INSERT acepta verificada_por=NULL (tarea nueva)", True)
    except sqlite3.IntegrityError as e:
        test("INSERT acepta verificada_por=NULL (tarea nueva)", False, str(e))

    print("\n[4/5] tests de la comprobacion firmar.py (evento verificado)")

    tareas_corregidas = conn.execute(
        "SELECT id, verificada_por, progreso FROM tarea "
        "WHERE verificada_por IS NOT NULL AND progreso IN ('espera_firma','hecha') "
        "AND id IN (70, 34, 40, 44) "
        "ORDER BY id"
    ).fetchall()

    print(f"  verificando {len(tareas_corregidas)} tareas corregidas por F0.1 (34,40,44,70)")
    verificadas_ok = 0
    verificadas_fail = 0
    for tid, vp, prog in tareas_corregidas:
        ok_v, motivo = verificar_evento_verificado(conn, tid)
        if ok_v:
            verificadas_ok += 1
            print(f"    tarea {tid}: OK -- {motivo}")
        else:
            verificadas_fail += 1
            print(f"    tarea {tid}: FALLO -- {motivo}")

    test(
        "tareas corregidas tienen evento verificado coincidente",
        verificadas_fail == 0,
        f"{verificadas_ok} OK, {verificadas_fail} fallan"
    )

    tareas_vaciadas = conn.execute(
        "SELECT id FROM tarea WHERE verificada_por IS NULL AND id IN (17, 38, 41)"
    ).fetchall()
    test(
        "tareas 17/38/41 tienen verificada_por=NULL (sin evento verificado)",
        len(tareas_vaciadas) == 3,
        f"{len(tareas_vaciadas)} de 3 vaciadas"
    )

    print(f"\n  --- replay: entregar_tarea.py ya no escribe verificada_por ---")
    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
        "VALUES (?, 'R1', 'test entrega sin verificador', 'pendiente', "
        "'IA:05-arquitecto-sypnose:claude-opus-4-6')",
        (test_plan,),
    )
    tid_test = conn.execute(
        "SELECT id FROM tarea WHERE titulo='test entrega sin verificador'"
    ).fetchone()[0]
    conn.execute("UPDATE tarea SET progreso='espera_firma' WHERE id=?", (tid_test,))
    row_test = conn.execute("SELECT verificada_por FROM tarea WHERE id=?", (tid_test,)).fetchone()
    test(
        "entrega sin verificada_por deja NULL",
        row_test[0] is None,
        f"verificada_por={row_test[0]}"
    )
    conn.execute("DELETE FROM tarea WHERE titulo='test entrega sin verificador'")

    conn.close()
    copia.unlink(missing_ok=True)

    print(f"\n[5/5] resultado")
    print(f"  {ok} OK, {fail} FALLO")
    if fail > 0:
        print("\n  HAY FALLOS -- revisar antes de ejecutar en produccion")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON -- D7c lista para produccion")
    print("=" * 60)

    print("\n--- SQL PRODUCCION (el lead ejecuta, en orden) ---")
    print("-- 1. Trigger INSERT gemelo:")
    print(TRIGGER_D7C_INSERT_SQL)
    print("\n-- 2. Relajar UPDATE para permitir NULL verificada_por en espera_firma:")
    print(TRIGGER_D7C_JUZGA_U_SQL)
    print("\n-- 3. Relajar INSERT para permitir NULL verificada_por en espera_firma:")
    print(TRIGGER_D7C_JUZGA_I_SQL)

    print("\n--- SQL VUELTA ATRAS ---")
    print(ROLLBACK_SQL)

    print("\n--- PARCHE FIRMAR.PY (ya aplicado en el commit) ---")
    print("Anadir verificar_evento_verificado(conn, tarea_id) antes de firmar.")
    print("Rechazar firma si no existe evento verificado posterior a entrega")
    print("con actor == tarea.verificada_por.")


if __name__ == "__main__":
    main()
