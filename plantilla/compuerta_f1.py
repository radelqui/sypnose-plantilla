"""PLAN-CS-F1: railes deterministas de integridad de requisitos.

Modos:
    --verificar [r1..r8|rastro|todos]  Recorre el registro y nombra violaciones existentes por rail.
    --atacar    [r1..r8|rastro|todos]  Crea copia temporal, aplica triggers, ejecuta ataques.
    --aplicar                          Backup .backup, instala triggers, registra hash de esquema.

Siempre sobre COPIA del registro (--db). Nunca escribe en el registro vivo.

    python plantilla/compuerta_f1.py --db registro-copia.db --atacar
    python plantilla/compuerta_f1.py --db registro-copia.db --verificar todos
    python plantilla/compuerta_f1.py --db registro-copia.db --aplicar
"""
from __future__ import annotations

import argparse
import hashlib
import os
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

# R2: approval required — must have fichero= sha256=, be consumed (posterior to
# last requisito_modificado), and be < 24h old. Blocks without valid approval.
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
    AND e.detalle LIKE '%fichero=%'
    AND e.detalle LIKE '%sha256=%'
    AND e.cuando > COALESCE(
      (SELECT MAX(e2.cuando) FROM evento e2
       WHERE e2.plan_id = OLD.plan_id
         AND e2.accion = 'requisito_modificado'
         AND e2.detalle LIKE 'ref=' || OLD.ref || ' %'),
      '2000-01-01T00:00:00.000Z'
    )
    AND e.cuando > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-24 hours') || 'Z'
)
BEGIN SELECT RAISE(ABORT,
  'F1-R2: requiere cambio_requisito_aprobado vigente (fichero= sha256=, posterior al ultimo cambio, <24h)');
END;
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

# F3/F4 evasion: cannot pivot req_ref or plan_id on a delivered/signed tarea
TRIGGER_R4C = """
CREATE TRIGGER IF NOT EXISTS f1_r4c_tarea_ref_congelada
BEFORE UPDATE OF req_ref, plan_id ON tarea
WHEN EXISTS (
  SELECT 1 FROM evento e
  WHERE (e.accion = 'tarea_entregada' OR e.accion = 'firma_tarea')
    AND e.plan_id = OLD.plan_id
    AND (e.detalle LIKE 'tarea ' || CAST(OLD.id AS TEXT) || ' %'
         OR e.detalle LIKE 'tarea ' || CAST(OLD.id AS TEXT) || ':%')
)
BEGIN SELECT RAISE(ABORT,
  'F1-R4c: tarea entregada o firmada no permite cambiar req_ref ni plan_id');
END;
"""

# R6 only governs "tarea N" format (N integer followed by space or colon).
# Other verdicts (views, measurements, plans) pass through freely.
# Limitation F5: a detalle could prefix "tarea 79" but judge tarea 80 in the
# body text; firmar.py anchors the format, so this is a known limit.
TRIGGER_R6 = """
CREATE TRIGGER IF NOT EXISTS f1_r6_sin_entrega_no_veredicto
BEFORE INSERT ON evento
WHEN NEW.accion = 'verificado'
  AND NEW.plan_id IS NOT NULL
  AND NEW.detalle LIKE 'tarea %'
  AND SUBSTR(NEW.detalle, 7, 1) BETWEEN '0' AND '9'
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

# R6b: for "tarea N" format, validates the tarea exists in that plan
TRIGGER_R6B = """
CREATE TRIGGER IF NOT EXISTS f1_r6b_verificado_tarea_valida
BEFORE INSERT ON evento
WHEN NEW.accion = 'verificado'
  AND NEW.detalle LIKE 'tarea %'
  AND SUBSTR(NEW.detalle, 7, 1) BETWEEN '0' AND '9'
  AND (
    NEW.plan_id IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM tarea t
      WHERE t.plan_id = NEW.plan_id
        AND CAST(t.id AS TEXT) = SUBSTR(NEW.detalle, 7,
          MIN(INSTR(SUBSTR(NEW.detalle, 7) || ' ', ' '),
              INSTR(SUBSTR(NEW.detalle, 7) || ':', ':')) - 1)
    )
  )
