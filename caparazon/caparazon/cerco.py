"""Caparazón SYPNOSE: cerco de escritura (worktree + archivos permitidos) y objetivos de escritura de comandos de shell."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
INOCUOS = {"/dev/null", "nul", "$null", "/dev/stdout", "/dev/stderr", "&1", "&2"}
SEPARADORES = {";", "&&", "||", "|", "&", "|&"}
REDIRECCIONES = {">", ">>", "&>", "&>>", ">|"}
ESCRIBE_TODOS = {"rm", "rmdir", "mkdir", "touch", "truncate", "unlink", "shred", "chmod", "chown", "tee", "mv"}
ESCRIBE_DESTINO = {"cp", "install", "ln", "rsync", "scp"}
PS_ESCRIBE = {"set-content", "add-content", "out-file", "new-item", "remove-item", "copy-item", "move-item", "rename-item",
              "clear-content", "tee-object", "ni", "del", "erase", "rd", "ri", "copy", "cpi", "move", "mi", "sc", "ac", "md"}
PS_PARAM_RUTA = {"-path", "-literalpath", "-destination", "-filepath", "-target"}
PS_PARAM_VALOR = {"-value", "-itemtype", "-encoding", "-type", "-name", "-newname", "-inputobject", "-filter", "-include", "-exclude"}
SHELLS_ANIDADAS = {"bash", "sh", "zsh"}
CODIGO_EN_LINEA = {"python", "python3", "py", "node", "perl", "ruby", "pwsh", "powershell"}
PISTAS_ESCRITURA = re.compile(r"open\(|write|unlink|remove|rmtree|mkdir|rename|replace\(|copy|move|Set-Content|Out-File|New-Item|appendFile", re.I)
RUTA_EN_CODIGO = re.compile(r"""['"]((?:[A-Za-z]:[\\/]|/|\.\.[\\/]|~[\\/])[^'"]+)['"]""")
GIT_C = "\x00git-C:"  # objetivo de `git -C <dir>`: opera en ese repositorio; los ficheros que cambie los revisa la auditoría git


def norm(ruta: str, base: str) -> str:
    r = ruta.strip().strip('"').strip("'")
    m = re.match(r"^/([a-zA-Z])(/.*)?$", r)
    if m and os.name == "nt":
        r = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    r = os.path.expandvars(os.path.expanduser(r))
    if not os.path.isabs(r):
        r = os.path.join(base, r)
    return os.path.normcase(os.path.realpath(r))


def dentro(ruta_n: str, base_n: str) -> bool:
    try:
        return os.path.commonpath([ruta_n, base_n]) == base_n
    except ValueError:
        return False


def relativa(ruta_n: str, base_n: str) -> str:
    return os.path.relpath(ruta_n, base_n).replace("\\", "/")


def _patron(glob: str) -> re.Pattern:
    """Glob de permitidos: `**` a cualquier profundidad; `*` y `?` dentro de un solo nivel."""
    return re.compile("".join({"**": ".*", "*": "[^/]*", "?": "[^/]"}.get(p, re.escape(p)) for p in re.split(r"(\*\*|\*|\?)", glob)) + r"\Z")


def rel_permitida(rel: str, permitidos: list[str]) -> bool:
    rel = os.path.normcase(rel).replace("\\", "/")
    for a in permitidos:
        a_n = os.path.normcase(a.strip().strip("`")).replace("\\", "/")
        if "*" in a_n or "?" in a_n:
            if _patron(a_n.strip("/")).match(rel):
                return True
            continue
        es_dir = a_n.endswith("/")
        a_n = a_n.strip("/")
        if rel == a_n or (es_dir and rel.startswith(a_n + "/")):
            return True
    return False


def veredicto(ruta: str, cwd: str, worktree: str, permitidos: list[str], extra_permitidos: list[str] = (),
              worktrees_extra: list[dict] = ()) -> str | None:
    """None si la escritura está permitida; si no, el motivo del bloqueo. Cada escritura se mide contra el worktree que la contiene (el del
    chat o uno de worktrees_extra, el más interno) y sus permitidos. `git -C <dir>` vale dentro de cualquiera de ellos: los ficheros que
    cambie los revisa la auditoría git."""
    if ruta.strip().lower() in INOCUOS:
        return None
    es_git_c = ruta.startswith(GIT_C)
    r = norm(ruta[len(GIT_C):] if es_git_c else ruta, cwd)
    for extra in extra_permitidos:
        if extra and dentro(r, norm(extra, cwd)):
            return None
    zonas = [(norm(worktree, cwd), list(permitidos))] + [(norm(str(x["ruta"]), cwd), list(x.get("permitidos") or []))
                                                        for x in worktrees_extra if x.get("ruta")]
    candidatas = [(base, perm) for base, perm in zonas if dentro(r, base)]
    if not candidatas:
        return f"{r} está fuera del worktree {zonas[0][0]}" + (f" y de los worktrees extra {[z[0] for z in zonas[1:]]}" if len(zonas) > 1 else "")
    base, perm = max(candidatas, key=lambda z: len(z[0]))
    if es_git_c:
        return None
    rel = relativa(r, base)
    if not rel_permitida(rel, perm):
        return f"{rel} está fuera de archivos_permitidos {perm}" + ("" if base == zonas[0][0] else f" del worktree extra {base}")
    return None


def _tokens(linea: str) -> list[str]:
    try:
        lx = shlex.shlex(linea, posix=True, punctuation_chars=";&|<>")
        lx.whitespace_split = True
        lx.escape = ""
        return list(lx)
    except ValueError:
        return linea.split()


def _segmento(seg: list[str], cwd: str, profundidad: int) -> tuple[list[str], str]:
    objetivos, limpio, i = [], [], 0
    while i < len(seg):
        t = seg[i]
        if t in REDIRECCIONES or (t.endswith(">") and set(t) <= set("0123456789&>|")):
            if i + 1 < len(seg):
                objetivos.append(seg[i + 1])
            i += 2
            continue
        if t in (">&", "<", "<<", "<<<"):
            i += 2
            continue
        if limpio and re.fullmatch(r"\d", limpio[-1]) and t.startswith(">"):
            limpio.pop()
        limpio.append(t)
        i += 1
    while limpio and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", limpio[0]) or limpio[0] in ("sudo", "env", "nohup", "time", "command", "exec")):
        limpio.pop(0)
    if not limpio:
        return objetivos, cwd
    orden = re.sub(r"\.exe$", "", os.path.basename(limpio[0]).lower())
    args = limpio[1:]
    posicionales = [a for a in args if not a.startswith("-")]
    if orden in ("cd", "set-location", "sl", "pushd") and posicionales:
        return objetivos, norm(posicionales[0], cwd)
    if orden in ESCRIBE_TODOS:
        objetivos += posicionales
    elif orden in ESCRIBE_DESTINO and posicionales:
        objetivos.append(posicionales[-1])
    elif orden == "sed" and any(a == "--in-place" or a.startswith("-i") for a in args):
        objetivos += posicionales[1:]
    elif orden == "dd":
        objetivos += [a[3:] for a in args if a.startswith("of=")]
    elif orden == "git":
        # -C y --work-tree llevan el repositorio en el que opera git; -c, -b, -B y --reason llevan un valor que no es una ruta.
        posic, j = [], 0
        while j < len(args):
            if args[j] in ("-C", "--work-tree") and j + 1 < len(args):
                objetivos.append(GIT_C + args[j + 1])
                j += 2
            elif args[j] in ("-c", "-b", "-B", "--reason", "--git-dir"):
                j += 2
            else:
                if not args[j].startswith("-"):
                    posic.append(args[j])
                j += 1
        if posic[:1] == ["clone"] and len(posic) >= 3:
            objetivos.append(posic[2])
        elif posic[:2] == ["worktree", "add"] and len(posic) >= 3:
            objetivos.append(posic[2])
    elif orden in SHELLS_ANIDADAS and "-c" in args and profundidad < 3:
        idx = args.index("-c")
        if idx + 1 < len(args):
            objetivos += objetivos_shell(args[idx + 1], cwd, profundidad + 1)
    elif orden == "cmd" and args and args[0].lower() in ("/c", "/k") and profundidad < 3:
        objetivos += objetivos_shell(" ".join(args[1:]), cwd, profundidad + 1)
    elif orden in PS_ESCRIBE:
        j, primero = 0, None
        while j < len(args):
            a = args[j].lower()
            if a in PS_PARAM_RUTA and j + 1 < len(args):
                objetivos.append(args[j + 1])
                j += 2
                continue
            if a in PS_PARAM_VALOR:
                j += 2
                continue
            if not a.startswith("-") and primero is None:
                primero = args[j]
            j += 1
        if primero is not None:
            objetivos.append(primero)
    if orden in CODIGO_EN_LINEA:
        codigo = " ".join(args)
        if PISTAS_ESCRITURA.search(codigo):
            objetivos += RUTA_EN_CODIGO.findall(codigo)
    return objetivos, cwd


def objetivos_shell(comando: str, cwd: str, profundidad: int = 0) -> list[str]:
    """Rutas absolutas normalizadas que el comando podría escribir (heurística; la auditoría git lo complementa)."""
    objetivos = []
    for linea in comando.splitlines():
        segmento, segmentos = [], []
        for t in _tokens(linea):
            if t in SEPARADORES:
                segmentos.append(segmento)
                segmento = []
            else:
                segmento.append(t)
        segmentos.append(segmento)
        for seg in segmentos:
            nuevos, cwd = _segmento(seg, cwd, profundidad)
            # norm() entiende /c/… de Git Bash, ~ y rutas relativas al cwd de ese punto del comando. Con os.path.join, en Python 3.13
            # (os.path.isabs('/c/…') es False) /c/MICD/… acababa en C:\c\MICD\… y ~/x quedaba dentro del worktree.
            objetivos += [n if n.strip().lower() in INOCUOS else GIT_C + norm(n[len(GIT_C):], cwd) if n.startswith(GIT_C) else norm(n, cwd)
                          for n in nuevos]
    return objetivos


def objetivos_herramienta(herramienta: str, entrada: dict, cwd: str) -> list[str]:
    if herramienta in ("Edit", "Write", "MultiEdit"):
        return [entrada.get("file_path", "")]
    if herramienta == "NotebookEdit":
        return [entrada.get("notebook_path", "")]
    if herramienta in ("Bash", "PowerShell"):
        return objetivos_shell(entrada.get("command", ""), cwd)
    return []


def cambios_git(worktree: str) -> set[str] | None:
    try:
        p = subprocess.run(["git", "-C", worktree, "status", "--porcelain=v1", "-uall", "-z"],
                           capture_output=True, timeout=20, creationflags=SIN_VENTANA)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    trozos, rutas, i = p.stdout.decode("utf-8", "replace").split("\0"), set(), 0
    while i < len(trozos):
        t = trozos[i]
        if len(t) >= 4:
            rutas.add(t[3:])
            if t[0] in "RC" or t[1] in "RC":
                i += 1
        i += 1
    return rutas


def ficheros_propios_claude_md(carpeta: Path) -> list[str]:
    md = carpeta / "CLAUDE.md"
    if not md.exists():
        return []
    texto = md.read_text(encoding="utf-8")
    m = re.search(r"^##\s*Ficheros propios\s*$(.*?)(?=^##\s|\Z)", texto, re.M | re.S)
    return re.findall(r"`([^`]+)`", m.group(1)) if m else []
