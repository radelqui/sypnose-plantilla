#!/usr/bin/env python3
"""Comprobación integrada del esqueleto: instancia, make test, diff vacío.

    python microservicio/comprobar_esqueleto.py

Ejecutar desde la raíz del worktree de plantilla. Resultado:
  exit 0 + "OK esqueleto: N passed, diff=0"
  exit 1 + motivo si falla.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

NOMBRE = "demo-x"
PUERTO = 8010
DOMINIO = "demo_x"

SCRIPT_DIR = Path(__file__).resolve().parent
INSTANCIAR = SCRIPT_DIR / "instanciar_microservicio.py"
DESTINO = SCRIPT_DIR / ".tmp" / NOMBRE


def fallo(msg: str) -> None:
    print(f"FALLO esqueleto: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not INSTANCIAR.exists():
        fallo(f"instanciar_microservicio.py no encontrado: {INSTANCIAR}")

    if DESTINO.exists():
        shutil.rmtree(DESTINO)

    print(f"[1/3] Instanciando {NOMBRE} en {DESTINO} ...")
    r = subprocess.run(
        [sys.executable, str(INSTANCIAR), NOMBRE,
         "--puerto", str(PUERTO), "--destino", str(DESTINO)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        fallo(f"instanciar falló (exit {r.returncode}):\n{r.stderr}\n{r.stdout}")
    print(r.stdout)

    print(f"[2/3] make test en {DESTINO} ...")
    r = subprocess.run(
        ["make", "test"],
        cwd=str(DESTINO), capture_output=True, text=True,
    )
    if r.returncode != 0:
        fallo(f"make test falló (exit {r.returncode}):\n{r.stderr}\n{r.stdout}")

    m = re.search(r"(\d+) passed", r.stdout)
    n_passed = m.group(1) if m else "?"
    print(f"  tests: {n_passed} passed")

    print(f"[3/3] git diff fuera de app/{DOMINIO}/ y tests/{DOMINIO}/ ...")
    r = subprocess.run(
        ["git", "diff", "--stat", "esqueleto-v1..HEAD", "--",
         ".", f":!app/{DOMINIO}/", f":!tests/{DOMINIO}/"],
        cwd=str(DESTINO), capture_output=True, text=True,
    )
    if r.returncode != 0:
        fallo(f"git diff falló (exit {r.returncode}):\n{r.stderr}")

    diff_lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    n_diff = len(diff_lines)
    if n_diff != 0:
        fallo(f"diff fuera de dominio no vacío ({n_diff} ficheros):\n{r.stdout}")

    print(f"\nOK esqueleto: {n_passed} passed, diff=0")


if __name__ == "__main__":
    main()