BEGIN SELECT RAISE(ABORT,
  'F1-R6b: verificado con formato tarea N requiere plan_id y tarea existente en el plan');
END;
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

# PRINCIPIO 3: the database leaves the trail — AFTER triggers record full text
TRIGGER_RASTRO_INSERT = """
CREATE TRIGGER IF NOT EXISTS f1_rastro_requisito_insertado
AFTER INSERT ON requisito
BEGIN
  INSERT INTO evento (cuando, actor, accion, plan_id, detalle)
  VALUES (
    strftime('%Y-%m-%dT%H:%M:%f', 'now') || 'Z',
    'S:registro',
    'requisito_insertado',
    NEW.plan_id,
    'ref=' || NEW.ref
    || ' ears=' || NEW.ears
    || ' comprobacion=' || NEW.comprobacion
  );
END;
"""

TRIGGER_RASTRO_UPDATE = """
CREATE TRIGGER IF NOT EXISTS f1_rastro_requisito_modificado
AFTER UPDATE OF ears, comprobacion ON requisito
BEGIN
  INSERT INTO evento (cuando, actor, accion, plan_id, detalle)
  VALUES (
    strftime('%Y-%m-%dT%H:%M:%f', 'now') || 'Z',
    'S:registro',
    'requisito_modificado',
    NEW.plan_id,
    'ref=' || NEW.ref
    || ' antes_ears=' || OLD.ears
    || ' despues_ears=' || NEW.ears
    || ' antes_comprobacion=' || OLD.comprobacion
    || ' despues_comprobacion=' || NEW.comprobacion
  );
END;
"""

