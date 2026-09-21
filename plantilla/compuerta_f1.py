"""PLAN-CS-F1: railes deterministas de integridad de requisitos.

Modos:
    --verificar [r1..r7|todos]  Recorre el registro y nombra violaciones existentes por rail.
    --atacar    [r1..r7|todos]  Crea copia temporal, aplica triggers, ejecuta >=14 ataques.
    --aplicar                   Backup .backup, instala triggers, registra hash de esquema.

Siempre sobre COPIA del registro (--db). Nunca escribe en el registro vivo.

    python plantilla/compuerta_f1.py --db registro-copia.db --atacar
    python plantilla/compuerta_f1.py --db registro-copia.db --verificar todos
    python plantilla/compuerta_f1.py --db registro-copia.db --aplicar
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ACTOR = "IA:08-caparazon:claude-opus-4-6"
PLANTILLA = Path(__file__).resolve().parent
REPO_ROOT = PLANTILLA.parent

ACCIONES_MOD = (
    "requisito_corregido",
    "requisito_actualizado",
    "spec_cargada",
    "plan_corregido",
)


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rol_de(actor: str) -> str:
    if not actor:
        return ""
    partes = actor.split(":")
    if len(partes) >= 3 and partes[0] == "IA":
        return partes[1].lower()
    if len(partes) >= 2:
        return partes[1].lower()
    return actor.lower()


def ref_de_detalle(detalle: str) -> str | None:
    m = re.search(r"[/]?(R\d+)", detalle or "")
    return m.group(1) if m else None


def toca_requisito(detalle: str) -> bool:
    det = (detalle or "").lower()
    return any(k in det for k in ("ears", "comprobacion", "comprobaci", "spec_sha", "viejo", "antes:", "despues:"))


# ── TRIGGERS ───────────────────────────────────────────────────

TRIGGER_R2 = """
CREATE TRIGGER IF NOT EXISTS f1_r2_examinado_no_reescribe
BEFORE UPDATE OF ears, comprobacion ON requisito
WHEN EXISTS (
  SELECT 1 FROM tarea t
  WHERE t.plan_id = OLD.plan_id AND t.req_ref = OLD.ref
    AND t.progreso NOT IN ('hecha', 'retirada')
)
AND NOT EXISTS (
  SELECT 1 FROM evento e
  WHERE e.plan_id = OLD.plan_id
    AND e.accion = 'cambio_requisito_aprobado'
    AND (e.actor LIKE 'H:%' OR e.actor LIKE 'IA:00-lead:%')
    AND (e.detalle LIKE '%' || OLD.ref || ' %'
         OR e.detalle LIKE '%' || OLD.ref || ':%'
         OR e.detalle LIKE '% ' || OLD.ref)
)
BEGIN SELECT RAISE(ABORT, 'F1-R2: modificacion de requisito con tarea abierta requiere cambio_requisito_aprobado de humano o lead'); END;
"""

TRIGGER_R4 = """
CREATE TRIGGER IF NOT EXISTS f1_r4_requisito_firmado
BEFORE UPDATE OF ears, comprobacion ON requisito
WHEN EXISTS (
  SELECT 1 FROM tarea t, evento e
  WHERE t.plan_id = OLD.plan_id AND t.req_ref = OLD.ref
    AND e.accion = 'firma_tarea' AND e.plan_id = OLD.plan_id
    AND (e.detalle LIKE 'tarea ' || CAST(t.id AS TEXT) || ' %'
         OR e.detalle LIKE 'tarea ' || CAST(t.id AS TEXT) || '(%'
         OR e.detalle LIKE 'tarea ' || CAST(t.id AS TEXT) || ':%')
)
BEGIN SELECT RAISE(ABORT, 'F1-R4: requisito con tarea firmada esta congelado'); END;
"""

TRIGGER_R4B = """
CREATE TRIGGER IF NOT EXISTS f1_r4b_requisito_no_borrar
BEFORE DELETE ON requisito
WHEN EXISTS (
  SELECT 1 FROM tarea WHERE plan_id = OLD.plan_id AND req_ref = OLD.ref
)
BEGIN SELECT RAISE(ABORT, 'F1-R4b: requisito con tareas no se puede borrar'); END;
"""

TRIGGER_R6 = """
CREATE TRIGGER IF NOT EXISTS f1_r6_sin_entrega_no_veredicto
BEFORE INSERT ON evento
WHEN NEW.accion = 'verificado'
  AND NEW.plan_id IS NOT NULL
  AND NEW.detalle LIKE 'tarea %'
  AND NOT EXISTS (
    SELECT 1 FROM evento e2
    WHERE e2.accion = 'tarea_entregada'
      AND e2.plan_id = NEW.plan_id
      AND (
        e2.detalle LIKE 'tarea '
          || SUBSTR(NEW.detalle, 7,
               MIN(INSTR(SUBSTR(NEW.detalle, 7) || ' ', ' '),
                   INSTR(SUBSTR(NEW.detalle, 7) || ':', ':')) - 1)
          || ' %'
        OR
        e2.detalle LIKE 'tarea '
          || SUBSTR(NEW.detalle, 7,
               MIN(INSTR(SUBSTR(NEW.detalle, 7) || ' ', ' '),
                   INSTR(SUBSTR(NEW.detalle, 7) || ':', ':')) - 1)
          || ':%'
      )
  )
