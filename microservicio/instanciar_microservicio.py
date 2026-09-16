# origen: rag-banking-agent@c7e5f54
#!/usr/bin/env python3
"""Genera un nuevo microservicio a partir del esqueleto reutilizable.

Uso: python microservicio/instanciar_microservicio.py <nombre> --puerto <puerto> [--destino <dir>]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKELETON_DIR = Path(__file__).parent
EXCLUDE = {"instanciar_microservicio.py", "__pycache__", ".git"}


def main():
    parser = argparse.ArgumentParser(description="Instanciar microservicio desde esqueleto")
    parser.add_argument("nombre", help="Nombre del microservicio (snake_case o kebab-case)")
    parser.add_argument("--puerto", type=int, default=8000, help="Puerto del servidor")
    parser.add_argument("--destino", default=None, help="Directorio destino")
    args = parser.parse_args()

    nombre = args.nombre
    snake = nombre.replace("-", "_")
    destino = Path(args.destino or nombre)

    if destino.exists():
        print(f"Error: {destino} ya existe", file=sys.stderr)
        sys.exit(1)

    destino.mkdir(parents=True)
    for item in SKELETON_DIR.iterdir():
        if item.name in EXCLUDE:
            continue
        target = destino / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, target)

    config = destino / "app" / "core" / "config.py"
    text = config.read_text()
    text = text.replace('app_name: str = "microservicio"', f'app_name: str = "{nombre}"')
    config.write_text(text)

    makefile = destino / "Makefile"
    text = makefile.read_text()
    text = text.replace("--port 8000", f"--port {args.puerto}")
    makefile.write_text(text)

    def git(*cmd):
        subprocess.run(["git", "-C", str(destino)] + list(cmd), check=True, capture_output=True)

    git("init")
    git("add", ".")
    git("commit", "-m", f"esqueleto: {nombre} desde plantilla")
    git("tag", "esqueleto-v1")

    domain_app = destino / "app" / snake
    domain_tests = destino / "tests" / snake
    domain_app.mkdir()
    (domain_app / "__init__.py").write_text("")
    domain_tests.mkdir()
    (domain_tests / "__init__.py").write_text("")
    git("add", ".")
    git("commit", "-m", f"dominio: {snake} (vacío)")

    print(f"Microservicio '{nombre}' creado en {destino}")
    print(f"  esqueleto-v1 tag creado")
    print(f"  Dominio: app/{snake}/ y tests/{snake}/")


if __name__ == "__main__":
    main()