ALL_TRIGGERS = {
    "f1_r2_examinado_no_reescribe": TRIGGER_R2,
    "f1_r4_requisito_firmado": TRIGGER_R4,
    "f1_r4b_requisito_no_borrar": TRIGGER_R4B,
    "f1_r4c_tarea_ref_congelada": TRIGGER_R4C,
    "f1_r6_sin_entrega_no_veredicto": TRIGGER_R6,
    "f1_r6b_verificado_tarea_valida": TRIGGER_R6B,
    "f1_r8_evidencia_inmutable_u": TRIGGER_R8U,
    "f1_r8_evidencia_inmutable_d": TRIGGER_R8D,
    "f1_rastro_requisito_insertado": TRIGGER_RASTRO_INSERT,
    "f1_rastro_requisito_modificado": TRIGGER_RASTRO_UPDATE,
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
    violaciones = []
    for py in REPO_ROOT.rglob("*.py"):
        if py.name == "compuerta_f1.py":
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        for i, linea in enumerate(texto.splitlines(), 1):
            if "--delegado" in linea and not linea.strip().startswith("#"):
                violaciones.append(f"R7/{py.relative_to(REPO_ROOT)}:{i}: contiene --delegado")
    try:
        import subprocess
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
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "evidencia" not in tablas:
        return ["R8: tabla evidencia no existe en este esquema"]
    triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    falta = []
    if "f1_r8_evidencia_inmutable_u" not in triggers:
        falta.append("f1_r8_evidencia_inmutable_u")
    if "f1_r8_evidencia_inmutable_d" not in triggers:
        falta.append("f1_r8_evidencia_inmutable_d")
    if falta:
        return [f"R8: triggers de evidencia no instalados ({', '.join(falta)})"]
    return []


def verificar_rastro(conn: sqlite3.Connection) -> list[str]:
    triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
    falta = []
    if "f1_rastro_requisito_insertado" not in triggers:
        falta.append("f1_rastro_requisito_insertado")
    if "f1_rastro_requisito_modificado" not in triggers:
        falta.append("f1_rastro_requisito_modificado")
    if falta:
        return [f"RASTRO: triggers AFTER no instalados ({', '.join(falta)})"]
    return []


VERIFICADORES = {
    "r1": verificar_r1, "r2": verificar_r2, "r3": verificar_r3,
    "r4": verificar_r4, "r5": verificar_r5, "r6": verificar_r6,
    "r7": verificar_r7, "r8": verificar_r8, "rastro": verificar_rastro,
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


HASH64 = "a" * 64


def plan_de_ataque(conn: sqlite3.Connection, tag: str) -> str:
    plan_id = f"PLAN-ATK-{tag}"
    wt = f"/tmp/f1-atk-{tag.lower()}-{id(conn)}"
    conn.execute(
        "INSERT OR IGNORE INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
        "VALUES (?,'mantener','test-f1','test','test','test','abierto',?,'H:carlos',?,?)",
        (plan_id, ACTOR, wt, ahora()))
    return plan_id


def _aprobacion_detalle(ref: str) -> str:
    return f"{ref} fichero=Requerimientos/F1/test.md sha256={HASH64}"


def atacar_r1(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []
    vs = verificar_r1(conn)

    total_planes = len(conn.execute(
        "SELECT DISTINCT plan_id FROM requisito WHERE ref='R0'"
    ).fetchall())
    count_vs = len(vs)
    resultados.append((
        f"R1+ planes correctos pasan ({total_planes - count_vs} de {total_planes})",
        count_vs < total_planes
    ))

    hay_t05 = any("PLAN-CS-T05" in v for v in vs)
    hay_t10 = any("PLAN-CS-T10" in v for v in vs)
    resultados.append(("R1- T05 (EARS=01-git-cicd, spec por 02-backend-api)", hay_t05))
    resultados.append(("R1- T10 (EARS=04-agentes, spec por 02-backend-api)", hay_t10))
    return resultados


def atacar_r2(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_R2)
    conn.executescript(TRIGGER_RASTRO_INSERT)
    conn.executescript(TRIGGER_RASTRO_UPDATE)
    resultados = []

    # R2+ proper approval with fichero= sha256= format
    plan = plan_de_ataque(conn, "R2")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, _aprobacion_detalle("R1")))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -q' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R2+ aprobacion con fichero= sha256= -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R2+ aprobacion con fichero= sha256= -> pasa", False))

    # R2- consumed: second UPDATE, approval is before requisito_modificado from first UPDATE
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R2- aprobacion consumida (segundo UPDATE) -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- aprobacion consumida (segundo UPDATE) -> ABORT", "F1-R2" in str(e)))

    # R2- no approval at all
    plan2 = plan_de_ataque(conn, "R2b")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan2, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan2, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan2,))
        resultados.append(("R2- sin aprobacion -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- sin aprobacion -> ABORT", "F1-R2" in str(e)))

    # R2- wrong format (no fichero= sha256=)
    plan3 = plan_de_ataque(conn, "R2c")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan3, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan3, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan3, "R1 autorizado"))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan3,))
        resultados.append(("R2- aprobacion sin fichero= sha256= -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- aprobacion sin fichero= sha256= -> ABORT", "F1-R2" in str(e)))

    # R2- expired approval (>24h old)
    plan4 = plan_de_ataque(conn, "R2d")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan4, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan4, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 ("2026-09-01T10:00:00.000Z", "H:carlos", "cambio_requisito_aprobado", plan4,
                  _aprobacion_detalle("R1")))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan4,))
        resultados.append(("R2- aprobacion expirada (>24h) -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- aprobacion expirada (>24h) -> ABORT", "F1-R2" in str(e)))

    # R2- approval from non-lead IA
    plan5 = plan_de_ataque(conn, "R2e")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan5, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan5, "R1", "test", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "IA:02-backend-api:claude-sonnet-5", "cambio_requisito_aprobado", plan5,
                  _aprobacion_detalle("R1")))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -vv' WHERE plan_id=? AND ref='R1'", (plan5,))
        resultados.append(("R2- aprobacion de IA no-lead -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R2- aprobacion de IA no-lead -> ABORT", "F1-R2" in str(e)))

    return resultados


def atacar_r3(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []
    vs = verificar_r3(conn)

    plan = plan_de_ataque(conn, "R3")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), ACTOR, "requisito_corregido", plan,
                  "R1: antes: echo test / despues: pytest -q / ablanda: neutro"))
    vs_after = verificar_r3(conn)
    hay_plan = any(plan in v for v in vs_after)
    resultados.append(("R3+ evento bien formado (antes/despues/ablanda) -> no violacion", not hay_plan))

    tiene_al_menos_10 = len(vs) >= 10
    resultados.append(("R3- al menos 10 violaciones (tabla B auditoria)", tiene_al_menos_10))
    tiene_0001 = any("PLAN-CS-0001" in v for v in vs)
    resultados.append(("R3- PLAN-CS-0001/R1 sin antes/despues/ablanda", tiene_0001))
    return resultados


