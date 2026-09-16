#!/usr/bin/env python3
"""Comprobación del docker-compose.demo.yml sin necesitar docker CLI.

    python microservicio/demo/comprobar_compose.py

Ejecutar desde la raíz del worktree de plantilla. Resultado:
  exit 0 + "compose demo OK: N servicios"
  exit 1 + motivo si falla.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FALLO compose: pyyaml no instalado (pip install pyyaml)", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
COMPOSE_FILE = SCRIPT_DIR / "docker-compose.demo.yml"
README_FILE = SCRIPT_DIR / "README.md"

REQUIRED_SERVICES = {"rag-banking-agent", "como-estoy-hecho", "postgres"}
EXPECTED_PORTS = {"rag-banking-agent": "8000", "como-estoy-hecho": "8010"}
SECRET_PATTERNS = re.compile(
    r"^(sk-|ghp_|gho_|password123|changeme$|secret$)", re.IGNORECASE
)


def fallo(msg: str) -> None:
    print(f"FALLO compose: {msg}", file=sys.stderr)
    sys.exit(1)


def check_file_exists() -> dict:
    print("[1/5] docker-compose.demo.yml existe ...")
    if not COMPOSE_FILE.exists():
        fallo(f"fichero no encontrado: {COMPOSE_FILE}")
    with open(COMPOSE_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        fallo("docker-compose.demo.yml no es un YAML válido")
    print("  fichero presente y parseable")
    return data


def check_services(data: dict) -> dict:
    print("[2/5] Servicios requeridos ...")
    services = data.get("services", {})
    if not services:
        fallo("no hay sección 'services' en el compose")
    missing = REQUIRED_SERVICES - set(services.keys())
    if missing:
        fallo(f"servicios ausentes: {', '.join(sorted(missing))}")
    print(f"  {len(services)} servicios: {', '.join(sorted(services.keys()))}")
    return services


def check_healthchecks(services: dict) -> None:
    print("[3/5] Healthchecks en servicios de app ...")
    for name in ["rag-banking-agent", "como-estoy-hecho", "postgres"]:
        svc = services.get(name, {})
        if "healthcheck" not in svc:
            fallo(f"servicio '{name}' sin healthcheck")
    print("  healthchecks presentes en los 3 servicios")


def check_no_secrets(services: dict) -> None:
    print("[4/5] Sin secretos hardcodeados ...")
    for svc_name, svc in services.items():
        env = svc.get("environment", {})
        if isinstance(env, dict):
            items = env.items()
        elif isinstance(env, list):
            items = []
            for entry in env:
                if "=" in str(entry):
                    k, v = str(entry).split("=", 1)
                    items.append((k, v))
        else:
            continue
        for key, value in items:
            val_str = str(value)
            if SECRET_PATTERNS.search(val_str):
                fallo(f"servicio '{svc_name}': variable '{key}' parece contener un secreto real: '{val_str[:20]}...'")
    print("  sin secretos hardcodeados detectados")


def check_ports(services: dict) -> None:
    print("[5/5] Puertos publicados ...")
    for svc_name, expected_port in EXPECTED_PORTS.items():
        svc = services.get(svc_name, {})
        ports = svc.get("ports", [])
        port_strs = [str(p) for p in ports]
        found = any(expected_port in p for p in port_strs)
        if not found:
            fallo(f"servicio '{svc_name}': puerto {expected_port} no publicado")
    print(f"  puertos correctos: {', '.join(f'{k}:{v}' for k, v in EXPECTED_PORTS.items())}")


def main() -> None:
    data = check_file_exists()
    services = check_services(data)
    check_healthchecks(services)
    check_no_secrets(services)
    check_ports(services)
    print(f"\ncompose demo OK: {len(services)} servicios")


if __name__ == "__main__":
    main()
