"""Carga las 12 preguntas de DEFENSA.md §10 en el registro.

Parsea las preguntas del fichero y las inserta como afirmaciones
defensa:N sobre sol:coforge:rag-banking-agent con pregunta, respuesta
y prueba.

    python3 cargar_portada.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
SOL_ID = "sol:coforge:rag-banking-agent"
DEFENSA_MD = PLANTILLA_DIR.parent / "DEFENSA.md"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_preguntas(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    section_match = re.search(r"^## 10\. .+$", text, re.MULTILINE)
    if not section_match:
        sys.exit("[FALLO] no se encontró §10 en DEFENSA.md")

    section_start = section_match.end()
    next_section = re.search(r"^## \d+\.", text[section_start:], re.MULTILINE)
    section_text = text[section_start:section_start + next_section.start()] if next_section else text[section_start:]

    preguntas = []
    blocks = re.split(r"\n\*\*(\d+)\.\s+", section_text)
    i = 1
    while i < len(blocks) - 1:
        num = int(blocks[i])
        content = blocks[i + 1]

        lines = content.strip().split("\n")
        pregunta_line = lines[0].rstrip("**").rstrip()
        if pregunta_line.endswith("**"):
            pregunta_line = pregunta_line[:-2]

        respuesta_lines = []
        prueba_lines = []
        in_prueba = False
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("Prueba:"):
                in_prueba = True
                prueba_lines.append(stripped[len("Prueba:"):].strip())
            elif in_prueba:
                if stripped:
                    prueba_lines.append(stripped)
            else:
                if stripped:
                    respuesta_lines.append(stripped)

        preguntas.append({
            "num": num,
            "pregunta": pregunta_line,
            "respuesta": " ".join(respuesta_lines),
            "prueba": " ".join(prueba_lines),
        })
        i += 2

    return preguntas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    if not DEFENSA_MD.exists():
        sys.exit(f"[FALLO] {DEFENSA_MD} no existe")

    preguntas = parse_preguntas(DEFENSA_MD)
    print(f"[DEFENSA.md] {len(preguntas)} preguntas parseadas")
    if len(preguntas) != 12:
        print(f"[WARN] esperadas 12, encontradas {len(preguntas)}")

    for p in preguntas:
        print(f"  {p['num']:2d}. {p['pregunta'][:70]}...")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone():
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "portada-defensa")

    altas = []
    existian = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        for p in preguntas:
            campo = f"defensa:{p['num']:02d}"
            valor = (
                f"P: {p['pregunta']}\n"
                f"R: {p['respuesta']}\n"
                f"Prueba: {p['prueba']}"
            )
            existing = conn.execute(
                "SELECT 1 FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                (SOL_ID, campo),
            ).fetchone()
            if existing:
                existian.append(campo)
                continue
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                "VALUES (?, ?, ?, 'observado', 'DEFENSA.md#10', ?, ?)",
                (SOL_ID, campo, valor, ACTOR, ts),
            )
            altas.append(campo)

        if altas:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'portada_defensa_cargada', ?, NULL, ?)",
                (ts, ACTOR, SOL_ID,
                 f"{len(altas)} preguntas de DEFENSA.md §10 cargadas como afirmaciones defensa:NN"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
