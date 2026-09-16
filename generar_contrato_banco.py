"""A5.4/A5.5 (16-sep): genera CONTRATO-BANCO.md desde la sección stack de oferta.yaml.

Tabla por grupo: tecnología · lo nuestro · lo que decide el banco · qué cambia · variables.
Variables = nombres de env vars / secretos K8s mencionados en evidencia y config.

    python3 generar_contrato_banco.py [--output CONTRATO-BANCO.md]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import yaml

PLANTILLA_DIR = Path(__file__).resolve().parent
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"

GRUPO_ORDEN = [
    "lenguaje-backend",
    "base-datos",
    "ia-agentes",
    "contenedores-despliegue",
    "cicd-calidad",
    "practicas-ingenieria",
    "opcional",
]

GRUPO_TITULO = {
    "lenguaje-backend": "Lenguaje y framework backend",
    "base-datos": "Base de datos",
    "ia-agentes": "IA y agentes",
    "contenedores-despliegue": "Contenedores y despliegue",
    "cicd-calidad": "CI/CD y calidad",
    "practicas-ingenieria": "Prácticas de ingeniería",
    "opcional": "Opcional / futuro",
}

VARIABLES_POR_TEC = {
    "python311": [],
    "fastapi": ["APP_HOST", "APP_PORT"],
    "pydantic": ["APP_ENV"],
    "sqlalchemy-asyncpg": ["DATABASE_URL", "LLAMAINDEX_DATABASE_URL"],
    "llamaindex": ["LLAMAINDEX_DATABASE_URL"],
    "anthropic-llm": ["ANTHROPIC_API_KEY"],
    "openai-embeddings": ["OPENAI_API_KEY"],
    "sse-starlette": [],
    "postgresql16": ["DATABASE_URL", "LLAMAINDEX_DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"],
    "hnsw-gin": [],
    "docker": ["DOCKER_REGISTRY"],
    "kubernetes": ["NAMESPACE", "IMAGE_TAG"],
    "github-actions": [],
    "pytest": [],
    "ruff": [],
    "bandit": [],
    "trivy": [],
    "react-vue": [],
}


def extraer_variables_unicas() -> list[str]:
    seen = set()
    for vs in VARIABLES_POR_TEC.values():
        seen.update(vs)
    return sorted(seen)


def generar(output: Path):
    oferta = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    stack = oferta.get("stack", {})
    if not stack:
        raise SystemExit("[FALLO] no hay sección 'stack' en oferta.yaml")

    todas = []
    for bloque in ("solucion", "plantilla"):
        for entry in stack.get(bloque, []):
            entry["_bloque"] = bloque
            todas.append(entry)

    por_grupo = defaultdict(list)
    for e in todas:
        por_grupo[e["grupo"]].append(e)

    vars_config = extraer_variables_unicas()

    lineas = []
    lineas.append("# CONTRATO-BANCO.md")
    lineas.append("")
    lineas.append("> Generado automáticamente por `generar_contrato_banco.py` desde `oferta.yaml` § stack.")
    lineas.append("> NO editar a mano: editar oferta.yaml y regenerar.")
    lineas.append("")
    lineas.append("Este documento lista cada tecnología del stack, lo que el POC implementa,")
    lineas.append("lo que el banco puede decidir sustituir, y los ficheros/variables que cambian.")
    lineas.append("0 secretos en código: solo NOMBRES de variables; los VALORES los inyecta el banco.")
    lineas.append("")

    if vars_config:
        lineas.append("## Variables de entorno (inyectadas por el banco)")
        lineas.append("")
        lineas.append("| Variable | Origen |")
        lineas.append("|----------|--------|")
        for v in vars_config:
            lineas.append(f"| `{v}` | K8s Secret / Vault |")
        lineas.append("")

    for grupo in GRUPO_ORDEN:
        entries = por_grupo.get(grupo, [])
        if not entries:
            continue

        titulo = GRUPO_TITULO.get(grupo, grupo)
        lineas.append(f"## {titulo}")
        lineas.append("")
        lineas.append("| Tecnología | Lo nuestro (POC) | Lo que decide el banco | Qué cambia | Variables |")
        lineas.append("|------------|------------------|------------------------|------------|-----------|")

        for e in entries:
            nombre = e["nombre"]
            lo_nuestro = e.get("para_que", "")
            decide = e.get("decide_banco", "—")
            cambia_raw = e.get("que_cambia", [])
            if isinstance(cambia_raw, list):
                cambia = ", ".join(cambia_raw) if cambia_raw else "—"
            else:
                cambia = str(cambia_raw) if cambia_raw else "—"

            tid = e["id"]
            vars_tec = VARIABLES_POR_TEC.get(tid, [])
            vars_str = ", ".join(f"`{v}`" for v in vars_tec) if vars_tec else "—"

            estado = e.get("estado", "")
            if estado == "opcional-no-implementado":
                nombre = f"*{nombre}* (no impl.)"

            lineas.append(f"| {nombre} | {lo_nuestro} | {decide} | {cambia} | {vars_str} |")

        lineas.append("")

    lineas.append("## Notas")
    lineas.append("")
    lineas.append("- Las tecnologías del bloque **plantilla** (registro SQLite, barrera, caparazón, MCP, verificador,")
    lineas.append("  firmas, vista pública, KB, graphify) son artefactos del proceso de desarrollo SYPNOSE.")
    lineas.append("  No entran en producción del banco y no requieren decisión.")
    lineas.append("- Cada variable listada se inyecta vía K8s Secret o Vault; el código solo lee el nombre.")
    lineas.append("- Para sustituir una tecnología, modificar `oferta.yaml` § stack y regenerar este fichero:")
    lineas.append("  `python3 generar_contrato_banco.py`")
    lineas.append("")

    output.write_text("\n".join(lineas), encoding="utf-8")
    print(f"[OK] {output} generado ({len(todas)} tecnologías, {len([g for g in GRUPO_ORDEN if por_grupo.get(g)])} grupos)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(PLANTILLA_DIR / "CONTRATO-BANCO.md"))
    args = p.parse_args()
    generar(Path(args.output))


if __name__ == "__main__":
    main()
