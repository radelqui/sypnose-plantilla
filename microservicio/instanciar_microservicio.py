#!/usr/bin/env python3
"""Instancia un microservicio nuevo a partir del esqueleto SYPNOSE.

    python microservicio/instanciar_microservicio.py demo-x --puerto 8010 --destino /tmp/demo-x

Copia el esqueleto, parametriza nombre/puerto/dominio, crea directorios
de dominio (app/<dominio>/ y tests/<dominio>/), inicializa git y hace
el commit inicial con tag esqueleto-v1.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ESQUELETO_DIR = SCRIPT_DIR / "esqueleto"

ORIGEN_MARCA = "# Origen: plantilla/microservicio/esqueleto/{rel} · instanciado por instanciar_microservicio.py"
ORIGEN_MARCA_YAML = "# Origen: plantilla/microservicio/esqueleto/{rel}"
ORIGEN_MARCA_DOCKER = "# Origen: plantilla/microservicio/esqueleto/{rel}"

TEXT_EXTENSIONS = {
    ".py", ".yml", ".yaml", ".toml", ".txt", ".md", ".cfg", ".ini",
    ".sh", ".bash", ".json", ".html", ".css", ".js", ".env", ".example",
}

BINARY_GLOBS = set()


def nombre_a_dominio(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", nombre.lower().strip("-_ "))


def nombre_a_titulo(nombre: str) -> str:
    return "".join(word.capitalize() for word in re.split(r"[-_ ]+", nombre))


def es_texto(path: Path) -> bool:
    if path.suffix in TEXT_EXTENSIONS:
        return True
    if path.name in ("Dockerfile", "Makefile", ".dockerignore", ".gitignore", "Procfile"):
        return True
    return False


def agregar_marca_origen(contenido: str, rel: str, path: Path) -> str:
    marca = ORIGEN_MARCA.format(rel=rel)
    if path.name == "Dockerfile":
        marca = ORIGEN_MARCA_DOCKER.format(rel=rel)
    elif path.suffix in (".yml", ".yaml"):
        marca = ORIGEN_MARCA_YAML.format(rel=rel)

    lineas = contenido.split("\n")
    if lineas and lineas[0].startswith("#!"):
        return lineas[0] + "\n" + marca + "\n" + "\n".join(lineas[1:])
    return marca + "\n" + contenido


def parametrizar(contenido: str, nombre: str, puerto: int, dominio: str, titulo: str) -> str:
    contenido = contenido.replace("{{SERVICE_NAME}}", nombre)
    contenido = contenido.replace("{{SERVICE_PORT}}", str(puerto))
    contenido = contenido.replace("{{DOMAIN}}", dominio)
    contenido = contenido.replace("{{DOMAIN_TITLE}}", titulo)
    return contenido


def copiar_esqueleto(destino: Path, nombre: str, puerto: int, dominio: str, titulo: str) -> list[str]:
    if not ESQUELETO_DIR.exists():
        sys.exit(f"[FALLO] esqueleto no encontrado: {ESQUELETO_DIR}")

    archivos_copiados = []

    for src in sorted(ESQUELETO_DIR.rglob("*")):
        if src.is_dir():
            continue
        if src.name == ".gitkeep":
            continue

        rel = src.relative_to(ESQUELETO_DIR)
        rel_str = str(rel).replace("\\", "/")

        dst_rel = rel_str.replace("{{DOMAIN}}", dominio)
        dst = destino / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if es_texto(src):
            contenido = src.read_text(encoding="utf-8")
            contenido = parametrizar(contenido, nombre, puerto, dominio, titulo)
            contenido = agregar_marca_origen(contenido, rel_str, src)
            dst.write_text(contenido, encoding="utf-8")
        else:
            shutil.copy2(src, dst)

        archivos_copiados.append(dst_rel)

    return archivos_copiados


def crear_dominio(destino: Path, dominio: str, titulo: str, nombre: str, puerto: int) -> list[str]:
    archivos = []

    app_domain = destino / "app" / dominio
    app_domain.mkdir(parents=True, exist_ok=True)
    init = app_domain / "__init__.py"
    init.write_text(
        f'# Dominio de negocio: {nombre}\n'
        f'# TODO: implementar lógica de {titulo}\n',
        encoding="utf-8",
    )
    archivos.append(f"app/{dominio}/__init__.py")

    tests_domain = destino / "tests" / dominio
    tests_domain.mkdir(parents=True, exist_ok=True)
    tinit = tests_domain / "__init__.py"
    tinit.write_text("", encoding="utf-8")
    archivos.append(f"tests/{dominio}/__init__.py")

    tfile = tests_domain / f"test_{dominio}.py"
    tfile.write_text(
        f'# Origen: generado por instanciar_microservicio.py (dominio {nombre})\n'
        f'def test_{dominio}_placeholder():\n'
        f'    """Placeholder — reemplazar con tests del dominio."""\n'
        f'    assert True\n',
        encoding="utf-8",
    )
    archivos.append(f"tests/{dominio}/test_{dominio}.py")

    static_dir = app_domain / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    url_name = nombre  # nombre already uses dashes
    index = static_dir / "index.html"
    index.write_text(
        f'<!doctype html>\n'
        f'<html lang="es">\n'
        f'<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{nombre} — {titulo}</title></head>\n'
        f'<body>\n'
        f'<div id="root"></div>\n'
        f'<script>document.getElementById("root").textContent = '
        f'"{titulo} UI — react placeholder";</script>\n'
        f'</body>\n'
        f'</html>\n',
        encoding="utf-8",
    )
    archivos.append(f"app/{dominio}/static/index.html")

    return archivos


def init_git(destino: Path, nombre: str) -> None:
    subprocess.run(["git", "init"], cwd=destino, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=destino, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"esqueleto: {nombre} instanciado desde plantilla SYPNOSE"],
        cwd=destino, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "tag", "esqueleto-v1"],
        cwd=destino, capture_output=True, check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Instancia un microservicio desde el esqueleto SYPNOSE",
    )
    ap.add_argument("nombre", help="nombre del microservicio (ej. demo-x, como-estoy-hecho)")
    ap.add_argument("--puerto", type=int, required=True, help="puerto HTTP (ej. 8010)")
    ap.add_argument("--destino", required=True, help="directorio destino")
    ap.add_argument("--dominio", help="nombre del dominio Python (default: nombre con _ en vez de -)")
    args = ap.parse_args()

    nombre = args.nombre
    puerto = args.puerto
    destino = Path(args.destino).resolve()
    dominio = args.dominio or nombre_a_dominio(nombre)
    titulo = nombre_a_titulo(nombre)

    print(f"[instanciar] {nombre}")
    print(f"  puerto:  {puerto}")
    print(f"  destino: {destino}")
    print(f"  dominio: {dominio}")
    print(f"  titulo:  {titulo}")
    print(f"  esqueleto: {ESQUELETO_DIR}")

    if destino.exists() and any(destino.iterdir()):
        sys.exit(f"[FALLO] destino no está vacío: {destino}")

    destino.mkdir(parents=True, exist_ok=True)

    archivos = copiar_esqueleto(destino, nombre, puerto, dominio, titulo)
    print(f"\n[esqueleto] {len(archivos)} archivos copiados")

    dominio_archivos = crear_dominio(destino, dominio, titulo, nombre, puerto)
    print(f"[dominio] {len(dominio_archivos)} archivos de dominio creados")

    init_git(destino, nombre)
    print(f"\n[git] repo inicializado con tag esqueleto-v1")

    total = len(archivos) + len(dominio_archivos)
    print(f"\n[OK] {nombre} instanciado en {destino} ({total} archivos)")


if __name__ == "__main__":
    main()
