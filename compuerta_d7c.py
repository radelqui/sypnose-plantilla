"""Fase D7c: trigger INSERT gemelo + firmar.py exige evento verificado + limpieza generica.

El trigger D7 existente (compuerta_d7_verificador) solo dispara en UPDATE.
El INSERT (quien_ejecuta_no_juzga_i) solo comprueba agente != verificada_por
sin mirar prefijo. D7c anade un trigger INSERT que restringe verificada_por
igual que el de UPDATE (IA:07-verificador:* o H:*) y verifica que firmar.py
exige evento verificado posterior a tarea_entregada con actor coincidente.

Tras aplicar el DDL, limpieza generica: toda tarea en espera_firma tiene su
verificada_por vaciado a NULL (bajo el viejo regimen lo precargaba
entregar_tarea.py; bajo D7c, verificada_por empieza vacio y lo llena 07).

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


def limpiar_espera_firma(conn):
    """Limpieza condicional post-D7c: vaciar verificada_por en tareas espera_firma
    SIN evento verificado valido.

    Condicional: solo vacia si NO existe evento verificado cuyo actor ==
    tarea.verificada_por, posterior a la ultima tarea_entregada de esa tarea.
    Tareas con veredicto real ya emitido conservan su verificada_por.
    """
    tareas = conn.execute(
        "SELECT id, verificada_por FROM tarea "
        "WHERE progreso='espera_firma' AND verificada_por IS NOT NULL"
    ).fetchall()
    if not tareas:
        return [], []

    from datetime import datetime, timezone
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
            (ts, "IA:05-arquitecto-sypnose:claude-opus-4-6", "correccion_verificada_por",
             "PLAN-CS-F0",
             f"D7c limpieza condicional: vaciado verificada_por en {len(vaciadas)} tareas "
             f"en espera_firma sin evento verificado valido; "
             f"conservadas {len(conservadas)} con veredicto real. "
             f"Vaciadas: {'; '.join(vaciadas)}. "
             f"Conservadas: {'; '.join(conservadas) if conservadas else 'ninguna'}."),
        )
    return vaciadas, conservadas


def main():
    global ok, fail
    ap = argparse.ArgumentParser(description="Fase D7c: INSERT gemelo + firmar check + limpieza")
    ap.add_argument("--db", required=True, help="ruta a registry.db (solo lectura, se hace .backup)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    with tempfile.NamedTemporaryFile(suffix="-compuerta-d7c.db", delete=False) as tmp:
        copia = Path(tmp.name)

    print(f"[1/6] backup {db_path} -> {copia}")
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(copia))
    src.backup(dst)
    src.close()
    dst.close()
    print(f"  OK ({copia.stat().st_size} bytes)")

    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("\n[2/6] crear trigger INSERT gemelo + relajar triggers espera_firma")
    conn.executescript(TRIGGER_D7C_INSERT_SQL)
    print("  trigger INSERT: compuerta_d7c_verificador_insert")
    conn.executescript(TRIGGER_D7C_JUZGA_U_SQL)
    print("  trigger UPDATE: quien_ejecuta_no_juzga_u (permite NULL verificada_por)")
    conn.executescript(TRIGGER_D7C_JUZGA_I_SQL)
    print("  trigger INSERT: quien_ejecuta_no_juzga_i (permite NULL verificada_por)")
    print("  OK")

    print("\n[3/6] tests del trigger INSERT (8 casos)")

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

    print("\n[4/6] tests de la comprobacion firmar.py (evento verificado)")

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

    print("\n[5/6] limpieza condicional: vaciar verificada_por SIN veredicto valido")

    pre_ef = conn.execute(
        "SELECT id, verificada_por FROM tarea WHERE progreso='espera_firma' AND verificada_por IS NOT NULL"
    ).fetchall()
    print(f"  tareas en espera_firma con vp no-NULL antes de limpieza: {len(pre_ef)}")
    for tid, vp in pre_ef:
        ok_v, motivo = verificar_evento_verificado(conn, tid)
        print(f"    tarea {tid}: verificada_por={vp} — {'VALIDO' if ok_v else 'SIN VEREDICTO'}: {motivo}")

    vaciadas, conservadas = limpiar_espera_firma(conn)

    print(f"  vaciadas: {len(vaciadas)}, conservadas: {len(conservadas)}")
    for v in vaciadas:
        print(f"    [VACIADA] {v}")
    for c in conservadas:
        print(f"    [CONSERVADA] {c}")

    # (a) tarea en espera_firma SIN veredicto -> NULL (tarea 71 no tiene verificado)
    t71_vp = conn.execute("SELECT verificada_por FROM tarea WHERE id=71").fetchone()
    test(
        "(a) espera_firma SIN veredicto -> NULL (tarea 71)",
        t71_vp and t71_vp[0] is None,
        f"verificada_por={t71_vp[0] if t71_vp else '?'}"
    )

    # (b) tarea en espera_firma CON veredicto real posterior -> conserva
    # Tarea 70 tiene verificado 24951 posterior a entrega 24686 del mismo actor
    t70_vp = conn.execute("SELECT verificada_por FROM tarea WHERE id=70").fetchone()
    t70_ok, t70_mot = verificar_evento_verificado(conn, 70)
    if t70_ok:
        test(
            "(b) espera_firma CON veredicto real -> conserva (tarea 70)",
            t70_vp and t70_vp[0] is not None,
            f"verificada_por={t70_vp[0] if t70_vp else '?'}, {t70_mot}"
        )
    else:
        test(
            "(b) espera_firma CON veredicto real -> conserva (tarea 70)",
            t70_vp and t70_vp[0] is None,
            f"verificada_por={t70_vp[0] if t70_vp else '?'}, sin veredicto valido: {t70_mot} — vaciada correctamente"
        )

    # (c) simular re-entrega: insertar tarea con veredicto ANTERIOR a la ultima entrega -> NULL
    from datetime import datetime, timezone
    ts_test = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
        "VALUES (?, 'R1', 'test-reentrega', 'pendiente', "
        "'IA:03-datos-rag:claude-opus-5', 'IA:07-verificador:claude-opus-5')",
        (test_plan,),
    )
    tid_re = conn.execute("SELECT id FROM tarea WHERE titulo='test-reentrega'").fetchone()[0]
    # primera entrega
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        ("2026-09-01T00:00:00.000Z", "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         test_plan, f"tarea {tid_re} R1: primera entrega"),
    )
    # verificado posterior a primera entrega
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        ("2026-09-02T00:00:00.000Z", "IA:07-verificador:claude-opus-5", "verificado",
         test_plan, f"tarea {tid_re} R1: CUMPLE primera"),
    )
    # re-entrega posterior al verificado
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        ("2026-09-03T00:00:00.000Z", "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         test_plan, f"tarea {tid_re} R1: RE-ENTREGA"),
    )
    conn.execute("UPDATE tarea SET progreso='espera_firma' WHERE id=?", (tid_re,))
    # ahora verificado es ANTERIOR a la ultima entrega
    ok_re, mot_re = verificar_evento_verificado(conn, tid_re)
    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid_re,))
    test(
        "(c) veredicto ANTERIOR a re-entrega -> NULL",
        not ok_re,
        f"{mot_re}"
    )
    conn.execute("DELETE FROM tarea WHERE titulo='test-reentrega'")

    # (d) verificada_por apunta a actor distinto del verificado real -> NULL
    conn.execute(
        "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente, verificada_por) "
        "VALUES (?, 'R1', 'test-actor-distinto', 'pendiente', "
        "'IA:03-datos-rag:claude-opus-5', 'IA:07-verificador:claude-opus-4-6')",
        (test_plan,),
    )
    tid_dist = conn.execute("SELECT id FROM tarea WHERE titulo='test-actor-distinto'").fetchone()[0]
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        ("2026-09-01T00:00:00.000Z", "IA:03-datos-rag:claude-opus-5", "tarea_entregada",
         test_plan, f"tarea {tid_dist} R1: entrega"),
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        ("2026-09-02T00:00:00.000Z", "IA:07-verificador:claude-opus-5", "verificado",
         test_plan, f"tarea {tid_dist} R1: CUMPLE por opus-5"),
    )
    conn.execute("UPDATE tarea SET progreso='espera_firma' WHERE id=?", (tid_dist,))
    ok_dist, mot_dist = verificar_evento_verificado(conn, tid_dist)
    conn.execute("UPDATE tarea SET verificada_por=NULL WHERE id=?", (tid_dist,))
    test(
        "(d) vp=opus-4-6 pero verificado por opus-5 -> NULL",
        not ok_dist,
        f"{mot_dist}"
    )
    conn.execute("DELETE FROM tarea WHERE titulo='test-actor-distinto'")

    # (e) tarea hecha con veredicto real conserva verificada_por
    t34_vp = conn.execute("SELECT verificada_por FROM tarea WHERE id=34").fetchone()
    test(
        "(e) tarea 34 (hecha, con veredicto real) conserva verificada_por",
        t34_vp and t34_vp[0] is not None,
        f"verificada_por={t34_vp[0] if t34_vp else '?'}"
    )

    conn.close()
    copia.unlink(missing_ok=True)

    print(f"\n[6/6] resultado")
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
    print("\n-- 4. Limpieza condicional (vaciar vp sin veredicto valido en espera_firma):")
    print("--    python3 compuerta_d7c.py aplica limpiar_espera_firma() automaticamente")
    print("--    Solo vacia tareas SIN evento verificado valido; conserva las que tienen veredicto real")

    print("\n--- SQL VUELTA ATRAS ---")
    print(ROLLBACK_SQL)

    print("\n--- PARCHE FIRMAR.PY (ya aplicado en el commit) ---")
    print("Anadir verificar_evento_verificado(conn, tarea_id) antes de firmar.")
    print("Rechazar firma si no existe evento verificado posterior a entrega")
    print("con actor == tarea.verificada_por.")


if __name__ == "__main__":
    main()