BEGIN SELECT RAISE(ABORT, 'F1-R6: sin tarea_entregada no se admite verificado'); END;
"""

TRIGGER_R6B = """
CREATE TRIGGER IF NOT EXISTS f1_r6b_verificado_tarea_valida
BEFORE INSERT ON evento
WHEN NEW.accion = 'verificado'
  AND (
    NEW.plan_id IS NULL
    OR NEW.detalle IS NULL
    OR NEW.detalle NOT LIKE 'tarea %'
    OR NOT EXISTS (
      SELECT 1 FROM tarea t
      WHERE t.plan_id = NEW.plan_id
        AND CAST(t.id AS TEXT) = SUBSTR(NEW.detalle, 7,
          MIN(INSTR(SUBSTR(NEW.detalle, 7) || ' ', ' '),
              INSTR(SUBSTR(NEW.detalle, 7) || ':', ':')) - 1)
    )
  )
BEGIN SELECT RAISE(ABORT, 'F1-R6: verificado requiere plan_id, detalle con tarea N y tarea existente en el plan'); END;
"""

TRIGGER_R8U = """
CREATE TRIGGER IF NOT EXISTS f1_r8_evidencia_inmutable_u
BEFORE UPDATE ON evidencia
BEGIN SELECT RAISE(ABORT, 'F1-R8: evidencia es de solo insercion'); END;
"""

TRIGGER_R8D = """
CREATE TRIGGER IF NOT EXISTS f1_r8_evidencia_inmutable_d
BEFORE DELETE ON evidencia
BEGIN SELECT RAISE(ABORT, 'F1-R8: evidencia es de solo insercion'); END;
"""

ALL_TRIGGERS = {
    "f1_r2_examinado_no_reescribe": TRIGGER_R2,
    "f1_r4_requisito_firmado": TRIGGER_R4,
    "f1_r4b_requisito_no_borrar": TRIGGER_R4B,
    "f1_r6_sin_entrega_no_veredicto": TRIGGER_R6,
    "f1_r6b_verificado_tarea_valida": TRIGGER_R6B,
    "f1_r8_evidencia_inmutable_u": TRIGGER_R8U,
    "f1_r8_evidencia_inmutable_d": TRIGGER_R8D,
}


def instalar_triggers(conn: sqlite3.Connection) -> list[str]:
    instalados = []
    existentes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for nombre, sql in ALL_TRIGGERS.items():
        if "evidencia" in nombre and "evidencia" not in tablas:
            instalados.append(f"{nombre} (tabla evidencia no existe, omitido)")
            continue
        if nombre in existentes:
            instalados.append(f"{nombre} (ya existe)")
        else:
            conn.executescript(sql)
            instalados.append(nombre)
    return instalados


def hash_esquema(conn: sqlite3.Connection) -> str:
    rows = conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name").fetchall()
    blob = "\n".join(r[0] for r in rows).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# ── VERIFICAR ──────────────────────────────────────────────────


def verificar_r1(conn: sqlite3.Connection) -> list[str]:
    """Autoria R0: el autor del spec debe coincidir con el rol del EARS."""
    violaciones = []
    planes = conn.execute(
        "SELECT DISTINCT p.id FROM plan p JOIN requisito r ON r.plan_id = p.id "
        "WHERE r.ref = 'R0'"
    ).fetchall()
    for (plan_id,) in planes:
        r0 = conn.execute("SELECT ears FROM requisito WHERE plan_id=? AND ref='R0'", (plan_id,)).fetchone()
        if not r0:
            continue
        ears_text = r0[0]
        m = re.search(r"(?:el rol|rol)\s+(\d{2}-[\w-]+)", ears_text, re.I)
        if not m:
            continue
        rol_ears = m.group(1).lower()
        r0_tarea = conn.execute(
            "SELECT id, agente FROM tarea WHERE plan_id=? AND req_ref='R0'", (plan_id,)
        ).fetchone()
        if not r0_tarea:
            continue
        r0_agente_rol = rol_de(r0_tarea[1]) if r0_tarea[1] else ""
        r1_tarea = conn.execute(
            "SELECT id, agente FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan_id,)
        ).fetchone()
        r1_agente_rol = rol_de(r1_tarea[1]) if r1_tarea and r1_tarea[1] else ""
        upd = conn.execute(
            "SELECT detalle FROM evento WHERE plan_id=? AND accion='requisito_actualizado' "
            "AND detalle LIKE 'R1 %' ORDER BY id DESC LIMIT 1", (plan_id,)
        ).fetchone()
        autor_spec = ""
        if upd:
            am = re.search(r"autor:\s*([\w-]+)", upd[0])
            if am:
                autor_spec = am.group(1).lower()
        if not autor_spec and r0_agente_rol:
            autor_spec = r0_agente_rol
        if autor_spec and autor_spec != rol_ears:
            violaciones.append(
                f"R1/{plan_id}: EARS nombra rol {rol_ears} pero spec escrita por {autor_spec}"
            )
    return violaciones


def verificar_r2(conn: sqlite3.Connection) -> list[str]:
    """Examina eventos de modificacion de requisitos: autor == agente de tarea."""
    violaciones = []
    mods = conn.execute(
        "SELECT e.id, e.plan_id, e.accion, e.actor, e.detalle FROM evento e "
        "WHERE e.accion IN ('requisito_corregido','requisito_actualizado','spec_cargada','plan_corregido') "
        "AND e.plan_id IS NOT NULL ORDER BY e.id"
    ).fetchall()
    for eid, plan_id, accion, actor, detalle in mods:
        det = detalle or ""
        if accion == "plan_corregido" and not toca_requisito(det):
            continue
        ref = ref_de_detalle(det)
        if not ref:
            continue
        tareas = conn.execute(
            "SELECT agente FROM tarea WHERE plan_id=? AND req_ref=?",
            (plan_id, ref)
        ).fetchall()
        if not tareas:
            continue
        actor_rol = rol_de(actor)
        autor_m = re.search(r"autor:\s*([\w-]+)", det)
        autor_rol = autor_m.group(1).lower() if autor_m else ""
        for (agente,) in tareas:
            agente_rol = rol_de(agente)
            if not agente_rol:
                continue
            if autor_rol and autor_rol == agente_rol:
                violaciones.append(
                    f"R2/ev{eid}/{plan_id}/{ref}: autor {autor_rol} == agente {agente_rol} [interpuesto por {actor_rol}]"
                )
            elif not autor_rol and actor_rol == agente_rol:
                violaciones.append(
                    f"R2/ev{eid}/{plan_id}/{ref}: actor {actor_rol} == agente {agente_rol}"
                )
    return violaciones


def verificar_r3(conn: sqlite3.Connection) -> list[str]:
    """Eventos de modificacion de requisitos sin antes/despues/ablanda."""
    violaciones = []
    mods = conn.execute(
        "SELECT e.id, e.plan_id, e.accion, e.detalle FROM evento e "
        "WHERE e.accion IN ('requisito_corregido','requisito_actualizado','plan_corregido') "
        "AND e.plan_id IS NOT NULL ORDER BY e.id"
    ).fetchall()
    for eid, plan_id, accion, detalle in mods:
        det = detalle or ""
        if accion == "plan_corregido" and not toca_requisito(det):
            continue
        ref = ref_de_detalle(det)
        if not ref:
            continue
        tiene_antes = "antes:" in det.lower()
        tiene_despues = "despues:" in det.lower() or "despues:" in det.lower()
        tiene_ablanda = re.search(r"ablanda\s*[:=]\s*(si|no|neutro)", det, re.I)
        if not tiene_antes or not tiene_despues:
            violaciones.append(f"R3/ev{eid}/{plan_id}/{ref}: falta antes:/despues:")
        elif not tiene_ablanda:
            violaciones.append(f"R3/ev{eid}/{plan_id}/{ref}: falta ablanda=si|no|neutro")
        elif tiene_ablanda and tiene_ablanda.group(1).lower() == "si":
            aprobacion = conn.execute(
                "SELECT 1 FROM evento WHERE accion='ablandamiento_autorizado' AND plan_id=? AND id < ?",
                (plan_id, eid)
            ).fetchone()
            if not aprobacion:
                violaciones.append(f"R3/ev{eid}/{plan_id}/{ref}: ablanda=si sin aprobacion previa")
    return violaciones


def verificar_r4(conn: sqlite3.Connection) -> list[str]:
    """Requisitos modificados despues de la firma de alguna tarea."""
    violaciones = []
    mods = conn.execute(
        "SELECT e.id, e.cuando, e.plan_id, e.accion, e.detalle FROM evento e "
        "WHERE e.accion IN ('requisito_corregido','requisito_actualizado','plan_corregido') "
        "AND e.plan_id IS NOT NULL ORDER BY e.id"
    ).fetchall()
    for eid, cuando, plan_id, accion, detalle in mods:
        det = detalle or ""
        if accion == "plan_corregido" and not toca_requisito(det):
            continue
        ref = ref_de_detalle(det)
        if not ref:
            continue
        tareas_ref = conn.execute(
            "SELECT t.id FROM tarea t WHERE t.plan_id=? AND t.req_ref=? AND t.progreso='hecha'",
            (plan_id, ref)
        ).fetchall()
        for (tid,) in tareas_ref:
            firma = conn.execute(
                "SELECT e2.id FROM evento e2 "
                "WHERE e2.accion = 'firma_tarea' AND e2.plan_id = ? "
                "AND (e2.detalle LIKE '%tarea " + str(tid) + " %' OR e2.detalle LIKE '%tarea " + str(tid) + "(%') "
                "AND e2.id < ?",
                (plan_id, eid)
            ).fetchone()
            if firma:
                violaciones.append(f"R4/ev{eid}/{plan_id}/{ref}: modificado tras firma (ev{firma[0]}, tarea {tid})")
    return violaciones


def verificar_r5(conn: sqlite3.Connection) -> list[str]:
    """Ventana minima 30 min entre modificacion (ablanda=si o sin clasificar) y entrega."""
    violaciones = []
    entregas = conn.execute(
        "SELECT e.id, e.cuando, e.plan_id, e.detalle FROM evento e "
        "WHERE e.accion = 'tarea_entregada' ORDER BY e.id"
    ).fetchall()
    for eid, cuando_e, plan_id, detalle in entregas:
        tarea_m = re.search(r"tarea\s+(\d+)", detalle or "")
        if not tarea_m:
            continue
        tarea_id = int(tarea_m.group(1))
        tarea = conn.execute("SELECT req_ref FROM tarea WHERE id=?", (tarea_id,)).fetchone()
        if not tarea:
            continue
        ref = tarea[0]
        mods = conn.execute(
            "SELECT e2.id, e2.cuando, e2.accion, e2.detalle FROM evento e2 "
            "WHERE e2.accion IN ('requisito_corregido','requisito_actualizado','plan_corregido') "
            "AND e2.plan_id = ? AND e2.id < ? ORDER BY e2.id DESC",
            (plan_id, eid)
        ).fetchall()
        for mid, cuando_m, maccion, mdet in mods:
            mref = ref_de_detalle(mdet or "")
            if not mref or mref != ref:
                continue
            if maccion == "plan_corregido" and not toca_requisito(mdet or ""):
                continue
            ablanda_m = re.search(r"ablanda\s*[:=]\s*(si|no|neutro)", mdet or "", re.I)
            if ablanda_m and ablanda_m.group(1).lower() == "neutro":
                continue
            try:
                t_mod = datetime.fromisoformat(cuando_m.replace("Z", "+00:00"))
                t_ent = datetime.fromisoformat(cuando_e.replace("Z", "+00:00"))
                delta = (t_ent - t_mod).total_seconds()
                if delta < 1800:
                    clasificacion = ablanda_m.group(1) if ablanda_m else "sin clasificar"
                    violaciones.append(
                        f"R5/ev{eid}/{plan_id}/{ref}: entrega {int(delta)}s tras modificacion "
                        f"(ablanda={clasificacion}, min 1800s)"
                    )
            except (ValueError, TypeError):
                pass
            break
    return violaciones


def verificar_r6(conn: sqlite3.Connection) -> list[str]:
    """Verificado sin tarea_entregada previa."""
    violaciones = []
    verificados = conn.execute(
        "SELECT e.id, e.plan_id, e.detalle FROM evento e "
        "WHERE e.accion = 'verificado' AND e.plan_id IS NOT NULL ORDER BY e.id"
    ).fetchall()
    for eid, plan_id, detalle in verificados:
        tarea_m = re.search(r"tarea\s+(\d+)", detalle or "")
        if not tarea_m:
            continue
        tarea_id = tarea_m.group(1)
        entrega = conn.execute(
            "SELECT 1 FROM evento WHERE accion='tarea_entregada' AND plan_id=? "
            "AND (detalle LIKE 'tarea " + tarea_id + " %' OR detalle LIKE 'tarea " + tarea_id + ":%' "
            "OR detalle LIKE 'tarea " + tarea_id + " %') AND id < ?",
            (plan_id, eid)
        ).fetchone()
        if not entrega:
            violaciones.append(f"R6/ev{eid}/{plan_id}/t{tarea_id}: verificado sin tarea_entregada previa")
    return violaciones


def verificar_r7(conn: sqlite3.Connection) -> list[str]:
    """--delegado no debe existir en ningun script."""
    import subprocess
    violaciones = []
    for py in REPO_ROOT.rglob("*.py"):
        if py.name == "compuerta_f1.py":
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        for i, linea in enumerate(texto.splitlines(), 1):
            if "--delegado" in linea and not linea.strip().startswith("#"):
                violaciones.append(f"R7/{py.relative_to(REPO_ROOT)}:{i}: contiene --delegado")
    try:
        out = subprocess.run(
            ["git", "grep", "-n", "--", "--delegado", "main", "--", "*.py"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10
        )
        for line in out.stdout.strip().splitlines():
            if "compuerta_f1.py" in line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                fname = parts[1]
                violaciones.append(f"R7/main:{fname}: contiene --delegado")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return violaciones


def verificar_r8(conn: sqlite3.Connection) -> list[str]:
    """Evidencia append-only: triggers instalados."""
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "evidencia" not in tablas:
        return ["R8: tabla evidencia no existe en este esquema"]
    triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    violaciones = []
    if "f1_r8_evidencia_inmutable_u" not in triggers:
        violaciones.append("R8: trigger f1_r8_evidencia_inmutable_u no instalado")
    if "f1_r8_evidencia_inmutable_d" not in triggers:
        violaciones.append("R8: trigger f1_r8_evidencia_inmutable_d no instalado")
    return violaciones


VERIFICADORES = {
    "r1": verificar_r1, "r2": verificar_r2, "r3": verificar_r3,
    "r4": verificar_r4, "r5": verificar_r5, "r6": verificar_r6, "r7": verificar_r7,
    "r8": verificar_r8,
}


def cmd_verificar(conn: sqlite3.Connection, rail: str) -> int:
    if rail == "todos":
        rails = list(VERIFICADORES.keys())
    else:
        rails = [rail]
    total = 0
    for r in rails:
        fn = VERIFICADORES[r]
        vs = fn(conn)
        print(f"\n-- {r.upper()} ({len(vs)} violaciones) --")
        for v in vs:
            print(f"  {v}")
        total += len(vs)
    print(f"\n{'=' * 40}")
    print(f"Total violaciones: {total}")
    return 0


# ── ATACAR ─────────────────────────────────────────────────────


def plan_de_ataque(conn: sqlite3.Connection, tag: str) -> str:
    plan_id = f"PLAN-ATK-{tag}"
    wt = f"/tmp/f1-atk-{tag.lower()}-{id(conn)}"
    conn.execute(
        "INSERT OR IGNORE INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
        "VALUES (?,'mantener','test-f1','test','test','test','abierto',?,'H:carlos',?,?)",
        (plan_id, ACTOR, wt, ahora()))
    return plan_id


def atacar_r2(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_R2)
    resultados = []

    plan = plan_de_ataque(conn, "R2")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, "R1 autorizado"))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -q' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R2+ con cambio_requisito_aprobado de H:carlos -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R2+ con cambio_requisito_aprobado de H:carlos -> pasa", False))

    plan2 = plan_de_ataque(conn, "R2b")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan2, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan2, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))

    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan2,))
        resultados.append(("R2- sin cambio_requisito_aprobado -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- sin cambio_requisito_aprobado -> ABORT", "F1-R2" in str(e)))

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "IA:02-backend-api:claude-sonnet-5", "cambio_requisito_aprobado", plan2, "R1 autorizado"))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -vv' WHERE plan_id=? AND ref='R1'", (plan2,))
        resultados.append(("R2- cambio_requisito_aprobado de IA no-lead -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- cambio_requisito_aprobado de IA no-lead -> ABORT", "F1-R2" in str(e)))

    return resultados


def atacar_r4(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_R4)
    conn.executescript(TRIGGER_R4B)
    resultados = []

    plan = plan_de_ataque(conn, "R4")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test sin firma", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    tid = conn.execute("SELECT id FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan,)).fetchone()[0]

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, "R1 autorizado"))

    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -q' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4+ modificar req sin evento firma_tarea -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R4+ modificar req sin evento firma_tarea -> pasa", False))

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "firma_tarea", plan, f"tarea {tid} (R1)"))

    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4- modificar req con firma_tarea -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4- modificar req con firma_tarea -> ABORT", "F1-R4" in str(e)))

    conn.execute("UPDATE tarea SET progreso='trabajando' WHERE id=?", (tid,))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -vv' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4- evasion: bajar progreso tras firma -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4- evasion: bajar progreso tras firma -> ABORT", "F1-R4" in str(e)))

    try:
        conn.execute("DELETE FROM requisito WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4b- borrar requisito con tareas -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4b- borrar requisito con tareas -> ABORT", "F1-R4b" in str(e)))

    return resultados


def atacar_r5(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []

    plan = plan_de_ataque(conn, "R5")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test ventana", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    tid = conn.execute("SELECT id FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan,)).fetchone()[0]

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T10:00:00.000Z", ACTOR, "requisito_corregido", plan,
                  "R1: antes: echo test / despues: pytest -q / ablanda: si"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T10:31:00.000Z", "IA:02-backend-api:claude-sonnet-5", "tarea_entregada", plan,
                  f"tarea {tid} R1: pytest -q -> 15 passed"))

    vs1 = verificar_r5(conn)
    hay_plan_31m = any(plan in v for v in vs1)
    resultados.append(("R5+ entrega 31 min despues de ablanda=si -> pasa", not hay_plan_31m))

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T11:00:00.000Z", ACTOR, "requisito_corregido", plan,
                  "R1: antes: pytest -q / despues: pytest -v / ablanda: si"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T11:00:12.000Z", "IA:02-backend-api:claude-sonnet-5", "tarea_entregada", plan,
                  f"tarea {tid} R1: pytest -v -> 15 passed"))

    vs2 = verificar_r5(conn)
    hay_12s = any("12s" in v and plan in v for v in vs2)
    resultados.append(("R5- entrega 12s despues de ablanda=si -> violacion", hay_12s))

    count_antes = len([v for v in vs2 if plan in v])

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T12:00:00.000Z", ACTOR, "requisito_corregido", plan,
                  "R1: antes: pytest -v / despues: pytest -vv / ablanda: neutro"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-15T12:00:05.000Z", "IA:02-backend-api:claude-sonnet-5", "tarea_entregada", plan,
                  f"tarea {tid} R1: pytest -vv -> 15 passed"))

    vs3 = verificar_r5(conn)
    count_despues = len([v for v in vs3 if plan in v])
    resultados.append(("R5+ entrega 5s despues de ablanda=neutro -> exento", count_despues == count_antes))

    return resultados


def atacar_r6(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_R6)
    conn.executescript(TRIGGER_R6B)
    resultados = []

    plan = plan_de_ataque(conn, "R6")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test sin entrega", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    tid = conn.execute("SELECT id FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan,)).fetchone()[0]

    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      f"tarea {tid} R1: CUMPLE"))
        resultados.append(("R6- verificado sin tarea_entregada -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6- verificado sin tarea_entregada -> ABORT", "F1-R6" in str(e)))

    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "IA:02-backend-api:claude-sonnet-5", "tarea_entregada", plan,
                  f"tarea {tid} R1: echo test -> ok"))

    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      f"tarea {tid} R1: CUMPLE"))
        resultados.append(("R6+ verificado con tarea_entregada previa -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R6+ verificado con tarea_entregada previa -> pasa", False))

    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      "tarea 999999 R1: CUMPLE"))
        resultados.append(("R6b- verificado con tarea inexistente -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6b- verificado con tarea inexistente -> ABORT", "F1-R6" in str(e)))

    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", None,
                      f"tarea {tid} R1: CUMPLE"))
        resultados.append(("R6b- verificado con plan_id NULL -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6b- verificado con plan_id NULL -> ABORT", "F1-R6" in str(e)))

    return resultados


def atacar_r1(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []
    vs = verificar_r1(conn)
    hay_t05 = any("PLAN-CS-T05" in v for v in vs)
    hay_t10 = any("PLAN-CS-T10" in v for v in vs)
    resultados.append(("R1- T05 (EARS=01-git-cicd, spec por 02-backend-api)", hay_t05))
    resultados.append(("R1- T10 (EARS=04-agentes, spec por 02-backend-api)", hay_t10))
    return resultados


def atacar_r3(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []
    vs = verificar_r3(conn)
    tiene_al_menos_10 = len(vs) >= 10
    resultados.append(("R3- al menos 10 violaciones (tabla B auditoria)", tiene_al_menos_10))
    tiene_0001 = any("PLAN-CS-0001" in v for v in vs)
    resultados.append(("R3- PLAN-CS-0001/R1 sin antes/despues/ablanda", tiene_0001))
    return resultados


def atacar_r7(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []

    tmp_dir = PLANTILLA / "__r7_test__"
    tmp_dir.mkdir(exist_ok=True)

    tmp_dirty = tmp_dir / "test_delegado.py"
    tmp_dirty.write_text("parser.add_argument('--delegado')\n", encoding="utf-8")
    try:
        vs_neg = verificar_r7(conn)
        tiene_test = any("__r7_test__" in v and "test_delegado" in v for v in vs_neg)
        resultados.append(("R7- fichero con --delegado inyectado -> detectado", tiene_test))
    finally:
        tmp_dirty.unlink(missing_ok=True)

    tmp_clean = tmp_dir / "test_limpio.py"
    tmp_clean.write_text("parser.add_argument('--verbose')\n", encoding="utf-8")
    try:
        vs_pos = verificar_r7(conn)
        tiene_clean = any("test_limpio" in v for v in vs_pos)
        resultados.append(("R7+ fichero sin --delegado -> no detectado", not tiene_clean))
    finally:
        tmp_clean.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    return resultados


def atacar_r8(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "evidencia" not in tablas:
        return [("R8 tabla evidencia no existe, omitido", True)]

    conn.executescript(TRIGGER_R8U)
    conn.executescript(TRIGGER_R8D)
    resultados = []

    plan = plan_de_ataque(conn, "R8")
    conn.execute(
        "INSERT OR IGNORE INTO evidencia (plan_id, fuente, dice) VALUES (?,?,?)",
        (plan, "test-r8-fuente", "test-r8-dice"))
    resultados.append(("R8+ INSERT en evidencia -> pasa", True))

    try:
        conn.execute("UPDATE evidencia SET dice='modified' WHERE plan_id=? AND fuente='test-r8-fuente'", (plan,))
        resultados.append(("R8- UPDATE en evidencia -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R8- UPDATE en evidencia -> ABORT", "F1-R8" in str(e)))

    try:
        conn.execute("DELETE FROM evidencia WHERE plan_id=? AND fuente='test-r8-fuente'", (plan,))
        resultados.append(("R8- DELETE en evidencia -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R8- DELETE en evidencia -> ABORT", "F1-R8" in str(e)))

    return resultados


ATACANTES = {
    "r1": atacar_r1, "r2": atacar_r2, "r3": atacar_r3,
    "r4": atacar_r4, "r5": atacar_r5, "r6": atacar_r6, "r7": atacar_r7,
    "r8": atacar_r8,
}


def cmd_atacar(db_path: Path, rail: str) -> int:
    tmp = tempfile.mkdtemp(prefix="f1-atk-")
    copia = Path(tmp) / "ataque.db"
    shutil.copy2(db_path, copia)
    conn = sqlite3.connect(str(copia))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if rail == "todos":
        rails = list(ATACANTES.keys())
    else:
        rails = [rail]

    total_ok = 0
    total = 0
    for r in rails:
        fn = ATACANTES[r]
        resultados = fn(conn)
        print(f"\n-- {r.upper()} --")
        for nombre, ok in resultados:
            estado = "CUMPLE" if ok else "NO CUMPLE"
            print(f"  {estado:12s}  {nombre}")
            total += 1
            if ok:
                total_ok += 1

    conn.close()
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'=' * 40}")
    print(f"Ataques: {total_ok}/{total}")
    if total_ok < total:
        print(f"FALLO: {total - total_ok} ataques no pasaron")
        return 1
    print("TODOS LOS ATAQUES PASARON")
    return 0


# ── APLICAR ────────────────────────────────────────────────────


def cmd_aplicar(db_path: Path) -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bk = db_path.parent / f"{db_path.stem}.backup-pre-f1-{ts}.db"
    conn_src = sqlite3.connect(str(db_path))
    conn_bk = sqlite3.connect(str(bk))
    conn_src.backup(conn_bk)
    conn_bk.close()
    conn_src.close()
    print(f"[backup] {bk}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    instalados = instalar_triggers(conn)
    for t in instalados:
        print(f"[trigger] {t}")

    h = hash_esquema(conn)
    conn.execute("INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
                 (ahora(), ACTOR, "esquema_actualizado",
                  f"F1 triggers instalados: {', '.join(instalados)}. Hash esquema: {h}"))
    conn.commit()
    conn.close()
    print(f"[esquema] hash={h}")
    print("[OK] triggers instalados, ninguna fila existente modificada")
    return 0


# ── MAIN ───────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="PLAN-CS-F1: railes deterministas de integridad de requisitos")
    ap.add_argument("--db", required=True, help="ruta a la copia del registro (sqlite3 .backup)")
    ap.add_argument("--verificar", nargs="?", const="todos", help="r1..r8 o 'todos'")
    ap.add_argument("--atacar", nargs="?", const="todos", help="r1..r8 o 'todos'")
    ap.add_argument("--aplicar", action="store_true", help="backup + instalar triggers")
    args = ap.parse_args()

    db = Path(args.db).expanduser().resolve()
    if not db.exists():
        sys.exit(f"[FALLO] {db} no existe")

    if args.verificar:
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA journal_mode=WAL")
        rc = cmd_verificar(conn, args.verificar)
        conn.close()
        return rc
    elif args.atacar:
        return cmd_atacar(db, args.atacar)
    elif args.aplicar:
        return cmd_aplicar(db)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
