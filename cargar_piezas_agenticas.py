"""M6: carga portada_pieza_agenticas con las 7 piezas de la plantilla del responsable.

Sección 'plataforma agéntica' de la portada: para cada pieza, estado
(hecho/parcial/diseñado) y evidencia del registro o qué cambiaría (opción
no-en-POC). Sigue el patrón de cargar_glosario.py (una afirmación JSON).

    python3 cargar_piezas_agenticas.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, verificar_sin_delete

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_piezas_agenticas.py"
PLAN_ID = "PLAN-CS-M6"

PIEZAS = [
    {
        "pieza": "1. Temporal",
        "estado": "diseñado (opción, no en el POC)",
        "evidencia": "tec:coforge:temporal-io estado=opcion-preparada",
        "que_cambiaria": "workflows duraderos del orquestador sobre el mismo registro; el molde no cambia",
    },
    {
        "pieza": "2. Claude Agent SDK",
        "estado": "hecho",
        "evidencia": "caparazón + fábrica: tec:coforge:caparazón y tec:coforge:claude-agent-sdk estado=implementado (TRASPASO-4 A1-A4)",
        "que_cambiaria": "",
    },
    {
        "pieza": "3. OpenHands",
        "estado": "diseñado (opción, no en el POC)",
        "evidencia": "tec:coforge:openhands estado=opcion-no-poc",
        "que_cambiaria": "el caparazón corre sobre Claude Code hoy; molde y registro no dependen del runtime",
    },
    {
        "pieza": "4. vLLM",
        "estado": "diseñado (opción, no en el POC)",
        "evidencia": "tec:coforge:vllm estado=opcion-no-poc",
        "que_cambiaria": "nada de código: endpoint y variables del contrato (valores inyectados por el banco)",
    },
    {
        "pieza": "5. pgvector + Apache AGE",
        "estado": "hecho (pgvector) + opción (AGE, no en el POC)",
        "evidencia": "pgvector: línea T08 (tec:coforge:postgresql16 y tec:coforge:hnsw-gin implementado); AGE: tec:coforge:apache-age opcion-no-poc",
        "que_cambiaria": "AGE: extensión en la misma base Postgres; el grafo que alimenta graphify pasa a openCypher",
    },
    {
        "pieza": "6. K8s / IAM / secretos / aislamiento",
        "estado": "hecho",
        "evidencia": "línea T13 (tec:coforge:kubernetes implementado); terraform M4 tarea 60 firmada (evento 24154, plan cerrado 24675); 0 secretos en código: solo nombres de variables",
        "que_cambiaria": "",
    },
    {
        "pieza": "7. Extras: RTK / agentmemory / MCP",
        "estado": "parcial (MCP, coste por turno, lecciones) + opción (RTK/agentmemory, no en el POC)",
        "evidencia": "MCP: tec:coforge:mcp-kb y mcp-sypnose implementado; coste por turno: eventos con tokens_turno/coste_turno_usd (tec:coforge:finops-por-evento); lecciones: tec:coforge:kb-lecciones implementado",
        "que_cambiaria": "RTK/agentmemory: capa de optimización y memoria junto al coste por turno ya medido (tec:coforge:rtk-agentmemory opcion-no-poc)",
    },
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_sin_delete()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    ts = ahora()
    nodo = "plantilla:microservicio-ia"
    campo = "portada_pieza_agenticas"
    valor = json.dumps(PIEZAS, ensure_ascii=False)

    ya = conn.execute(
        "SELECT id FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
        (nodo, campo),
    ).fetchone()

    if ya:
        print(f"[EXISTE] {campo} ya cargado (afirmacion {ya[0]})")
        conn.close()
        return

    if args.dry_run:
        print(f"[dry-run] {len(PIEZAS)} piezas en {campo} @ {nodo}")
        for p in PIEZAS:
            print(f"  {p['pieza']}: {p['estado']}")
            if p["evidencia"]:
                print(f"    evidencia: {p['evidencia'][:70]}...")
            if p["que_cambiaria"]:
                print(f"    que_cambiaria: {p['que_cambiaria'][:70]}...")
        conn.close()
        return

    backup_registro(conn, db_path, "pre-piezas-agenticas")

    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
        "VALUES (?, ?, ?, 'observado', ?, ?, ?, 1)",
        (nodo, campo, valor, FUENTE, ACTOR, ts),
    )

    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
        "VALUES (?, ?, 'dato_cargado', ?, ?, ?)",
        (ts, ACTOR, nodo, PLAN_ID,
         f"M6: portada_pieza_agenticas con {len(PIEZAS)} piezas de la plantilla del responsable "
         f"(2 hecho, 1 parcial, 4 con opción no-en-POC)"),
    )
    conn.commit()
    eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    print(f"[OK] {len(PIEZAS)} piezas cargadas en {campo}")
    print(f"[evento] {eid}")
    conn.close()


if __name__ == "__main__":
    main()
