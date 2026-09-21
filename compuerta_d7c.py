"""Fase D7c v4: INSERT gemelos + firmar exige verificado + limpieza + --aplicar.

Arreglos del veredicto 71 NO CUMPLE:
  (1) Trigger INSERT D7b auto-verificacion (mismo rol 07 no se auto-verifica)
  (2) verificar_evento_verificado() filtra plan_id
  (3) LIKE anclado: 'tarea N %' en ambas queries (evita tarea 7 vs 71)
  (4) ORDER BY+LIMIT correcto tras anclar LIKE + plan_id
  (5) --aplicar: DDL + limpieza sobre el vivo con backup .backup

    python3 compuerta_d7c.py --db ~/sypnose-f1/registry.db
    python3 compuerta_d7c.py --db ~/sypnose-f1/registry.db --aplicar
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"

TRIGGER_D7C_INSERT_SQL = """\
CREATE TRIGGER IF NOT EXISTS compuerta_d7c_verificador_insert
BEFORE INSERT ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
  AND NEW.verificada_por NOT LIKE 'H:%'
BEGIN
  SELECT RAISE(ABORT, 'D7c compuerta INSERT: verificada_por debe ser IA:07-verificador:* o H:*');
END;"""

TRIGGER_D7C_AUTO_INSERT_SQL = """\
CREATE TRIGGER IF NOT EXISTS compuerta_d7c_auto_verificacion_insert
BEFORE INSERT ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por LIKE 'IA:07-verificador:%'
  AND NEW.agente LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7c compuerta: mismo rol 07 no puede auto-verificarse (INSERT)');
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
DROP TRIGGER IF EXISTS compuerta_d7c_auto_verificacion_insert;
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
    """Comprueba evento verificado posterior a tarea_entregada con
    actor == tarea.verificada_por, filtrado por plan_id y LIKE anclado."""
    row = conn.execute(
        "SELECT verificada_por, agente, plan_id FROM tarea WHERE id=?", (tarea_id,)
    ).fetchone()
    if not row:
        return False, f"tarea {tarea_id} no existe"
    vp, agente, plan_id = row
    if not vp:
        return False, "verificada_por es NULL"

    entrega = conn.execute(
        "SELECT id, cuando FROM evento WHERE accion='tarea_entregada' "
        "AND plan_id=? AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (plan_id, f"tarea {tarea_id} %"),
    ).fetchone()
    if not entrega:
        return False, f"no hay evento tarea_entregada para tarea {tarea_id} en {plan_id}"

    verificado = conn.execute(
        "SELECT id, actor, cuando, detalle FROM evento WHERE accion='verificado' "
        "AND plan_id=? AND detalle LIKE ? AND cuando > ? ORDER BY id DESC LIMIT 1",
        (plan_id, f"tarea {tarea_id} %", entrega[1]),
    ).fetchone()
    if not verificado:
        return False, (
            f"no hay evento verificado posterior a la entrega (evento {entrega[0]}) "
            f"para tarea {tarea_id} en {plan_id}"
        )
    detalle_v = verificado[3] if len(verificado) > 3 else ""
    if detalle_v and ": NO CUMPLE" in detalle_v:
        return False, (
            f"veredicto NO CUMPLE para tarea {tarea_id} (evento {verificado[0]})"
        )
    if verificado[1] != vp:
        return False, (
            f"verificada_por={vp} pero evento verificado {verificado[0]} "
            f"es de actor {verificado[1]}"
        )
    return True, f"evento verificado {verificado[0]} por {verificado[1]} posterior a entrega {entrega[0]}"


def limpiar_espera_firma(conn):
    """Vaciar verificada_por en tareas espera_firma SIN evento verificado valido."""
    tareas = conn.execute(
        "SELECT id, verificada_por FROM tarea "
        "WHERE progreso='espera_firma' AND verificada_por IS NOT NULL"
    ).fetchall()
    if not tareas:
        return [], []

    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    vaciadas = []
    conservadas = []
    for tid, vp in tareas:
        ok_v, motivo = verificar_evento_verificado(conn, tid)
        if ok_v:
            conservadas.append(f"tarea {tid}: vp={vp} conservado ({motivo})")
        else:
            conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid,))
            vaciadas.append(f"tarea {tid}: {vp} -> NULL ({motivo})")

    if vaciadas:
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "correccion_verificada_por", "PLAN-CS-F0",
             f"D7c limpieza condicional: vaciado verificada_por en {len(vaciadas)} tareas "
             f"en espera_firma sin evento verificado valido; "
             f"conservadas {len(conservadas)} con veredicto real. "
             f"Vaciadas: {'; '.join(vaciadas)}. "
             f"Conservadas: {'; '.join(conservadas) if conservadas else 'ninguna'}."),
        )
    return vaciadas, conservadas


