"""Instancia el molde plantilla-microservicio-ia en una solución concreta. TRASPASO-3 VERSIÓN 1, T3.2/T3.3.

Corre en el servidor del registro. Requiere el molde ya cargado (cargar_molde.py): los requisitos se
COPIAN de PLAN-T-xx de la BD, no del yaml, para que la instancia salga del molde tal como está en el registro.
Idempotente, backup sqlite3 .backup previo, un evento por alta, evento 'instanciar' al final con el tiempo.

    time python3 instanciar.py --db ~/sypnose-f1/registry.db --oferta oferta.yaml --nombre microservicio-2 --sigla M2
    python3 instanciar.py ... --nombre coforge-santander --sigla CS --proyecto-id proy:vmi3211028:rag-banking-agent

--proyecto-id: usa un nodo proyecto ya indexado (Coforge). Sin él se crea proy:plantilla:<slug>.
--local (carpetas en el PC) no está implementado: este script corre donde vive la BD; ver FASE3.md §8.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
MOLDE = "plantilla-microservicio-ia"
ROL_TODOS = "05-arquitecto-sypnose"  # T-09 (rol "todos"): la trazabilidad de ramas y commits la montó el arquitecto


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    t0 = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--nombre", required=True, help="slug de la solución (id y nombre de la colección)")
    ap.add_argument("--sigla", required=True, help="sigla de los planes: PLAN-<SIGLA>-Txx")
    ap.add_argument("--proyecto-id", help="nodo proyecto ya existente a usar")
    ap.add_argument("--repo", help="ruta del repo de la instancia (se guarda como ruta del nodo proyecto nuevo)")
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slug = args.nombre
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        sys.exit(f"[FALLO] --nombre {slug!r} debe ser un slug (minúsculas, dígitos y guiones)")
    sigla = args.sigla.upper()
    if not re.fullmatch(r"[A-Z0-9]{1,6}", sigla):
        sys.exit(f"[FALLO] --sigla {args.sigla!r} no válida")

    oferta = yaml.safe_load(Path(args.oferta).read_text(encoding="utf-8"))
    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    one = lambda sql, *a: conn.execute(sql, a).fetchone()

    if not one("SELECT 1 FROM actor WHERE id=?", args.actor):
        sys.exit(f"[FALLO] actor {args.actor} no existe")
    if not one("SELECT 1 FROM coleccion WHERE id=? AND estado='activa'", MOLDE):
        sys.exit(f"[FALLO] el molde {MOLDE} no está cargado (ejecuta cargar_molde.py)")
    moldes = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT plan_id, ears, comprobacion FROM requisito WHERE plan_id LIKE 'PLAN-T-%' AND ref='R1'")}
    faltan = [l["id"] for l in oferta["lineas"] if f"PLAN-{l['id']}" not in moldes]
    if faltan:
        sys.exit(f"[FALLO] faltan en el registro los planes molde de {faltan}")

    col = one("SELECT estado FROM coleccion WHERE id=?", slug)
    if col and col[0] != "activa":
        sys.exit(f"[FALLO] la colección {slug} existe con estado {col[0]}: no se instancia sobre una retirada")
    if args.proyecto_id:
        if not one("SELECT 1 FROM nodo WHERE id=? AND tipo='proyecto'", args.proyecto_id):
            sys.exit(f"[FALLO] --proyecto-id {args.proyecto_id} no es un nodo proyecto existente")
        proyecto = args.proyecto_id
    else:
        proyecto = f"proy:plantilla:{slug}"

    if not args.dry_run:
        destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-inst-{slug}.db")
        dst = sqlite3.connect(destino)
        with dst:
            conn.backup(dst)
        dst.close()
        print(f"[backup] {destino} ({destino.stat().st_size} bytes)")

    altas, existian = [], []

    def evento(accion, detalle, nodo_id=None, plan_id=None):
        conn.execute("INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                     (ahora(), args.actor, accion, nodo_id, plan_id, detalle))

    def insertar(etiqueta, sql, a, accion, detalle, nodo_id=None, plan_id=None):
        if conn.execute(sql, a).rowcount == 1:
            evento(accion, detalle, nodo_id, plan_id)
            altas.append(etiqueta)
        else:
            existian.append(etiqueta)

    def afirmar(campo, valor):
        vig = conn.execute("SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                           (proyecto, campo)).fetchall()
        if any(v == valor for _, v in vig):
            existian.append(f"afirmacion {campo}")
            return
        for fid, _ in vig:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (fid,))
        conn.execute("INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                     "VALUES (?,?,?,'propuesto',?,?,?)",
                     (proyecto, campo, valor, f"instanciar.py {slug}", args.actor, ahora()))
        evento("afirmacion_versionada" if vig else "afirmacion_creada", f"{campo} = {valor}", nodo_id=proyecto)
        altas.append(f"afirmacion {campo}")

    planes_creados = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not args.proyecto_id:
            insertar(f"nodo {proyecto}",
                     "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ruta, ambito, vitalidad, descubierto_en, descubierto_por) "
                     "VALUES (?, 'proyecto', ?, ?, 'plantilla', 'activo', ?, 'humano')",
                     (proyecto, slug, args.repo, ahora()),
                     "alta_nodo", f"nodo proyecto {proyecto} (instancia de {MOLDE})", nodo_id=proyecto)
        insertar(f"coleccion {slug}",
                 "INSERT OR IGNORE INTO coleccion (id, nombre, regla, estado) VALUES (?, ?, ?, 'activa')",
                 (slug, slug, f"pendiente-sintaxis-E11: pertenencia por ancla (instancia de {MOLDE})"),
                 "coleccion_creada", f"coleccion {slug} (instancia de {MOLDE})", nodo_id=proyecto)
        insertar(f"ancla {slug}", "INSERT OR IGNORE INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
                 (slug, proyecto), "ancla_creada", f"ancla {slug} -> {proyecto}", nodo_id=proyecto)

        for l in oferta["lineas"]:
            num = l["id"].split("-")[1]
            pid = f"PLAN-{sigla}-T{num}"
            rol = ROL_TODOS if l["rol"] == "todos" else l["rol"]
            modelo = oferta["roles"][rol]["modelo"]
            agente = f"IA:{rol}:{modelo}"
            ears, comprobacion = moldes[f"PLAN-{l['id']}"]
            que = f"[{slug}] {l['plan']}"

            insertar(f"actor {agente}", "INSERT OR IGNORE INTO actor (id, clase, rol, modelo) VALUES (?, 'ia', ?, ?)",
                     (agente, rol, modelo), "alta_actor", agente)
            antes = one("SELECT 1 FROM plan WHERE id=?", pid)
            insertar(f"plan {pid}",
                     "INSERT OR IGNORE INTO plan (id, clase, que, para, porque, afecta, estado, autor) "
                     "VALUES (?, ?, ?, ?, ?, ?, 'propuesto', ?)",
                     (pid, l["clase"], que, l["oferta"], f"línea {l['id']} de la oferta · instancia de {MOLDE}",
                      rol, args.actor),
                     "alta_plan", f"{pid} · {l['id']} · {l['plan']}", plan_id=pid)
            planes_creados += 0 if antes else 1
            insertar(f"requisito {pid}/R1",
                     "INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?, 'R1', ?, ?)",
                     (pid, ears, comprobacion), "alta_requisito", f"{pid}/R1 copiado de PLAN-{l['id']}", plan_id=pid)
            insertar(f"plan_objetivo {pid}",
                     "INSERT OR IGNORE INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                     (pid, proyecto), "plan_objetivo_creado", f"{pid} -> {proyecto}", nodo_id=proyecto, plan_id=pid)
            if one("SELECT 1 FROM tarea WHERE plan_id=? AND req_ref='R1'", pid):
                existian.append(f"tarea {pid}/R1")
            else:
                conn.execute("INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?, 'R1', ?, 'pendiente', ?)",
                             (pid, l["plan"], agente))
                evento("alta_tarea", f"{pid}/R1 pendiente · agente {agente}", plan_id=pid)
                altas.append(f"tarea {pid}/R1")
            afirmar(f"linea:{l['id']}", pid)

        afirmar("instancia_de", MOLDE)
        segundos = round(time.monotonic() - t0, 2)
        evento("instanciar", f"{slug} ({sigla}) desde {MOLDE}: {planes_creados} planes nuevos, {len(altas)} altas, {segundos}s",
               nodo_id=proyecto)
        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"instancia {slug} ({sigla}) · proyecto {proyecto}")
    print(f"altas: {len(altas)} · ya existían: {len(existian)} · planes nuevos: {planes_creados}")
    for a in altas:
        print(f"  + {a}")
    if args.dry_run:
        print("--dry-run: transacción deshecha, nada escrito")
    else:
        q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
        like = f"PLAN-{sigla}-T%"
        print("\n[comprobación]")
        print("  colección activa     :", q("SELECT COUNT(*) FROM coleccion WHERE id=? AND estado='activa'", slug))
        print("  planes", like, ":", q("SELECT COUNT(*) FROM plan WHERE id LIKE ?", like))
        print("  requisitos           :", q("SELECT COUNT(*) FROM requisito WHERE plan_id LIKE ?", like))
        print("  tareas pendientes    :", q("SELECT COUNT(*) FROM tarea WHERE plan_id LIKE ? AND progreso='pendiente'", like))
        print("  tareas sin agente    :", q("SELECT COUNT(*) FROM tarea WHERE plan_id LIKE ? AND agente IS NULL", like))
    print(f"tiempo del script: {time.monotonic() - t0:.2f}s")
    conn.close()


if __name__ == "__main__":
    main()
