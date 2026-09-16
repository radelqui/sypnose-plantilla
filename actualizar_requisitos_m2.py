"""Actualiza requisitos R0/R1 de PLAN-CS-M2 con comprobaciones corregidas.

    python3 actualizar_requisitos_m2.py --db ~/sypnose-f1/registry.db

Lee specs/M2/spec.md y actualiza EARS y comprobación en el registro.
Idempotente: si ya coincide, 0 cambios.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN_ID = "PLAN-CS-M2"
SPEC_PATH = Path(__file__).resolve().parent / "specs" / "M2" / "spec.md"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def extraer_seccion(texto: str, ref: str) -> str:
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
    ears_lineas = []
    en_ears = False
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
        sys.exit("[FALLO] bloque EARS no encontrado")
    return " ".join(ears_lineas)


def extraer_comprobacion(seccion: str) -> str:
    m = re.search(r"\*\*Comprobación[^*]*\*\*", seccion)
    if not m:
        sys.exit("[FALLO] Comprobación no encontrada")
    resto = seccion[m.end():]
    fence = re.search(r"```(?:bash)?\s*\n(.*?)```", resto, re.DOTALL)
    if not fence:
        sys.exit("[FALLO] bloque bash no encontrado")
    return fence.group(1).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Actualizar requisitos M2")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    if not SPEC_PATH.exists():
        sys.exit(f"[FALLO] spec no existe: {SPEC_PATH}")

    texto = SPEC_PATH.read_text(encoding="utf-8")

    requisitos = {}
    for ref in ("R0", "R1"):
        seccion = extraer_seccion(texto, ref)
        requisitos[ref] = {
            "ears": extraer_ears(seccion),
            "comprobacion": extraer_comprobacion(seccion),
        }
        print(f"[spec] {ref}: {requisitos[ref]['ears'][:80]}...")
        print(f"[comp] {requisitos[ref]['comprobacion']}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    cambios = []
    for ref, nuevo in requisitos.items():
        row = conn.execute(
            "SELECT ears, comprobacion FROM requisito WHERE plan_id=? AND ref=?",
            (PLAN_ID, ref),
        ).fetchone()
        if not row:
            sys.exit(f"[FALLO] requisito {PLAN_ID}/{ref} no existe")
        if row[0] == nuevo["ears"] and row[1] == nuevo["comprobacion"]:
            print(f"[idempotente] {ref} ya coincide")
            continue
        cambios.append((ref, nuevo, row))

    if not cambios:
        print("[OK] 0 cambios")
        conn.close()
        return

    if args.dry_run:
        for ref, nuevo, viejo in cambios:
            print(f"[dry-run] UPDATE {ref}")
        conn.close()
        return

    b = backup_registro(conn, db_path, "req-m2")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for ref, nuevo, viejo in cambios:
            conn.execute(
                "UPDATE requisito SET ears=?, comprobacion=? WHERE plan_id=? AND ref=?",
                (nuevo["ears"], nuevo["comprobacion"], PLAN_ID, ref),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "requisito_actualizado", PLAN_ID,
                 f"{ref} comprobación corregida (commit 7a4f4b4): {nuevo['comprobacion'][:80]}"),
            )
            print(f"[update] {ref}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {len(cambios)} requisitos actualizados")


if __name__ == "__main__":
    main()
