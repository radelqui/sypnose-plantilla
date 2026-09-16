#!/usr/bin/env python3
"""Comprobación del segundo microservicio (como-estoy-hecho).

    python microservicio/comprobar_segundo.py [--repo <path>]

Ejecutar desde la raíz del worktree de plantilla (o con --repo).
R2: diff esqueleto=0 fuera de dominio.
R3: health OK con motor falso + UI react+viewport.
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
DEFAULT_REPO = SCRIPT_DIR.parent.parent / "como-estoy-hecho"


def fallo(msg: str) -> None:
    print(f"FALLO segundo: {msg}", file=sys.stderr)
    sys.exit(1)


def check_r2(repo: Path) -> None:
    print("[R2] diff fuera de dominio ...")
    r = subprocess.run(
        ["git", "diff", "--stat", "esqueleto-v1..HEAD", "--",
         ".", f":!app/{DOMINIO}/", f":!tests/{DOMINIO}/"],
        cwd=str(repo), capture_output=True, text=True,
    )
    if r.returncode != 0:
        fallo(f"git diff falló (exit {r.returncode}):\n{r.stderr}")

    diff_lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    if diff_lines:
        fallo(f"R2: diff fuera de dominio no vacío ({len(diff_lines)} ficheros):\n{r.stdout}")
    print("  R2 OK: diff=0")


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
