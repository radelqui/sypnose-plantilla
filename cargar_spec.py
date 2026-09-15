"""Carga descripción y por_qué de un spec.md como afirmaciones en el nodo solución.

Lee las secciones "Solución" y el razonamiento de diseño del spec de una línea,
verifica autoría (Chat: trailer = rol en roles_por_linea), y escribe
afirmaciones (certeza=propuesto) en sol:coforge:rag-banking-agent con
campos 'descripcion:<sigla>' / 'por_que:<sigla>' (par solución-línea).
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

import yaml

from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
SOL_ID = "sol:coforge:rag-banking-agent"
MAX_DESC = 400
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def cargar_roles_por_linea() -> dict:
    datos = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    return datos.get("roles_por_linea", {})


def obtener_spec_sha(spec_rel: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%H", "--", spec_rel],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"[FALLO] no hay commit para {spec_rel} en el repo plantilla")
    return r.stdout.strip()


def obtener_spec_autor(spec_rel: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%(trailers:key=Chat,valueonly)", "--", spec_rel],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] no se pudo leer trailers de {spec_rel}")
    autor = r.stdout.strip()
    if not autor:
        sys.exit(f"[FALLO] último commit de {spec_rel} no tiene trailer 'Chat:'")
    return autor


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
    ap = argparse.ArgumentParser(description="Carga descripcion y por_que de spec.md al nodo solución")
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

    roles_por_linea = cargar_roles_por_linea()
    rol_esperado = roles_por_linea.get(args.sigla, {}).get("rol")
    if not rol_esperado:
        sys.exit(f"[FALLO] sigla {args.sigla} no tiene rol en roles_por_linea de oferta.yaml")

    spec_rel = args.spec
    spec_sha = obtener_spec_sha(spec_rel)
    spec_autor = obtener_spec_autor(spec_rel)

    print(f"[spec] {spec_rel} (sha {spec_sha[:12]})")
    print(f"[autor] Chat: {spec_autor}")
    print(f"[rol esperado] {rol_esperado}")

    if spec_autor != rol_esperado:
        sys.exit(
            f"[FALLO] autoría: último commit de {spec_rel} es Chat: {spec_autor}, "
            f"pero roles_por_linea exige {rol_esperado} para {args.sigla}"
        )
    print("[autoría] OK")

    texto = spec_path.read_text(encoding="utf-8")
    descripcion = extraer_descripcion(texto)
    por_que = extraer_por_que(texto)

    if not descripcion:
        sys.exit("[FALLO] no se pudo extraer descripción del spec")

    campo_desc = f"descripcion:{args.sigla}"
    campo_pq = f"por_que:{args.sigla}"

    print(f"[nodo] {SOL_ID}")
    print(f"[{campo_desc}] ({len(descripcion)} chars) {descripcion[:80]}...")
    if por_que:
        print(f"[{campo_pq}] ({len(por_que)} chars) {por_que[:80]}...")
    else:
        print(f"[{campo_pq}] (vacío — solo 1 párrafo en Solución)")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    row = conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone()
    if not row:
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe en el registro")

    campos = {campo_desc: descripcion}
    if por_que:
        campos[campo_pq] = por_que

    cambios = []
    for campo, valor in campos.items():
        existente = conn.execute(
            "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
            (SOL_ID, campo),
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
            print(f"[dry-run] {op} {SOL_ID}.{campo} = {valor[:60]}...")
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
                (SOL_ID, campo, valor, "propuesto", fuente, ACTOR, ts),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "afirmacion_spec", SOL_ID, f"{campo} = {valor[:80]}... · fuente: {fuente} · autor: {spec_autor}"),
            )
            print(f"[{op}] {SOL_ID}.{campo}")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {len(cambios)} afirmaciones escritas en {SOL_ID} desde {spec_rel} (autor {spec_autor})")


if __name__ == "__main__":
    main()
