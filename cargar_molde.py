"""Carga el molde (plantilla/oferta.yaml) en el registro SYPNOSE. TRASPASO-3 VERSIÓN 1, T3.1.

Corre en el servidor del registro (PyYAML + sqlite3). No toca código de SYPNOSE: solo filas.
Idempotente: cada alta es INSERT OR IGNORE o comprobación previa; re-ejecutar no duplica ni modifica
planes/requisitos existentes (si difieren del yaml lo avisa, no los pisa). Afirmación con valor nuevo:
versión nueva + vigente=0 en la anterior. Backup sqlite3 .backup antes de escribir. Un evento por alta.

    python3 cargar_molde.py --db ~/sypnose-f1/registry.db --oferta oferta.yaml [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import OFERTA_YAML, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
CLASES = {"investigar", "migrar", "mantener", "retirar"}
FUENTE = "plantilla/oferta.yaml"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def cargar_oferta(ruta: Path) -> dict:
    d = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    requeridos = {"id", "oferta", "plan", "clase", "ears", "comprobacion", "rol", "skills"}
    for l in d["lineas"]:
        faltan = requeridos - set(l)
        if faltan:
            sys.exit(f"[FALLO] línea {l.get('id')} sin {sorted(faltan)}")
        if l["clase"] not in CLASES:
            sys.exit(f"[FALLO] línea {l['id']}: clase {l['clase']!r} no válida")
        if l["rol"] != "todos" and l["rol"] not in d["roles"]:
            sys.exit(f"[FALLO] línea {l['id']}: rol {l['rol']!r} no está en roles")
    return d


def id_plan_tipo(linea_id: str) -> str:
    return f"PLAN-{linea_id}"  # T-01 -> PLAN-T-01


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-molde.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


class Carga:
    def __init__(self, conn: sqlite3.Connection, actor: str):
        self.c = conn
        self.actor = actor
        self.altas: list[str] = []
        self.existian: list[str] = []
        self.avisos: list[str] = []

    def evento(self, accion: str, detalle: str, nodo_id: str | None = None, plan_id: str | None = None):
        self.c.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
            (ahora(), self.actor, accion, nodo_id, plan_id, detalle),
        )

    def insertar(self, etiqueta: str, sql: str, args: tuple, accion: str, detalle: str,
                 nodo_id: str | None = None, plan_id: str | None = None) -> bool:
        if self.c.execute(sql, args).rowcount == 1:
            self.evento(accion, detalle, nodo_id, plan_id)
            self.altas.append(etiqueta)
            return True
        self.existian.append(etiqueta)
        return False

    def afirmar(self, nodo_id: str, campo: str, valor: str, certeza: str = "propuesto"):
        vigentes = self.c.execute(
            "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1", (nodo_id, campo)
        ).fetchall()
        if any(v == valor for _, v in vigentes):
            self.existian.append(f"afirmacion {campo}")
            return
        for fila_id, _ in vigentes:
            self.c.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (fila_id,))
        self.c.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
            (nodo_id, campo, valor, certeza, FUENTE, self.actor, ahora()),
        )
        accion = "afirmacion_versionada" if vigentes else "afirmacion_creada"
        self.evento(accion, f"{campo} = {valor[:160]}", nodo_id=nodo_id)
        self.altas.append(f"afirmacion {campo}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--dry-run", action="store_true", help="ejecuta todo en una transacción y la deshace")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    oferta = cargar_oferta(OFERTA_YAML)
    slug = oferta["plantilla"]
    coleccion = f"plantilla-{slug}"
    nodo = f"plantilla:{slug}"

    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] el actor {args.actor} no existe en 'actor'")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b} ({b.stat().st_size} bytes)")

    k = Carga(conn, args.actor)
    conn.execute("BEGIN IMMEDIATE")
    try:
        k.insertar(
            f"nodo {nodo}",
            "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
            "VALUES (?, 'plantilla', ?, 'plantilla', 'activo', ?, 'humano')",
            (nodo, "Plantilla microservicio IA", ahora()),
            "alta_nodo", f"nodo plantilla {nodo} (molde de la oferta: {oferta['oferta']})", nodo_id=nodo,
        )
        k.insertar(
            f"coleccion {coleccion}",
            "INSERT OR IGNORE INTO coleccion (id, nombre, regla, estado) VALUES (?, ?, ?, 'activa')",
            (coleccion, coleccion, "pendiente-sintaxis-E11: pertenencia por ancla (ambito=plantilla)"),
            "coleccion_creada", f"coleccion {coleccion}", nodo_id=nodo,
        )
        k.insertar(
            f"ancla {coleccion}",
            "INSERT OR IGNORE INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
            (coleccion, nodo), "ancla_creada", f"ancla {coleccion} -> {nodo}", nodo_id=nodo,
        )

        for l in oferta["lineas"]:
            pid = id_plan_tipo(l["id"])
            que = f"[{coleccion}] {l['plan']}"
            k.insertar(
                f"plan {pid}",
                "INSERT OR IGNORE INTO plan (id, clase, que, para, porque, afecta, estado, autor) "
                "VALUES (?, ?, ?, ?, 'línea de la oferta', ?, 'propuesto', ?)",
                (pid, l["clase"], que, l["oferta"], l["rol"], args.actor),
                "alta_plan", f"{pid} · {l['id']} · {l['plan']}", plan_id=pid,
            )
            actual = conn.execute("SELECT que, para, clase FROM plan WHERE id=?", (pid,)).fetchone()
            if actual != (que, l["oferta"], l["clase"]):
                k.avisos.append(f"{pid} existe y difiere del yaml (no se pisa): {actual}")
            k.insertar(
                f"requisito {pid}/R1",
                "INSERT OR IGNORE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?, 'R1', ?, ?)",
                (pid, l["ears"], l["comprobacion"]),
                "alta_requisito", f"{pid}/R1", plan_id=pid,
            )
            ears_bd = conn.execute("SELECT ears FROM requisito WHERE plan_id=? AND ref='R1'", (pid,)).fetchone()
            if ears_bd and ears_bd[0] != l["ears"]:
                k.avisos.append(f"{pid}/R1: la EARS de la BD difiere del yaml (no se pisa)")
            k.insertar(
                f"plan_objetivo {pid}",
                "INSERT OR IGNORE INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                (pid, nodo), "plan_objetivo_creado", f"{pid} -> {nodo}", nodo_id=nodo, plan_id=pid,
            )
            k.afirmar(nodo, f"linea:{l['id']}", l["oferta"])

        k.afirmar(nodo, "oferta", oferta["oferta"])
        comunes = sorted({s for l in oferta["lineas"] if l["rol"] == "todos" for s in l["skills"]})
        for rol, cfg in oferta["roles"].items():
            skills = sorted({s for l in oferta["lineas"] if l["rol"] == rol for s in l["skills"]} | set(comunes))
            k.afirmar(nodo, f"rol:{rol}", f"modelo={cfg['modelo']}; skills={', '.join(skills)}")

        for v in oferta.get("vistas", []):
            consola = v.get("consola")
            if not consola:
                k.avisos.append(f"vista {v['nombre']!r} no creada: sin bloque 'consola' (la consola solo filtra nodos; ver consultas.sql)")
                continue
            if conn.execute("SELECT 1 FROM vista_guardada WHERE nombre=? AND estado='activa'", (v["nombre"],)).fetchone():
                k.existian.append(f"vista {v['nombre']}")
                continue
            conn.execute(
                "INSERT INTO vista_guardada (nombre, ambito, chip, filtro, creada_en, creada_por) VALUES (?, ?, ?, ?, ?, ?)",
                (v["nombre"], consola.get("ambito"), consola.get("chip"), consola.get("filtro"), ahora(), args.actor),
            )
            k.evento("vista_guardada", f"{v['nombre']} · consola {consola}", nodo_id=nodo)
            k.altas.append(f"vista {v['nombre']}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"altas: {len(k.altas)} · ya existían: {len(k.existian)}")
    for a in k.altas:
        print(f"  + {a}")
    for a in k.avisos:
        print(f"  ! {a}")
    if args.dry_run:
        print("--dry-run: transacción deshecha, nada escrito")
        return
    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  planes PLAN-T-%       :", q("SELECT COUNT(*) FROM plan WHERE id LIKE 'PLAN-T-%'"))
    print("  requisitos PLAN-T-%   :", q("SELECT COUNT(*) FROM requisito WHERE plan_id LIKE 'PLAN-T-%'"))
    print("  plan_objetivo plantilla:", q(f"SELECT COUNT(*) FROM plan_objetivo WHERE nodo_id='{nodo}'"))
    print("  afirmaciones vigentes :", q(f"SELECT COUNT(*) FROM afirmacion WHERE nodo_id='{nodo}' AND vigente=1"))
    print("  vistas plantilla      :", q("SELECT COUNT(*) FROM vista_guardada WHERE ambito='plantilla' AND estado='activa'"))
    conn.close()


if __name__ == "__main__":
    main()
