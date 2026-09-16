#!/usr/bin/env python3
"""Comprobación de terraform/ en el esqueleto.

    python microservicio/comprobar_terraform.py

Ejecutar desde la raíz del worktree de plantilla. Resultado:
  exit 0 + "OK terraform: ..."
  exit 1 + motivo si falla.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TERRAFORM_DIR = SCRIPT_DIR / "esqueleto" / "terraform"

MAIN_TF = TERRAFORM_DIR / "main.tf"
VARIABLES_TF = TERRAFORM_DIR / "variables.tf"
README = TERRAFORM_DIR / "README.md"

CONTRATO_VARS = [
    "ANTHROPIC_API_KEY",
    "APP_ENV",
    "APP_HOST",
    "APP_PORT",
    "DATABASE_URL",
    "DOCKER_REGISTRY",
    "IMAGE_TAG",
    "LLAMAINDEX_DATABASE_URL",
    "NAMESPACE",
    "OPENAI_API_KEY",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
    "POSTGRES_USER",
]

DEPLOY_COMMANDS = ["terraform init", "terraform plan", "terraform apply"]


def fallo(msg: str) -> None:
    print(f"FALLO terraform: {msg}", file=sys.stderr)
    sys.exit(1)


def check_files_exist() -> None:
    print("[1/4] Ficheros existen ...")
    for f in [MAIN_TF, VARIABLES_TF, README]:
        if not f.exists():
            fallo(f"fichero no encontrado: {f.name}")
    print("  main.tf, variables.tf, README.md presentes")


def check_providers_and_module() -> None:
    print("[2/4] Providers aws/kubernetes y módulo eks ...")
    content = MAIN_TF.read_text(encoding="utf-8")

    if not re.search(r'provider\s+"aws"', content):
        fallo("main.tf no contiene provider \"aws\"")
    if not re.search(r'provider\s+"kubernetes"', content):
        fallo("main.tf no contiene provider \"kubernetes\"")
    if not re.search(r'module\s+"eks"', content):
        fallo("main.tf no contiene module \"eks\"")
    print("  providers aws, kubernetes y módulo eks presentes")


def check_variables() -> None:
    print("[3/4] Variables del CONTRATO-BANCO ...")
    main_content = MAIN_TF.read_text(encoding="utf-8")
    vars_content = VARIABLES_TF.read_text(encoding="utf-8")
    combined = main_content + "\n" + vars_content

    missing = []
    for var in CONTRATO_VARS:
        if var.lower() not in combined.lower():
            missing.append(var)
    if missing:
        fallo(f"variables ausentes: {', '.join(missing)}")
    print(f"  {len(CONTRATO_VARS)} variables del contrato presentes")


def check_readme() -> None:
    print("[4/4] README con instrucciones EKS/AKS ...")
    content = README.read_text(encoding="utf-8")

    for cmd in DEPLOY_COMMANDS:
        if cmd not in content:
            fallo(f"README.md no contiene comando: {cmd}")

    if "EKS" not in content.upper():
        fallo("README.md no menciona EKS")
    if "AKS" not in content.upper():
        fallo("README.md no menciona AKS")

    print("  3 comandos de despliegue + instrucciones EKS/AKS")


def main() -> None:
    check_files_exist()
    check_providers_and_module()
    check_variables()
    check_readme()
    print(f"\nOK terraform: main.tf + variables.tf + README.md validados")


if __name__ == "__main__":
    main()
