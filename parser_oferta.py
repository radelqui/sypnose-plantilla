"""Extrae las líneas literales de la oferta desde el texto crudo (oferta-coforge.txt).
TRASPASO-4 A1: C1 raíces = dato; ninguna frase escrita a mano en el molde.

    python3 parser_oferta.py --txt oferta-coforge.txt [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def extraer_lineas(texto: str) -> list[dict]:
    lineas = []
    seccion = None
    idx = 0
    for raw in texto.splitlines():
        line = raw.strip()
        if line.lower().startswith("key responsibilities"):
            seccion = "responsabilidad"
            continue
        if line.lower().startswith("nice to have"):
            seccion = "deseable"
            continue
        if not line or not line.startswith("•"):
            continue
        idx += 1
        frase = line.lstrip("•").strip()
        frase = re.sub(r"\s+", " ", frase)
        lineas.append({
            "idx": idx,
            "id": f"T{idx:02d}",
            "seccion": seccion or "sin_seccion",
            "texto": frase,
        })
    return lineas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", required=True, help="ruta al fichero de texto crudo de la oferta")
    ap.add_argument("--json", dest="as_json", action="store_true", help="salida JSON en vez de tabla")
    args = ap.parse_args()

    texto = Path(args.txt).read_text(encoding="utf-8")
    lineas = extraer_lineas(texto)

    if not lineas:
        sys.exit("[FALLO] no se encontraron líneas con viñeta '•' en el texto")

    if args.as_json:
        print(json.dumps(lineas, ensure_ascii=False, indent=2))
    else:
        print(f"{len(lineas)} líneas extraídas:")
        for l in lineas:
            print(f"  {l['id']} [{l['seccion'][:4]}] {l['texto']}")


if __name__ == "__main__":
    main()
