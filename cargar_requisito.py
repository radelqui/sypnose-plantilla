"""Carga un requisito desde un spec.md al registro SYPNOSE.

Lee la sección R<n> del spec, extrae EARS (blockquote) y comprobación (bash fence),
pasa la barrera, hace backup_registro() ANTES de escribir, y registra evento.
Idempotente: si EARS y comprobación ya coinciden, 0 cambios.

    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db T01 R1 specs/T01/spec.md
    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db T01 R1 specs/T01/spec.md --dry-run
"""
from __future__ import annotations

import argparse
import re
import sqlite3
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


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def extraer_seccion_r(texto: str, ref: str) -> str:
    patron = re.compile(rf"^## {re.escape(ref)}\b.*$", re.MULTILINE)
    m = patron.search(texto)
    if not m:
        sys.exit(f"[FALLO] sección '## {ref}' no encontrada en el spec")
    inicio = m.end()
    siguiente = re.search(r"^## ", texto[inicio:], re.MULTILINE)
    if siguiente:
        return texto[inicio:inicio + siguiente.start()]
    return texto[inicio:]


def extraer_ears(seccion: str) -> str:
    lineas = seccion.split("\n")
    en_ears = False
    ears_lineas = []
    for linea in lineas:
        if re.match(r"\*\*EARS", linea):
            en_ears = True
            continue
        if en_ears:
            if linea.startswith(">"):
                ears_lineas.append(linea.lstrip("> ").rstrip())
            elif ears_lineas and not linea.strip():
                break
            elif ears_lineas:
                break
    if not ears_lineas:
        sys.exit("[FALLO] bloque EARS (blockquote >) no encontrado en la sección")
    return " ".join(ears_lineas)


def extraer_comprobacion(seccion: str) -> str:
    m = re.search(r"\*\*Comprobación[^*]*\*\*", seccion)
    if not m:
        sys.exit("[FALLO] '**Comprobación ...**' no encontrado en la sección")
    resto = seccion[m.end():]
    fence = re.search(r"```(?:bash)?\s*\n(.*?)```", resto, re.DOTALL)
    if not fence:
        sys.exit("[FALLO] bloque ```bash``` no encontrado tras Comprobación")
    return fence.group(1).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga requisito desde spec.md al registro")
    ap.add_argument("sigla", help="sigla de la línea, ej. T01")
    ap.add_argument("linea", help="referencia del requisito, ej. R1")
    ap.add_argument("spec", help="ruta al spec.md relativa a plantilla/")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--actor", default=ACTOR)
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    spec_path = PLANTILLA_DIR / args.spec
    if not spec_path.exists():
        sys.exit(f"[FALLO] spec no encontrado: {spec_path}")

    plan_id = f"PLAN-CS-{args.sigla}"
    ref = args.linea

    texto = spec_path.read_text(encoding="utf-8")
    seccion = extraer_seccion_r(texto, ref)
    ears = extraer_ears(seccion)
    comprobacion = extraer_comprobacion(seccion)

    print(f"[spec] {spec_path.relative_to(PLANTILLA_DIR)}")
    print(f"[plan_id] {plan_id}")
    print(f"[ref] {ref}")
    print(f"[ears] {ears[:80]}{'...' if len(ears) > 80 else ''}")
    print(f"[comprobacion] {comprobacion}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    existente = conn.execute(
        "SELECT ears, comprobacion FROM requisito WHERE plan_id=? AND ref=?",
        (plan_id, ref),
    ).fetchone()

    if existente:
        ears_actual, comp_actual = existente
        if ears_actual == ears and comp_actual == comprobacion:
            print(f"[idempotente] {plan_id} {ref} ya tiene EARS y comprobación idénticos. 0 cambios.")
            conn.close()
            return

    if args.dry_run:
        print("[dry-run] habría escrito:")
        if existente:
            print(f"  UPDATE requisito SET ears=..., comprobacion=... WHERE plan_id={plan_id} AND ref={ref}")
        else:
            print(f"  INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES ({plan_id}, {ref}, ...)")
        conn.close()
        return

    b = backup_registro(conn, db_path, "requisito")

    conn.execute("BEGIN IMMEDIATE")
    try:
        if existente:
            conn.execute(
                "UPDATE requisito SET ears=?, comprobacion=? WHERE plan_id=? AND ref=?",
                (ears, comprobacion, plan_id, ref),
            )
            accion = "requisito_actualizado"
            print(f"[update] {plan_id} {ref}")
        else:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, ref, ears, comprobacion),
            )
            accion = "requisito_cargado"
            print(f"[insert] {plan_id} {ref}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (
                ahora(),
                args.actor,
                accion,
                plan_id,
                f"{ref} EARS cargado de {args.spec}",
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {plan_id} {ref} cargado desde {args.spec}")


if __name__ == "__main__":
    main()
