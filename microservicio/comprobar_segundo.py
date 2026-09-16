#!/usr/bin/env python3
"""Comprobación del segundo microservicio (como-estoy-hecho).

    python microservicio/comprobar_segundo.py [--repo <path>]

Ejecutar desde la raíz del worktree de plantilla (o con --repo).
R2: arbol contra arbol esqueleto-v1.2 (plantilla) vs instancia;
    ficheros exclusivos=0, lineas distintas solo marca/nombre/puerto.
R3: health OK con motor falso + UI react+viewport.
    Requiere el venv de como-estoy-hecho (fastapi, uvicorn, pytest);
    usar --skip-server si no hay venv instalado.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DOMINIO = "como_estoy_hecho"
PUERTO = 8010
SCRIPT_DIR = Path(__file__).resolve().parent
ESQUELETO_DIR = SCRIPT_DIR / "esqueleto"
DEFAULT_REPO = SCRIPT_DIR.parent.parent / "como-estoy-hecho"

MARCA_PREFIXES = ("# Origen:", "# origen:")
PLACEHOLDERS = {
    "{{SERVICE_NAME}}": "como-estoy-hecho",
    "{{SERVICE_PORT}}": "8010",
    "{{DOMAIN}}": DOMINIO,
}


def fallo(msg: str) -> None:
    print(f"FALLO segundo: {msg}", file=sys.stderr)
    sys.exit(1)


def _expand_placeholders(line: str) -> str:
    """Replace esqueleto placeholders with the instance values."""
    for ph, val in PLACEHOLDERS.items():
        line = line.replace(ph, val)
    return line


def check_r2(repo: Path) -> None:
    print("[R2] arbol contra arbol (esqueleto vs instancia) ...")
    if not ESQUELETO_DIR.is_dir():
        fallo(f"directorio esqueleto no encontrado: {ESQUELETO_DIR}")

    skip_dirs = {".git", ".venv", ".pytest_cache", "__pycache__"}

    esq_files: set[str] = set()
    for p in ESQUELETO_DIR.rglob("*"):
        if p.is_file():
            rel = p.relative_to(ESQUELETO_DIR)
            if any(part in skip_dirs for part in rel.parts):
                continue
            esq_files.add(str(rel).replace("\\", "/"))

    inst_files: set[str] = set()
    for p in repo.rglob("*"):
        if p.is_file():
            rel = p.relative_to(repo)
            parts = rel.parts
            if any(part in skip_dirs for part in parts):
                continue
            if parts[0] == ".env":
                continue
            if len(parts) >= 2 and parts[0] == "app" and parts[1] == DOMINIO:
                continue
            if len(parts) >= 2 and parts[0] == "tests" and parts[1] == DOMINIO:
                continue
            inst_files.add(str(rel).replace("\\", "/"))

    only_esq = esq_files - inst_files
    only_inst = inst_files - esq_files
    if only_esq:
        fallo(f"R2: {len(only_esq)} ficheros solo en esqueleto: {sorted(only_esq)}")
    if only_inst:
        fallo(f"R2: {len(only_inst)} ficheros solo en instancia (fuera del dominio): {sorted(only_inst)}")

    bad_lines = 0
    total_allowed = 0
    bad_files: list[str] = []
    for rel in sorted(esq_files & inst_files):
        esq_path = ESQUELETO_DIR / rel
        inst_path = repo / rel
        try:
            esq_text = esq_path.read_text(encoding="utf-8").splitlines()
            inst_text = inst_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            if esq_path.read_bytes() != inst_path.read_bytes():
                bad_files.append(f"{rel} (binary differs)")
            continue

        inst_stripped = [l for l in inst_text if not l.startswith(MARCA_PREFIXES)]
        esq_expanded = [_expand_placeholders(l) for l in esq_text]

        file_bad = 0
        file_allowed = 0
        for i, (e, s) in enumerate(zip(esq_expanded, inst_stripped)):
            if e != s:
                file_bad += 1
        extra_esq = len(esq_expanded) - len(inst_stripped)
        extra_inst = len(inst_stripped) - len(esq_expanded)
        if extra_esq > 0:
            file_bad += extra_esq
        if extra_inst > 0:
            file_bad += extra_inst
        file_allowed = len(inst_text) - len(inst_stripped)
        total_allowed += file_allowed

        if file_bad:
            bad_files.append(f"{rel} ({file_bad} lineas)")
            bad_lines += file_bad

    if bad_lines:
        fallo(f"R2: {bad_lines} lineas fuera del esqueleto en {len(bad_files)} ficheros: {bad_files}")

    print(f"  R2 OK: {len(esq_files)} ficheros comunes, 0 exclusivos, "
          f"{total_allowed} lineas distintas (marca/nombre/puerto)")


def check_r3(repo: Path) -> None:
    print("[R3] health + UI con motor falso ...")
    env_file = repo / ".env"
    had_env = env_file.exists()
    if not had_env:
        env_file.write_text("ENGINE_MODE=fake\nAPP_PORT=8010\n", encoding="utf-8")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PUERTO)],
        cwd=str(repo),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    try:
        for _ in range(30):
            time.sleep(1)
            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/health", timeout=3)
                if resp.status == 200:
                    break
            except Exception:
                continue
        else:
            fallo("R3: /health no respondió 200 en 30 segundos")

        print("  /health → 200 OK")

        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/como-estoy-hecho/ui", timeout=5)
        except Exception as e:
            fallo(f"R3: GET /como-estoy-hecho/ui falló: {e}")

        if resp.status != 200:
            fallo(f"R3: /como-estoy-hecho/ui status={resp.status}")

        body = resp.read().decode("utf-8", errors="replace").lower()
        if "react" not in body:
            fallo("R3: /como-estoy-hecho/ui no contiene 'react'")
        if "viewport" not in body:
            fallo("R3: /como-estoy-hecho/ui no contiene 'viewport'")

        print("  /como-estoy-hecho/ui → 200, contains 'react' + 'viewport'")

    finally:
        proc.terminate()
        proc.wait(timeout=5)
        if not had_env:
            env_file.unlink(missing_ok=True)


def check_tests(repo: Path) -> int:
    print("[tests] pytest ...")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", f"tests/{DOMINIO}/", "-q"],
        cwd=str(repo), capture_output=True, text=True,
    )
    if r.returncode != 0:
        fallo(f"pytest falló (exit {r.returncode}):\n{r.stdout}\n{r.stderr}")

    m = re.search(r"(\d+) passed", r.stdout)
    n = int(m.group(1)) if m else 0
    print(f"  {n} passed")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(DEFAULT_REPO),
                    help="path to como-estoy-hecho checkout")
    ap.add_argument("--skip-server", action="store_true",
                    help="skip R3 (server test) if no deps installed")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        fallo(f"no es un repo git: {repo}")

    check_r2(repo)

    if not args.skip_server:
        check_r3(repo)
    else:
        print("[R3] skipped (--skip-server)")

    n = check_tests(repo)

    print(f"\nOK segundo: R2 diff=0, R3 health+UI, {n} tests passed")


if __name__ == "__main__":
    main()
