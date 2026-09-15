"""Carga descripción y por_qué de un spec.md como afirmaciones en el registro.

Lee las secciones "Solución" y el razonamiento de diseño del spec de una línea,
y las escribe como afirmaciones (certeza=propuesto) en el nodo linea:coforge:<sigla>.
Idempotente: si el valor ya coincide, 0 cambios.

    python3 cargar_spec.py --db ~/sypnose-f1/registry.db T01 specs/T01/spec.md
    python3 cargar_spec.py --db ~/sypnose-f1/registry.db T01 specs/T01/spec.md --dry-run
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
MAX_DESC = 400


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def obtener_spec_sha(spec_rel: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%H", "--", spec_rel],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"[FALLO] no hay commit para {spec_rel} en el repo plantilla")
    return r.stdout.strip()


def extraer_seccion(texto: str, titulo: str) -> str:
    patron = re.compile(rf"^## {re.escape(titulo)}\b.*$", re.MULTILINE)
    m = patron.search(texto)
    if not m:
        return ""
    inicio = m.end()
    siguiente = re.search(r"^## ", texto[inicio:], re.MULTILINE)
    if siguiente:
        return texto[inicio:inicio + siguiente.start()].strip()
    return texto[inicio:].strip()


def extraer_descripcion(texto: str) -> str:
    seccion = extraer_seccion(texto, "Solución")
    if not seccion:
        sys.exit("[FALLO] sección '## Solución' no encontrada en el spec")
    parrafos = [p.strip() for p in seccion.split("\n\n") if p.strip() and not p.strip().startswith("-")]
    desc = parrafos[0] if parrafos else seccion
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) > MAX_DESC:
        desc = desc[:MAX_DESC - 3] + "..."
    return desc


def extraer_por_que(texto: str) -> str:
    seccion = extraer_seccion(texto, "Solución")
    if not seccion:
        return ""
    parrafos = [p.strip() for p in seccion.split("\n\n") if p.strip() and not p.strip().startswith("-")]
    if len(parrafos) < 2:
        return ""
    por_que = parrafos[1]
    por_que = re.sub(r"\s+", " ", por_que).strip()
    if len(por_que) > MAX_DESC:
        por_que = por_que[:MAX_DESC - 3] + "..."
    return por_que


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga descripcion y por_que de spec.md al registro")
    ap.add_argument("sigla", help="sigla de la línea, ej. T01")
    ap.add_argument("spec", help="ruta al spec.md relativa a plantilla/")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    spec_path = PLANTILLA_DIR / args.spec
    if not spec_path.exists():
        sys.exit(f"[FALLO] spec no encontrado: {spec_path}")

    nodo_id = f"linea:coforge:{args.sigla}"
    spec_rel = args.spec
    spec_sha = obtener_spec_sha(spec_rel)

    texto = spec_path.read_text(encoding="utf-8")
    descripcion = extraer_descripcion(texto)
    por_que = extraer_por_que(texto)

    if not descripcion:
        sys.exit("[FALLO] no se pudo extraer descripción del spec")

    print(f"[nodo] {nodo_id}")
    print(f"[spec] {spec_rel} (sha {spec_sha[:12]})")
    print(f"[descripcion] ({len(descripcion)} chars) {descripcion[:80]}...")
    if por_que:
        print(f"[por_que] ({len(por_que)} chars) {por_que[:80]}...")
    else:
        print("[por_que] (vacío — solo 1 párrafo en Solución)")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone()
    if not row:
        sys.exit(f"[FALLO] nodo {nodo_id} no existe en el registro")

    campos = {"descripcion": descripcion}
    if por_que:
        campos["por_que"] = por_que

    cambios = []
    for campo, valor in campos.items():
        existente = conn.execute(
            "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
            (nodo_id, campo),
        ).fetchone()
        if existente:
            if existente[1] == valor:
                print(f"[idempotente] {campo} ya coincide. 0 cambios.")
                continue
            cambios.append(("update", campo, valor, existente[0]))
        else:
            cambios.append(("insert", campo, valor, None))

    if not cambios:
        print("[OK] 0 cambios — todo idempotente.")
        conn.close()
        return

    if args.dry_run:
        for op, campo, valor, _ in cambios:
            print(f"[dry-run] {op} {nodo_id}.{campo} = {valor[:60]}...")
        conn.close()
        return

    b = backup_registro(conn, db_path, "spec")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        fuente = f"spec:{spec_rel}@{spec_sha[:12]}"
        for op, campo, valor, old_id in cambios:
            if op == "update":
                conn.execute(
                    "UPDATE afirmacion SET vigente=0 WHERE id=?", (old_id,),
                )
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
                "VALUES (?,?,?,?,?,?,?,1)",
                (nodo_id, campo, valor, "propuesto", fuente, ACTOR, ts),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "afirmacion_spec", nodo_id, f"{campo} = {valor[:80]}... · fuente: {fuente}"),
            )
            print(f"[{op}] {nodo_id}.{campo}")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {len(cambios)} afirmaciones escritas en {nodo_id} desde {spec_rel}")


if __name__ == "__main__":
    main()