def atacar_r4(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_R2)
    conn.executescript(TRIGGER_R4)
    conn.executescript(TRIGGER_R4B)
    conn.executescript(TRIGGER_R4C)
    conn.executescript(TRIGGER_RASTRO_INSERT)
    conn.executescript(TRIGGER_RASTRO_UPDATE)
    resultados = []

    plan = plan_de_ataque(conn, "R4")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, "R1", "test ears", "echo test"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, "R1", "test sin firma", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    tid = conn.execute("SELECT id FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan,)).fetchone()[0]

    # R4+: no firma → passes (with R2 approval)
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, _aprobacion_detalle("R1")))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -q' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4+ modificar req sin evento firma_tarea -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R4+ modificar req sin evento firma_tarea -> pasa", False))

    # Insert firma
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "firma_tarea", plan, f"tarea {tid} (R1)"))

    # R4-: with firma → ABORT (fresh approval to bypass R2 consumption)
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, _aprobacion_detalle("R1")))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -v' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4- modificar req con firma_tarea -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4- modificar req con firma_tarea -> ABORT", "F1-R4" in str(e)))

    # Evasion: downgrade progreso → firma event persists → still ABORT
    conn.execute("UPDATE tarea SET progreso='trabajando' WHERE id=?", (tid,))
    try:
        conn.execute("UPDATE requisito SET comprobacion='pytest -vv' WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4- evasion: bajar progreso tras firma -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4- evasion: bajar progreso tras firma -> ABORT", "F1-R4" in str(e)))

    # R4b: DELETE requisito with tareas
    try:
        conn.execute("DELETE FROM requisito WHERE plan_id=? AND ref='R1'", (plan,))
        resultados.append(("R4b- borrar requisito con tareas -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4b- borrar requisito con tareas -> ABORT", "F1-R4b" in str(e)))

    # R4c-: change req_ref on signed tarea → ABORT
    try:
        conn.execute("UPDATE tarea SET req_ref='R999' WHERE id=?", (tid,))
        resultados.append(("R4c- cambiar req_ref de tarea firmada -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R4c- cambiar req_ref de tarea firmada -> ABORT", "F1-R4c" in str(e)))

    # R4c+: change req_ref on tarea without entrega/firma → passes
    plan2 = plan_de_ataque(conn, "R4e")
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan2, "R1", "test", "echo test"))
    conn.execute("INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan2, "R2", "test2", "echo test2"))
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan2, "R1", "test movible", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    tid2 = conn.execute("SELECT id FROM tarea WHERE plan_id=? AND req_ref='R1'", (plan2,)).fetchone()[0]
    try:
        conn.execute("UPDATE tarea SET req_ref='R2' WHERE id=?", (tid2,))
        resultados.append(("R4c+ cambiar req_ref sin entrega ni firma -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R4c+ cambiar req_ref sin entrega ni firma -> pasa", False))

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

    # R6- verificado sin tarea_entregada → ABORT
    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      f"tarea {tid} R1: CUMPLE"))
        resultados.append(("R6- verificado sin tarea_entregada -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6- verificado sin tarea_entregada -> ABORT", "F1-R6" in str(e)))

    # R6+ verificado con tarea_entregada previa → pasa
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

    # R6b- tarea inexistente → ABORT
    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      "tarea 999999 R1: CUMPLE"))
        resultados.append(("R6b- verificado con tarea inexistente -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6b- verificado con tarea inexistente -> ABORT", "F1-R6" in str(e)))

    # R6b- plan_id NULL with "tarea N" format → ABORT
    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", None,
                      f"tarea {tid} R1: CUMPLE"))
        resultados.append(("R6b- tarea N con plan_id NULL -> ABORT", False))
    except sqlite3.IntegrityError as e:
        resultados.append(("R6b- tarea N con plan_id NULL -> ABORT", "F1-R6" in str(e)))

    # R6+ non-"tarea N" format passes through (PRINCIPIO 2: no romper el molde)
    try:
        conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                     (ahora(), "IA:07-verificador:claude-opus-5", "verificado", plan,
                      "V12 047cf4a: vista correcta"))
        resultados.append(("R6+ veredicto sin formato tarea N -> pasa", True))
    except sqlite3.IntegrityError:
        resultados.append(("R6+ veredicto sin formato tarea N -> pasa", False))

    return resultados


