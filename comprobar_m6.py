"""M6: comprobación literal de las 7 piezas del responsable + 4 opciones de stack.

    python3 comprobar_m6.py --db <copia de registry.db>

CUMPLE (exit 0) cuando:
  A. portada_pieza_agenticas vigente con las 7 piezas (Temporal, Claude Agent
     SDK, OpenHands, vLLM, pgvector+Apache AGE, K8s/IAM/secretos, extras
     RTK/agentmemory/MCP); cada fila con pieza+estado y, si es hecho/parcial,
     evidencia no vacía; si es opción, marca 'no en el POC' y qué cambiaría.
  B. nodos tec:coforge:{vllm,openhands,apache-age,rtk-agentmemory} con estado
     vigente opcion-no-poc y decide_banco y que_cambia no vacíos.
Solo lectura: no escribe nada.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import verificar_sin_delete

NODO_PIEZAS = "plantilla:microservicio-ia"
CAMPO_PIEZAS = "portada_pieza_agenticas"

PIEZAS_ESPERADAS = [
    "1. Temporal",
    "2. Claude Agent SDK",
    "3. OpenHands",
    "4. vLLM",
    "5. pgvector + Apache AGE",
    "6. K8s / IAM / secretos / aislamiento",
    "7. Extras: RTK / agentmemory / MCP",
]

OPCIONES = ["vllm", "openhands", "apache-age", "rtk-agentmemory"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    args = ap.parse_args()

    verificar_sin_delete()

    conn = sqlite3.connect(f"file:{Path(args.db).expanduser()}?mode=ro", uri=True)
    fallos = []

    fila = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
        (NODO_PIEZAS, CAMPO_PIEZAS),
    ).fetchone()
    if not fila:
        fallos.append(f"A: no hay afirmación vigente {CAMPO_PIEZAS} en {NODO_PIEZAS}")
    else:
        aid, valor = fila
        try:
            piezas = json.loads(valor)
        except json.JSONDecodeError:
            fallos.append(f"A: afirmación {aid} no es JSON válido")
            piezas = []
        print(f"A: {CAMPO_PIEZAS} afirmación {aid}, {len(piezas)} filas")
        if len(piezas) != 7:
            fallos.append(f"A: esperadas 7 piezas, hay {len(piezas)}")
        nombres = []
        for p in piezas:
            nom = p.get("pieza", "")
            nombres.append(nom)
            est = p.get("estado", "")
            ev = p.get("evidencia", "")
            qc = p.get("que_cambiaria", "")
            if not nom or not est:
                fallos.append(f"A: fila sin pieza/estado: {p}")
                continue
            if "no en el POC" in est:
                if not qc:
                    fallos.append(f"A: '{nom}' es opción sin que_cambiaria")
            else:
                if not ev:
                    fallos.append(f"A: '{nom}' hecho/parcial sin evidencia")
        for esperada in PIEZAS_ESPERADAS:
            if not any(esperada in n for n in nombres):
                fallos.append(f"A: falta la pieza '{esperada}'")

    for oid in OPCIONES:
        nid = f"tec:coforge:{oid}"
        if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nid,)).fetchone():
            fallos.append(f"B: no existe nodo {nid}")
            continue
        filas = {
            c: v
            for c, v in conn.execute(
                "SELECT campo, valor FROM afirmacion WHERE nodo_id=? AND vigente=1",
                (nid,),
            )
        }
        est = filas.get("estado", "")
        db = filas.get("decide_banco", "")
        qc = filas.get("que_cambia", "")
        print(f"B: {nid} estado='{est}' decide_banco={'sí' if db else 'NO'} que_cambia={'sí' if qc else 'NO'}")
        if est != "opcion-no-poc":
            fallos.append(f"B: {nid} estado='{est}' ≠ opcion-no-poc")
        if not db:
            fallos.append(f"B: {nid} sin decide_banco")
        if not qc:
            fallos.append(f"B: {nid} sin que_cambia")

    conn.close()

    print()
    if fallos:
        print("FALLA:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("CUMPLE: 7 piezas con estado y evidencia/marca no-en-POC; 4 opciones opcion-no-poc con decide_banco y que_cambia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