def aplicar_ddl(conn):
    """Aplica los 4 bloques de DDL al registro."""
    conn.executescript(TRIGGER_D7C_INSERT_SQL)
    conn.executescript(TRIGGER_D7C_AUTO_INSERT_SQL)
    conn.executescript(TRIGGER_D7C_JUZGA_U_SQL)
    conn.executescript(TRIGGER_D7C_JUZGA_I_SQL)


def main():
    global ok, fail
    ap = argparse.ArgumentParser(description="D7c v4: INSERT gemelos + firmar + limpieza + aplicar")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--aplicar", action="store_true",
                    help="aplicar DDL + limpieza al vivo (hace backup primero)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-d7c.db", delete=False) as tmp:
        copia = Path(tmp.name)

    print(f"[1/7] backup {db_path} -> {copia}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copia))
    src.backup(dst)
    src.close()
    dst.close()
    print(f"  OK ({copia.stat().st_size} bytes)")

    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[2/7] aplicar DDL (4 triggers)")
    aplicar_ddl(conn)
    print("  compuerta_d7c_verificador_insert")
    print("  compuerta_d7c_auto_verificacion_insert")
    print("  quien_ejecuta_no_juzga_u (relajado)")
    print("  quien_ejecuta_no_juzga_i (relajado)")

    conn.execute("PRAGMA foreign_keys=OFF")

    test_plan = "PLAN-CS-F0"
    test_agente = "IA:03-datos-rag:claude-opus-5"

    print("\n[3/7] tests trigger INSERT verificada_por (8 casos)")

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
            test(f"INSERT rechaza verificada_por={label}", True)

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

    print("\n[4/7] test D7b INSERT auto-verificacion (bug 1)")
    try:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
            "VALUES (?, 'R1', 'test-d7b-auto', 'espera_firma', "
            "'IA:07-verificador:claude-opus-4-6', 'IA:07-verificador:claude-opus-5')",
            (test_plan,),
        )
        conn.execute("DELETE FROM tarea WHERE titulo='test-d7b-auto'")
        test("D7b INSERT: 07-opus-4-6 agente + 07-opus-5 vp rechazado", False, "no rechazo")
    except sqlite3.IntegrityError as e:
        test("D7b INSERT: 07-opus-4-6 agente + 07-opus-5 vp rechazado", True)

    try:
        conn.execute(
            "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
            "VALUES (?, 'R1', 'test-d7b-ok', 'espera_firma', "
            "'IA:05-arquitecto-sypnose:claude-opus-4-6', 'IA:07-verificador:claude-opus-5')",
            (test_plan,),
        )
        conn.execute("DELETE FROM tarea WHERE titulo='test-d7b-ok'")
        test("D7b INSERT: 05-arquitecto agente + 07 vp aceptado", True)
    except sqlite3.IntegrityError as e:
        test("D7b INSERT: 05-arquitecto agente + 07 vp aceptado", False, str(e))

    print("\n[5/7] tests verificar_evento_verificado (bugs 2-4: plan_id + LIKE anclado)")

    ts_base = "2026-09-01T00:00:00.000Z"
    ts_ent1 = "2026-09-01T01:00:00.000Z"
    ts_ver1 = "2026-09-01T02:00:00.000Z"
    ts_ent2 = "2026-09-01T03:00:00.000Z"
    ts_ver2 = "2026-09-01T04:00:00.000Z"

    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
        "VALUES ('PLAN-TEST-LIKE', 'R1', 'tarea 7 test', 'espera_firma', "
        "'IA:03-datos-rag:claude-opus-5', 'IA:07-verificador:claude-opus-5')",
    )
    tid7 = conn.execute("SELECT id FROM tarea WHERE titulo='tarea 7 test'").fetchone()[0]

    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
        "VALUES ('PLAN-TEST-LIKE', 'R1', 'tarea 71 test', 'espera_firma', "
        "'IA:03-datos-rag:claude-opus-5', 'IA:07-verificador:claude-opus-5')",
    )
    tid71 = conn.execute("SELECT id FROM tarea WHERE titulo='tarea 71 test'").fetchone()[0]

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ent1, "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         "PLAN-TEST-LIKE", f"tarea {tid7} R1: entrega"),
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ver1, "IA:07-verificador:claude-opus-5", "verificado",
         "PLAN-TEST-LIKE", f"tarea {tid7} R1: CUMPLE"),
    )

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ent2, "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         "PLAN-TEST-LIKE", f"tarea {tid71} R1: entrega"),
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ver2, "IA:07-verificador:claude-opus-5", "verificado",
         "PLAN-TEST-LIKE", f"tarea {tid71} R1: CUMPLE"),
    )

    ok7, mot7 = verificar_evento_verificado(conn, tid7)
    test(
        f"bug3: tarea {tid7} tiene su propio veredicto (no el de {tid71})",
        ok7,
        mot7,
    )

    ok71, mot71 = verificar_evento_verificado(conn, tid71)
    test(
        f"bug3: tarea {tid71} tiene su propio veredicto (no el de {tid7})",
        ok71,
        mot71,
    )

    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
        "VALUES ('PLAN-TEST-CROSS', 'R1', 'cross-plan test', 'espera_firma', "
        "'IA:03-datos-rag:claude-opus-5', 'IA:07-verificador:claude-opus-5')",
    )
    tid_cross = conn.execute("SELECT id FROM tarea WHERE titulo='cross-plan test'").fetchone()[0]

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ent1, "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         "PLAN-TEST-CROSS", f"tarea {tid_cross} R1: entrega"),
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts_ver1, "IA:07-verificador:claude-opus-5", "verificado",
         "PLAN-WRONG", f"tarea {tid_cross} R1: CUMPLE en otro plan"),
    )

    ok_cross, mot_cross = verificar_evento_verificado(conn, tid_cross)
    test(
        "bug2: verificado en PLAN-WRONG no cuenta para PLAN-TEST-CROSS",
        not ok_cross,
        mot_cross,
    )

    conn.execute("DELETE FROM tarea WHERE titulo IN ('tarea 7 test','tarea 71 test','cross-plan test')")

    print(f"\n  --- tareas reales con veredicto conocido ---")
    for tid_check in [70, 72]:
        row = conn.execute(
            "SELECT verificada_por, progreso FROM tarea WHERE id=?", (tid_check,)
        ).fetchone()
        if row and row[0]:
            ok_r, mot_r = verificar_evento_verificado(conn, tid_check)
            test(f"tarea {tid_check} ({row[1]}) tiene veredicto valido", ok_r, mot_r)

    print("\n  --- entrega sin verificador ---")
    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
        "VALUES (?, 'R1', 'test entrega sin vp', 'pendiente', ?)",
        (test_plan, "IA:05-arquitecto-sypnose:claude-opus-4-6"),
    )
    tid_test = conn.execute("SELECT id FROM tarea WHERE titulo='test entrega sin vp'").fetchone()[0]
    conn.execute("UPDATE tarea SET progreso='espera_firma' WHERE id=?", (tid_test,))
    row_test = conn.execute("SELECT verificada_por FROM tarea WHERE id=?", (tid_test,)).fetchone()
    test("entrega sin verificada_por deja NULL", row_test[0] is None, f"verificada_por={row_test[0]}")
    conn.execute("DELETE FROM tarea WHERE titulo='test entrega sin vp'")

    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[6/7] limpieza condicional")

    pre_ef = conn.execute(
        "SELECT id, verificada_por FROM tarea WHERE progreso='espera_firma' AND verificada_por IS NOT NULL"
    ).fetchall()
    print(f"  tareas con vp no-NULL antes: {len(pre_ef)}")
    for tid, vp in pre_ef:
        ok_v, motivo = verificar_evento_verificado(conn, tid)
        print(f"    tarea {tid}: vp={vp} — {'VALIDO' if ok_v else 'SIN VEREDICTO'}: {motivo}")

    vaciadas, conservadas = limpiar_espera_firma(conn)

    print(f"  vaciadas: {len(vaciadas)}, conservadas: {len(conservadas)}")
    for v in vaciadas:
        print(f"    [VACIADA] {v}")
    for c in conservadas:
        print(f"    [CONSERVADA] {c}")

    t70_vp = conn.execute("SELECT verificada_por FROM tarea WHERE id=70").fetchone()
    t70_ok, t70_mot = verificar_evento_verificado(conn, 70)
    if t70_ok:
        test("tarea 70 con veredicto real conserva vp", t70_vp and t70_vp[0] is not None,
             f"vp={t70_vp[0] if t70_vp else '?'}, {t70_mot}")
    else:
        test("tarea 70 sin veredicto vaciada correctamente", t70_vp and t70_vp[0] is None,
             f"vp={t70_vp[0] if t70_vp else '?'}, {t70_mot}")

    t72_vp = conn.execute("SELECT verificada_por FROM tarea WHERE id=72").fetchone()
    if t72_vp:
        t72_ok, t72_mot = verificar_evento_verificado(conn, 72)
        if t72_ok:
            test("tarea 72 con veredicto real conserva vp", t72_vp[0] is not None,
                 f"vp={t72_vp[0]}, {t72_mot}")
        else:
            test("tarea 72 sin veredicto vaciada", t72_vp[0] is None,
                 f"vp={t72_vp[0]}, {t72_mot}")

    conn.close()
    copia.unlink(missing_ok=True)

    print(f"\n[7/7] resultado: {ok} OK, {fail} FALLO")
    if fail > 0:
        print("\n  HAY FALLOS")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("TODOS LOS TESTS PASARON")
    print("=" * 60)

    if args.aplicar:
        print("\n[APLICAR] DDL + limpieza sobre el vivo")
        live_conn = sqlite3.connect(str(db_path))
        live_conn.execute("PRAGMA journal_mode=WAL")
        live_conn.execute("PRAGMA foreign_keys=ON")
        live_conn.execute("PRAGMA busy_timeout=8000")

        backup_registro(live_conn, db_path, "pre-d7c-aplicar")

        live_conn.execute("BEGIN IMMEDIATE")
        try:
            aplicar_ddl(live_conn)
            print("  DDL aplicado (4 triggers)")

            vaciadas_live, conservadas_live = limpiar_espera_firma(live_conn)
            print(f"  limpieza: {len(vaciadas_live)} vaciadas, {len(conservadas_live)} conservadas")

            ts_apply = datetime.now(timezone.utc).isoformat(
                timespec="milliseconds").replace("+00:00", "Z")
            live_conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts_apply, ACTOR, "d7c_aplicado", "PLAN-CS-F0",
                 f"D7c v4 aplicado al vivo: 4 triggers "
                 f"(compuerta_d7c_verificador_insert, compuerta_d7c_auto_verificacion_insert, "
                 f"quien_ejecuta_no_juzga_u relajado, quien_ejecuta_no_juzga_i relajado). "
                 f"Limpieza: {len(vaciadas_live)} vaciadas, {len(conservadas_live)} conservadas."),
            )
            live_conn.commit()
        except Exception:
            live_conn.rollback()
            raise
        finally:
            live_conn.close()

        print(f"\n[OK] D7c v4 aplicado al vivo ({db_path})")
    else:
        print("\n--- DDL PRODUCCION (--aplicar o el lead ejecuta) ---")
        print("-- 1. Trigger INSERT verificada_por:")
        print(TRIGGER_D7C_INSERT_SQL)
        print("\n-- 2. Trigger INSERT auto-verificacion D7b:")
        print(TRIGGER_D7C_AUTO_INSERT_SQL)
        print("\n-- 3. Relajar UPDATE quien_ejecuta_no_juzga:")
        print(TRIGGER_D7C_JUZGA_U_SQL)
        print("\n-- 4. Relajar INSERT quien_ejecuta_no_juzga:")
        print(TRIGGER_D7C_JUZGA_I_SQL)


if __name__ == "__main__":
    main()
