"""B8: instala el caparazón SYPNOSE en una carpeta de chat (hooks, commit-msg, .mcp.json, settings.json, sección de CLAUDE.md).

    python instalar_caparazon.py <carpeta> [--modo prueba|real] [--worktree <ruta>] [--worktree-extra "<ruta>:<patrón>[,<patrón>]"]...
                                 [--prefijo-planes PLAN-CS-] [--plan-id PLAN-CS-T01]
    python instalar_caparazon.py <carpeta> --desinstalar

Escribe el marcador INSTALADO junto a los módulos y SYPNOSE_MODO en .claude/settings.json. Las sesiones de la carpeta solo escriben en
vivo en el registro y la KB con --modo real; con --modo prueba (por defecto) los eventos se quedan en la cola local con aviso.
Idempotente: reinstalar deja los mismos ficheros. Desinstalar retira solo lo que puso el caparazón y conserva estado y pendientes.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _flujo in (sys.stdout, sys.stderr):
    _flujo.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parent
MODULOS = ["comun.py", "cerco.py", "brief.py", "prompt_submit.py", "pre_tool_use.py", "post_tool_use.py", "stop.py",
           "model_switch.py", "commit_msg.py", "flush.py", "cabeceras_github.py"]
PRECIOS = RAIZ.parent / "precios.yaml"
SERVIDORES = ("sypnose", "knowledge-hub", "github")
MARCA_INI, MARCA_FIN = "<!-- caparazon:inicio -->", "<!-- caparazon:fin -->"
MARCADOR = "INSTALADO"


def posix(ruta: Path | str) -> str:
    return str(ruta).replace("\\", "/")


def worktrees_extra(valores: list[str]) -> list[dict]:
    """--worktree-extra "<ruta>:<patrón>[,<patrón>]" (repetible) → [{ruta, permitidos}], agrupado por ruta absoluta."""
    res: dict[str, list[str]] = {}
    for valor in valores:
        ruta, sep, patrones = valor.rpartition(":")
        if not sep or not Path(ruta).is_absolute() or not patrones.strip():
            sys.exit(f"[caparazón] --worktree-extra necesita <ruta absoluta>:<patrón> (llegó '{valor}')")
        lista = res.setdefault(str(Path(ruta).resolve()), [])
        lista += [p.strip() for p in patrones.split(",") if p.strip() and p.strip() not in lista]
    return [{"ruta": r, "permitidos": p} for r, p in res.items()]


def sustituir(valor, variables: dict):
    if isinstance(valor, str):
        for k, v in variables.items():
            valor = valor.replace("{{" + k + "}}", v)
        return valor
    if isinstance(valor, list):
        return [sustituir(x, variables) for x in valor]
    if isinstance(valor, dict):
        return {k: sustituir(v, variables) for k, v in valor.items()}
    return valor


def leer_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def escribir(p: Path, texto: str) -> bool:
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_text(encoding="utf-8") == texto:
        return False
    with p.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return True


def escribir_json(p: Path, datos: dict) -> bool:
    return escribir(p, json.dumps(datos, ensure_ascii=False, indent=2) + "\n")


def respaldar_original(p: Path, sello: str, manifiesto: dict) -> None:
    respaldos = manifiesto.setdefault("respaldos", {})
    if p.name in respaldos:
        return
    respaldos[p.name] = None
    if p.exists():
        respaldos[p.name] = f"{p.name}.bak-caparazon-{sello}"
        shutil.copy2(p, p.with_name(respaldos[p.name]))
        print(f"  respaldo del original: {respaldos[p.name]}")


def git(wt: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True, check=check)


def es_nuestro(handler: dict, dir_capa: Path) -> bool:
    return any(posix(dir_capa).lower() in posix(a).lower() for a in handler.get("args", []))


def quitar_hooks(settings: dict, dir_capa: Path, podar_vacio: bool = True) -> None:
    hooks = settings.get("hooks", {})
    for evento in list(hooks):
        grupos = [{**g, "hooks": [h for h in g.get("hooks", []) if not es_nuestro(h, dir_capa)]} for g in hooks[evento]]
        grupos = [g for g in grupos if g["hooks"]]
        if grupos:
            hooks[evento] = grupos
        else:
            del hooks[evento]
    if not hooks and podar_vacio:
        settings.pop("hooks", None)


def instalar(args, carpeta: Path, wt: Path) -> None:
    dir_claude = carpeta / ".claude"
    dir_capa = dir_claude / "caparazon"
    manifiesto_p = dir_capa / "instalacion.json"
    manifiesto = leer_json(manifiesto_p)
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    ssh_bin = shutil.which("ssh") or "ssh"
    print(f"[caparazón] instalando en {carpeta} (worktree {wt})")

    for nombre in MODULOS:
        origen = RAIZ / "caparazon" / nombre
        destino = dir_capa / nombre
        if escribir(destino, origen.read_text(encoding="utf-8")):
            print(f"  módulo {nombre}")
    if escribir(dir_capa / "precios.yaml", PRECIOS.read_text(encoding="utf-8")):
        print(f"  precios.yaml (tabla canónica {PRECIOS})")
    config = {
        "carpeta": carpeta.name, "carpeta_ruta": str(carpeta), "worktree": str(wt),
        "coleccion": args.coleccion, "kb_proyecto": args.kb_proyecto, "prefijo_planes": args.prefijo_planes,
        "plan_id": args.plan_id, "verificador": args.verificador, "worktrees_extra": worktrees_extra(args.worktree_extra),
        "registro_url": "http://127.0.0.1:7101", "kb_url": "http://127.0.0.1:18791", "escritura": "ssh",
        "ssh": {"bin": ssh_bin, "destino": args.ssh_destino, "puerto": args.ssh_puerto, "clave": args.ssh_clave, "db": args.registro_db},
    }
    if escribir_json(dir_capa / "config.json", config):
        print("  config.json")
    if escribir_json(dir_capa / MARCADOR, {"carpeta_ruta": str(carpeta), "worktree": str(wt), "instalador": posix(Path(__file__).resolve())}):
        print(f"  {MARCADOR} (marcador de instalación: sin él los hooks no escriben en vivo)")
    githook = f'#!/bin/sh\nexec "{posix(sys.executable)}" "{posix(dir_capa / "commit_msg.py")}" "$1"\n'
    if escribir(dir_capa / "githooks" / "commit-msg", githook):
        print("  githooks/commit-msg")

    variables = {"PYTHON": sys.executable, "CAPARAZON": posix(dir_capa), "PYTHON_POSIX": posix(sys.executable), "MODO": args.modo,
                 "CAPARAZON_POSIX": posix(dir_capa), "SSH": ssh_bin, "SSH_CLAVE": str(Path(args.ssh_clave).expanduser()),
                 "SSH_PUERTO": str(args.ssh_puerto), "SSH_DESTINO": args.ssh_destino, "CARPETA": carpeta.name,
                 "WORKTREE": str(wt), "TUNEL": f"ssh -N -i {args.ssh_clave} -p {args.ssh_puerto} -L 7101:127.0.0.1:7101 "
                                              f"-L 18791:127.0.0.1:18791 -L 18793:127.0.0.1:18793 {args.ssh_destino}"}

    settings_p = dir_claude / "settings.json"
    respaldar_original(settings_p, sello, manifiesto)
    settings = leer_json(settings_p)
    nuevo = sustituir(json.loads((RAIZ / "plantillas" / "settings.json").read_text(encoding="utf-8")), variables)
    quitar_hooks(settings, dir_capa, podar_vacio=False)
    for evento, grupos in nuevo["hooks"].items():
        settings.setdefault("hooks", {}).setdefault(evento, []).extend(grupos)
    anadidos = manifiesto.setdefault("permisos_anadidos", {"allow": [], "deny": []})
    for clave in ("allow", "deny"):
        lista = settings.setdefault("permissions", {}).setdefault(clave, [])
        for regla in nuevo["permissions"][clave]:
            if regla not in lista:
                lista.append(regla)
                anadidos[clave].append(regla)
    habilitados = settings.setdefault("enabledMcpjsonServers", [])
    for s in nuevo["enabledMcpjsonServers"]:
        if s not in habilitados:
            habilitados.append(s)
            manifiesto.setdefault("servidores_habilitados", []).append(s)
    entorno, env_previos = settings.setdefault("env", {}), manifiesto.setdefault("env_previos", {})
    for clave, valor in nuevo["env"].items():
        if clave not in env_previos:
            env_previos[clave] = entorno.get(clave)
        entorno[clave] = valor
    if escribir_json(settings_p, settings):
        print(f"  .claude/settings.json (hooks, permisos, servidores MCP, SYPNOSE_MODO={args.modo})")

    mcp_p = carpeta / ".mcp.json"
    respaldar_original(mcp_p, sello, manifiesto)
    mcp = leer_json(mcp_p)
    plantilla_mcp = sustituir(json.loads((RAIZ / "plantillas" / "mcp.json").read_text(encoding="utf-8")), variables)
    previos = manifiesto.setdefault("mcp_previos", {})
    for nombre, definicion in plantilla_mcp["mcpServers"].items():
        actual = mcp.setdefault("mcpServers", {}).get(nombre)
        if nombre not in previos:
            previos[nombre] = actual
        mcp["mcpServers"][nombre] = definicion
    if escribir_json(mcp_p, mcp):
        print("  .mcp.json (sypnose, knowledge-hub, github)")

    md_p = carpeta / "CLAUDE.md"
    seccion = sustituir((RAIZ / "plantillas" / "CLAUDE.caparazon.md").read_text(encoding="utf-8"), variables).strip()
    bloque = f"{MARCA_INI}\n{seccion}\n{MARCA_FIN}\n"
    texto = md_p.read_text(encoding="utf-8") if md_p.exists() else ""
    patron = re.compile(re.escape(MARCA_INI) + r".*?" + re.escape(MARCA_FIN) + r"\n?", re.S)
    texto = patron.sub(lambda _: bloque, texto) if patron.search(texto) else texto.rstrip("\n") + "\n\n" + bloque
    if escribir(md_p, texto):
        print("  CLAUDE.md (sección caparazón)")

    if git(wt, "config", "--get", "extensions.worktreeConfig", check=False).stdout.strip() != "true":
        git(wt, "config", "extensions.worktreeConfig", "true")
        print("  git: extensions.worktreeConfig=true")
    if git(wt, "config", "--worktree", "--get", "core.hooksPath", check=False).stdout.strip() != posix(dir_capa / "githooks"):
        git(wt, "config", "--worktree", "core.hooksPath", posix(dir_capa / "githooks"))
        print(f"  git: core.hooksPath (solo este worktree) = {posix(dir_capa / 'githooks')}")
    for extra in config["worktrees_extra"]:
        wx = Path(extra["ruta"])
        cima = git(wx, "rev-parse", "--show-toplevel", check=False).stdout.strip() if wx.is_dir() else ""
        if not cima or Path(cima).resolve() != wx.resolve():
            print(f"  aviso: {wx} todavía no es la raíz de un worktree git; el cerco ya lo admite con {extra['permitidos']} y "
                  "commit-msg se engancha al reinstalar cuando exista")
            continue
        if git(wx, "config", "--get", "extensions.worktreeConfig", check=False).stdout.strip() != "true":
            git(wx, "config", "extensions.worktreeConfig", "true")
            print(f"  git ({wx.name}): extensions.worktreeConfig=true")
        if git(wx, "config", "--worktree", "--get", "core.hooksPath", check=False).stdout.strip() != posix(dir_capa / "githooks"):
            git(wx, "config", "--worktree", "core.hooksPath", posix(dir_capa / "githooks"))
            print(f"  git ({wx}): core.hooksPath (solo ese worktree) = {posix(dir_capa / 'githooks')}")
        if str(wx) not in manifiesto.setdefault("hooks_extra", []):
            manifiesto["hooks_extra"].append(str(wx))
    manifiesto.setdefault("instalado_en", sello)
    escribir_json(manifiesto_p, manifiesto)
    print(f"[caparazón] instalado en modo {args.modo}. Abre el chat en la carpeta: SessionStart imprimirá el brief."
          + ("" if args.modo == "real" else " En modo prueba los eventos se quedan en la cola local; para escribir en vivo, reinstala con --modo real."))


def desinstalar(carpeta: Path, wt: Path) -> None:
    dir_claude = carpeta / ".claude"
    dir_capa = dir_claude / "caparazon"
    manifiesto = leer_json(dir_capa / "instalacion.json")
    if not manifiesto:
        sys.exit(f"[caparazón] {carpeta} no tiene caparazón instalado")
    print(f"[caparazón] desinstalando de {carpeta}")
    settings_p = dir_claude / "settings.json"
    settings = leer_json(settings_p)
    quitar_hooks(settings, dir_capa)
    for clave, reglas in manifiesto.get("permisos_anadidos", {}).items():
        lista = [r for r in settings.get("permissions", {}).get(clave, []) if r not in reglas]
        if lista:
            settings["permissions"][clave] = lista
        else:
            settings.get("permissions", {}).pop(clave, None)
    if not settings.get("permissions"):
        settings.pop("permissions", None)
    servidores = [s for s in settings.get("enabledMcpjsonServers", []) if s not in manifiesto.get("servidores_habilitados", [])]
    if servidores:
        settings["enabledMcpjsonServers"] = servidores
    else:
        settings.pop("enabledMcpjsonServers", None)
    entorno = settings.get("env", {})
    for clave, previo in manifiesto.get("env_previos", {}).items():
        if previo is None:
            entorno.pop(clave, None)
        else:
            entorno[clave] = previo
    if not entorno:
        settings.pop("env", None)
    if not settings and manifiesto.get("respaldos", {}).get("settings.json", "") is None:
        settings_p.unlink(missing_ok=True)
        print("  .claude/settings.json retirado (no existía antes)")
    else:
        escribir_json(settings_p, settings)
        print("  .claude/settings.json sin hooks ni permisos del caparazón")
    mcp_p = carpeta / ".mcp.json"
    mcp = leer_json(mcp_p)
    for nombre, previo in manifiesto.get("mcp_previos", {}).items():
        if previo is None:
            mcp.get("mcpServers", {}).pop(nombre, None)
        else:
            mcp.setdefault("mcpServers", {})[nombre] = previo
    if mcp.get("mcpServers"):
        escribir_json(mcp_p, mcp)
    else:
        mcp_p.unlink(missing_ok=True)
    print("  .mcp.json restaurado")
    md_p = carpeta / "CLAUDE.md"
    if md_p.exists():
        patron = re.compile(r"\n*" + re.escape(MARCA_INI) + r".*?" + re.escape(MARCA_FIN) + r"\n?", re.S)
        escribir(md_p, patron.sub("\n", md_p.read_text(encoding="utf-8")).rstrip("\n") + "\n")
        print("  CLAUDE.md sin sección caparazón")
    git(wt, "config", "--worktree", "--unset", "core.hooksPath", check=False)
    print("  git: core.hooksPath del worktree retirado")
    for ruta_extra in manifiesto.get("hooks_extra", []):
        git(Path(ruta_extra), "config", "--worktree", "--unset", "core.hooksPath", check=False)
        print(f"  git ({ruta_extra}): core.hooksPath retirado")
    (dir_capa / MARCADOR).unlink(missing_ok=True)
    print(f"  {MARCADOR} retirado: los módulos que se conservan ya no escriben en vivo")
    destino = dir_claude / f"caparazon-desinstalado-{datetime.now():%Y%m%d-%H%M%S}"
    dir_capa.rename(destino)
    print(f"  módulos, estado y pendientes conservados en {destino.name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Instala o retira el caparazón SYPNOSE en una carpeta de chat")
    ap.add_argument("carpeta")
    ap.add_argument("--worktree", help="worktree git del chat (por defecto <carpeta>/wt)")
    ap.add_argument("--desinstalar", action="store_true")
    ap.add_argument("--modo", choices=("prueba", "real"), default="prueba",
                    help="real: las sesiones de la carpeta escriben en vivo en el registro y la KB (SYPNOSE_MODO=real)")
    ap.add_argument("--worktree-extra", action="append", default=[], metavar="RUTA:PATRONES",
                    help="worktree adicional donde el chat puede escribir (p. ej. su spec en el repo plantilla): <ruta>:<patrón>[,<patrón>]; repetible")
    ap.add_argument("--prefijo-planes", default="PLAN-CS-")
    ap.add_argument("--plan-id", default=None)
    ap.add_argument("--coleccion", default="coforge-santander")
    ap.add_argument("--kb-proyecto", default="coforge-santander")
    ap.add_argument("--verificador", default="07-verificador")
    ap.add_argument("--ssh-destino", default="sypnose@62.171.147.46")
    ap.add_argument("--ssh-puerto", type=int, default=2024)
    ap.add_argument("--ssh-clave", default="~/.ssh/id_ed25519_radelqui")
    ap.add_argument("--registro-db", default="/home/sypnose/sypnose-f1/registry.db")
    args = ap.parse_args()
    carpeta = Path(args.carpeta).resolve()
    wt = Path(args.worktree).resolve() if args.worktree else carpeta / "wt"
    if not carpeta.is_dir():
        sys.exit(f"[caparazón] no existe la carpeta {carpeta}")
    if git(wt, "rev-parse", "--is-inside-work-tree", check=False).stdout.strip() != "true":
        sys.exit(f"[caparazón] {wt} no es un worktree git")
    desinstalar(carpeta, wt) if args.desinstalar else instalar(args, carpeta, wt)


if __name__ == "__main__":
    main()