def _verificar_r7_en(directorio: Path) -> list[str]:
    violaciones = []
    for py in directorio.rglob("*.py"):
        texto = py.read_text(encoding="utf-8", errors="replace")
        for i, linea in enumerate(texto.splitlines(), 1):
            if "--delegado" in linea and not linea.strip().startswith("#"):
                violaciones.append(f"R7/{py.relative_to(directorio)}:{i}: contiene --delegado")
    return violaciones


def atacar_r7(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    resultados = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="f1-r7-"))
    try:
        (tmp_dir / "test_delegado.py").write_text(
            "parser.add_argument('--delegado')\n", encoding="utf-8")
        vs_neg = _verificar_r7_en(tmp_dir)
        tiene_test = any("test_delegado" in v for v in vs_neg)
        resultados.append(("R7- fichero con --delegado inyectado -> detectado", tiene_test))

        (tmp_dir / "test_delegado.py").unlink()
        (tmp_dir / "test_limpio.py").write_text(
            "parser.add_argument('--verbose')\n", encoding="utf-8")
        vs_pos = _verificar_r7_en(tmp_dir)
        tiene_clean = any("test_limpio" in v for v in vs_pos)
        resultados.append(("R7+ fichero sin --delegado -> no detectado", not tiene_clean))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
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


def atacar_rastro(conn: sqlite3.Connection) -> list[tuple[str, bool]]:
    conn.executescript(TRIGGER_RASTRO_INSERT)
    conn.executescript(TRIGGER_RASTRO_UPDATE)
    conn.executescript(TRIGGER_R2)
    resultados = []

    plan = plan_de_ataque(conn, "RASTRO")
    ref = f"RT{os.getpid()}"

    count_before = conn.execute(
        "SELECT COUNT(*) FROM evento WHERE plan_id=? AND accion='requisito_insertado'", (plan,)
    ).fetchone()[0]

    conn.execute("INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                 (plan, ref, "test ears rastro", "echo rastro"))

    count_after = conn.execute(
        "SELECT COUNT(*) FROM evento WHERE plan_id=? AND accion='requisito_insertado' AND detalle LIKE ?",
        (plan, f"ref={ref} %")
    ).fetchone()[0]
    resultados.append(("RASTRO+ INSERT requisito -> evento requisito_insertado", count_after > count_before))

    # For UPDATE test, satisfy R2 with proper approval
    conn.execute("INSERT OR IGNORE INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                 (plan, ref, "test rastro", "trabajando", "IA:02-backend-api:claude-sonnet-5"))
    conn.execute("INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                 (ahora(), "H:carlos", "cambio_requisito_aprobado", plan, _aprobacion_detalle(ref)))

    count_mod_before = conn.execute(
        "SELECT COUNT(*) FROM evento WHERE plan_id=? AND accion='requisito_modificado' AND detalle LIKE ?",
        (plan, f"ref={ref} %")
    ).fetchone()[0]

    conn.execute(f"UPDATE requisito SET ears='test ears rastro v2' WHERE plan_id=? AND ref=?", (plan, ref))

    count_mod_after = conn.execute(
        "SELECT COUNT(*) FROM evento WHERE plan_id=? AND accion='requisito_modificado' AND detalle LIKE ?",
        (plan, f"ref={ref} %")
    ).fetchone()[0]
    resultados.append(("RASTRO+ UPDATE requisito -> evento requisito_modificado", count_mod_after > count_mod_before))

    return resultados


ATACANTES = {
    "r1": atacar_r1, "r2": atacar_r2, "r3": atacar_r3,
    "r4": atacar_r4, "r5": atacar_r5, "r6": atacar_r6,
    "r7": atacar_r7, "r8": atacar_r8, "rastro": atacar_rastro,
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
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
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
    ap.add_argument("--verificar", nargs="?", const="todos", help="r1..r8, rastro, o 'todos'")
    ap.add_argument("--atacar", nargs="?", const="todos", help="r1..r8, rastro, o 'todos'")
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
