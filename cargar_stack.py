"""A5.5 (16-sep): carga el stack tecnológico desde oferta.yaml al registro.

Crea nodos tec:coforge:<id>, relaciones sol→usa→tec, tec→cubre→línea,
tec→usa→fichero (evidencia), y afirmaciones para_que/por_que/estado.
Certeza = observado si la evidencia existe en el repo, declarado si no.

    python3 cargar_stack.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_stack.py"
SOL_ID = "sol:coforge:rag-banking-agent"
PLANTILLA_SOL_ID = "sol:coforge:sypnose-plantilla"
AMBITO = "vmi3211028"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"
REPO_RAG = PLANTILLA_DIR.parent / "rag-banking-agent"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def evidencia_existe(ruta_evidencia: str, bloque: str) -> bool:
    if bloque == "solucion":
        base = REPO_RAG
    else:
        base = PLANTILLA_DIR
    fichero = ruta_evidencia.split("@")[0]
    return (base / fichero).exists()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--actor", default=ACTOR)
    args = p.parse_args()

    verificar_sin_delete()

    oferta = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    stack = oferta.get("stack", {})
    if not stack:
        sys.exit("[FALLO] no hay sección 'stack' en oferta.yaml")

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_canonicos_registrados(conn)

    if not args.dry_run:
        backup_registro(conn, db, "pre-stack")

    altas = []
    existian = []
    afirmaciones = 0
    relaciones = 0

    for bloque, sol_id in [("solucion", SOL_ID), ("plantilla", PLANTILLA_SOL_ID)]:
        entries = stack.get(bloque, [])
        if not entries:
            continue

        if bloque == "plantilla":
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (PLANTILLA_SOL_ID,)).fetchone():
                if not args.dry_run:
                    conn.execute(
                        "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                        "VALUES (?, 'solucion', 'SYPNOSE plantilla (Coforge/Santander)', ?, 'activo', ?, ?)",
                        (PLANTILLA_SOL_ID, AMBITO, ahora(), FUENTE),
                    )
                altas.append(f"nodo {PLANTILLA_SOL_ID}")

        for entry in entries:
            tid = entry["id"]
            nodo_id = f"tec:coforge:{tid}"
            nombre = entry["nombre"]
            grupo = entry["grupo"]
            para_que = entry["para_que"]
            por_que = entry["por_que"]
            lineas = entry.get("lineas", [])
            evidencias = entry.get("evidencia", [])
            estado_yaml = entry.get("estado", "implementado")

            todas_existen = all(evidencia_existe(e, bloque) for e in evidencias) if evidencias else False
            certeza = "observado" if todas_existen else "propuesto"
            estado_final = estado_yaml if todas_existen or estado_yaml == "opcional-no-implementado" else "declarado-sin-evidencia"

            if args.dry_run:
                print(f"  [dry-run] {nodo_id}: {nombre} ({grupo}) certeza={certeza} estado={estado_final}")
                continue

            rc = conn.execute(
                "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                "VALUES (?, 'tecnologia', ?, ?, 'activo', ?, ?)",
                (nodo_id, nombre, AMBITO, ahora(), FUENTE),
            ).rowcount
            if rc == 1:
                altas.append(f"nodo {nodo_id}")
            else:
                existian.append(f"nodo {nodo_id}")

            # sol → usa → tec
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'usa', ?, ?, ?)",
                (sol_id, nodo_id, certeza, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                altas.append(f"usa {sol_id} → {nodo_id}")
                relaciones += 1

            # tec → cubre → línea
            for lid in lineas:
                linea_id = f"linea:coforge:{lid}"
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'cubre', ?, ?, ?)",
                    (nodo_id, linea_id, certeza, FUENTE, ahora()),
                ).rowcount
                if rc == 1:
                    altas.append(f"cubre {nodo_id} → {linea_id}")
                    relaciones += 1

            # tec → usa → fichero (evidencia)
            for ev in evidencias:
                fichero = ev.split("@")[0]
                if bloque == "solucion":
                    fichero_id = f"mod:vmi3211028:rag-banking-agent:{fichero}"
                else:
                    fichero_id = f"mod:plantilla:{fichero}"
                if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (fichero_id,)).fetchone():
                    conn.execute(
                        "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                        "VALUES (?, 'modulo', ?, ?, 'activo', ?, ?)",
                        (fichero_id, fichero, AMBITO, ahora(), FUENTE),
                    )
                    altas.append(f"nodo {fichero_id}")
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'usa', ?, ?, ?)",
                    (nodo_id, fichero_id, certeza, FUENTE, ahora()),
                ).rowcount
                if rc == 1:
                    relaciones += 1

            # Afirmaciones: para_que, por_que, grupo, estado
            ev_texto = ", ".join(evidencias) if evidencias else None
            for campo, valor in [("para_que", para_que), ("por_que", por_que), ("grupo", grupo), ("estado", estado_final)]:
                rc = conn.execute(
                    "INSERT OR IGNORE INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, evidencia, vigente) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (nodo_id, campo, valor, certeza, FUENTE, args.actor, ahora(), ev_texto),
                ).rowcount
                if rc == 1:
                    afirmaciones += 1

            print(f"  {nodo_id}: {nombre} [{grupo}] certeza={certeza} estado={estado_final}")

    # Portada: afirmaciones de texto canónico sobre el nodo solución
    portada = oferta.get("portada", {})
    portada_count = 0
    for capa, texto in portada.items():
        campo = f"portada_{capa}"
        if not args.dry_run:
            rc = conn.execute(
                "INSERT OR IGNORE INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, evidencia, vigente) "
                "VALUES (?, ?, ?, 'observado', ?, ?, ?, 'oferta.yaml#portada', 1)",
                (SOL_ID, campo, texto, FUENTE, args.actor, ahora()),
            ).rowcount
            if rc == 1:
                portada_count += 1
                afirmaciones += 1
        else:
            print(f"  [dry-run] portada {campo}: {texto[:60]}...")
            portada_count += 1
    if portada_count:
        print(f"  [portada] {portada_count} afirmaciones creadas")

    if not args.dry_run and (altas or afirmaciones):
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ahora(), args.actor, "stack_cargado",
             f"{len(altas)} altas, {relaciones} relaciones, {afirmaciones} afirmaciones"),
        )
        conn.commit()

    conn.close()

    print(f"\nResultado: {len(altas)} altas, {len(existian)} ya existían, {relaciones} relaciones, {afirmaciones} afirmaciones")


if __name__ == "__main__":
    main()
