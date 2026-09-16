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
SSH_REMOTO = "\x00ssh-git-remoto:"  # B15: git de escritura por SSH → bloqueado
SSH_OPTS_CON_ARG = set("bBcDEeFIiJLlmOopQRSwW")


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
    """Glob de permitidos: `**` a cualquier profundidad; `*` y `?` dentro de un solo nivel. B16: en Windows, re.IGNORECASE."""
    return re.compile("".join({"**": ".*", "*": "[^/]*", "?": "[^/]"}.get(p, re.escape(p)) for p in re.split(r"(\*\*|\*|\?)", glob)) + r"\Z",
                      re.IGNORECASE if os.name == "nt" else 0)


def _fold(s: str) -> str:
    """B16: en Windows, casefold como red de seguridad sobre normcase (os.path.normcase ya baja a minúsculas, pero casefold cubre Unicode)."""
    return s.casefold() if os.name == "nt" else s


def rel_permitida(rel: str, permitidos: list[str]) -> bool:
    rel = _fold(os.path.normcase(rel).replace("\\", "/"))
    for a in permitidos:
        a_n = _fold(os.path.normcase(a.strip().strip("`")).replace("\\", "/"))
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
    if ruta.startswith(SSH_REMOTO):
        return f"git de escritura por SSH bloqueado: {ruta[len(SSH_REMOTO):]}"
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


class ComandoIlegible(ValueError):
    """El cerco no puede tokenizar el comando. Nunca adivina rutas (B11): quien llame bloquea con un mensaje claro."""


HEREDOC = re.compile(r"""<<(-?)[ \t]*(?:'([^'\n]+)'|"([^"\n]+)"|([A-Za-z0-9_.-]+))""")


def _preparar(comando: str) -> str:
    """Texto para shlex, siguiendo las comillas como bash (B11). Hace cuatro cosas:
    - quita los cuerpos de heredoc, que son datos y no órdenes;
    - quita los comentarios y las continuaciones de línea;
    - convierte en ';' los saltos de línea que separan órdenes;
    - trata como heredoc un `<<` dentro de $(…) o `…`, pero no uno dentro de comillas ni dentro de $((…))."""
    out, pila, pendientes, i, n = [], ["N"], [], 0, len(comando)
    while i < n:
        c, cima = comando[i], pila[-1]
        if c == "\n":
            j = i + 1
            for delimitador, con_tabs in pendientes:
                while j < n:
                    fin = comando.find("\n", j)
                    linea = comando[j:] if fin < 0 else comando[j:fin]
                    j = n if fin < 0 else fin + 1
                    if (linea.lstrip("\t") if con_tabs else linea) == delimitador:
                        break
            pendientes = []
            out.append("\n" if cima in ("S", "D") else " ; ")
            i = j
            continue
        if cima == "S":
            if c == "'":
                pila.pop()
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            if comando[i + 1] != "\n":
                out.append(comando[i:i + 2])
            i += 2
            continue
        if cima == "A":
            if comando.startswith("))", i):
                pila.pop()
                out.append("))")
                i += 2
            else:
                out.append(c)
                i += 1
            continue
        if cima == "D":
            if c == '"':
                pila.pop()
            elif comando.startswith("$((", i) or comando.startswith("$(", i):
                pila.append("A" if comando.startswith("$((", i) else "C")
                out.append(comando[i:i + (3 if pila[-1] == "A" else 2)])
                i += 3 if pila[-1] == "A" else 2
                continue
            elif c == "`":
                pila.append("B")
            out.append(c)
            i += 1
            continue
        # N (fuera de comillas), C ($(…)), P ((…)) y B (`…`)
        if c == "#" and (not out or out[-1][-1:] in (" ", "\t", ";", "&", "|", "(")):
            fin = comando.find("\n", i)
            i = n if fin < 0 else fin
            continue
        if comando.startswith("<<", i) and not comando.startswith("<<<", i) and (m := HEREDOC.match(comando, i)):
            pendientes.append((m.group(2) or m.group(3) or m.group(4), m.group(1) == "-"))
            out.append(m.group(0))
            i = m.end()
            continue
        if comando.startswith("$((", i) or comando.startswith("((", i):
            largo = 3 if c == "$" else 2
            pila.append("A")
            out.append(comando[i:i + largo])
            i += largo
            continue
        if comando.startswith("$(", i):
            pila.append("C")
            out.append("$(")
            i += 2
            continue
        if c == "'":
            pila.append("S")
        elif c == '"':
            pila.append("D")
        elif c == "(":
            pila.append("P")
        elif c == ")" and cima in ("C", "P"):
            pila.pop()
        elif c == "`":
            if cima == "B":
                pila.pop()
            else:
                pila.append("B")
        out.append(c)
        i += 1
    return "".join(out)


def _tokens(comando: str) -> list[str]:
    """Tokens del comando entero (B11): sin heredocs y con las comillas respetadas aunque abarquen varias líneas. Si shlex no puede,
    lanza ComandoIlegible. Antes se partía por espacios: 'Coforge Santander' se rompía y el cerco adivinaba rutas."""
    lx = shlex.shlex(_preparar(comando), posix=True, punctuation_chars=";&|<>")
    lx.whitespace_split = True
    lx.escape = ""
    lx.commenters = ""
    try:
        return list(lx)
    except ValueError as e:
        raise ComandoIlegible(str(e)) from None


def _segmentos(comando: str) -> list[list[str]]:
    segmentos, segmento = [], []
    for t in _tokens(comando):
        if t in SEPARADORES:
            segmentos.append(segmento)
            segmento = []
        else:
            segmento.append(t)
    segmentos.append(segmento)
    return segmentos


def _comando_remoto_ssh(args: list[str]) -> str:
    """B15: extrae el comando remoto de los argumentos de ssh (todo lo que va después de [user@]host)."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a.startswith("-") and len(a) == 2 and a[1] in SSH_OPTS_CON_ARG:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        i += 1
        break
    return " ".join(args[i:])


def _objetivos_ssh(args: list[str]) -> list[str]:
    """B15: si el comando remoto SSH contiene git de escritura, emite un marcador SSH_REMOTO que el cerco rechazará."""
    remoto = _comando_remoto_ssh(args)
    if not remoto:
        return []
    try:
        for seg in _segmentos(remoto):
            resto = [t for t in seg if t not in SEPARADORES and t not in REDIRECCIONES]
            while resto and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", resto[0]):
                resto.pop(0)
            while resto and resto[0] in ("sudo", "env", "nohup", "cd", "time", "command"):
                if resto[0] == "cd" and len(resto) > 1:
                    resto = resto[2:]
                else:
                    resto.pop(0)
            if not resto:
                continue
            orden_r = re.sub(r"\.exe$", "", os.path.basename(resto[0]).lower())
            if orden_r == "git" and not _git_consulta(resto[1:]):
                return [SSH_REMOTO + remoto[:200]]
    except (ComandoIlegible, ValueError):
        return [SSH_REMOTO + remoto[:200]]
    return []


def _segmento(seg: list[str], cwd: str, profundidad: int) -> tuple[list[str], str]:
    objetivos, limpio, i = [], [], 0
    while i < len(seg):
        t = seg[i]
        if t in REDIRECCIONES or (t.endswith(">") and set(t) <= set("0123456789&>|")):
            # B21: un dígito solo antes de > o >> es un descriptor de fichero (2>, 1>>), no una ruta
            if limpio and re.fullmatch(r"\d", limpio[-1]):
                limpio.pop()
            if i + 1 < len(seg):
                objetivos.append(seg[i + 1])
            i += 2
            continue
        if t in (">&", "<", "<<", "<<<"):
            # B21: un dígito solo antes de >& es un descriptor (2>&1), no una ruta
            if limpio and re.fullmatch(r"\d", limpio[-1]):
                limpio.pop()
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
    elif orden == "ssh" and profundidad < 3:
        objetivos += _objetivos_ssh(args)
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
    """Rutas absolutas normalizadas que el comando podría escribir (heurística; la auditoría git lo complementa). Si el comando no se
    puede tokenizar, lanza ComandoIlegible."""
    objetivos = []
    for seg in _segmentos(comando):
        nuevos, cwd = _segmento(seg, cwd, profundidad)
        # norm() entiende /c/… de Git Bash, ~ y rutas relativas al cwd de ese punto del comando. Con os.path.join, en Python 3.13
        # (os.path.isabs('/c/…') es False) /c/MICD/… acababa en C:\c\MICD\… y ~/x quedaba dentro del worktree.
        objetivos += [n if n.strip().lower() in INOCUOS or n.startswith(SSH_REMOTO)
                      else GIT_C + norm(n[len(GIT_C):], cwd) if n.startswith(GIT_C) else norm(n, cwd)
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


ORDENES_LECTURA = {"ls", "dir", "cat", "type", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "find", "wc", "sort", "uniq",
                   "cut", "tr", "echo", "printf", "pwd", "cd", "pushd", "popd", "which", "where", "whoami", "hostname", "date", "tree",
                   "stat", "file", "diff", "cmp", "du", "df", "env", "printenv", "basename", "dirname", "realpath", "readlink", "sha256sum",
                   "md5sum", "jq", "column", "nl", "true", "false", "test", "[", "git",
                   "get-content", "gc", "get-childitem", "gci", "get-item", "gi", "select-string", "sls", "get-location", "gl", "test-path",
                   "resolve-path", "measure-object", "select-object", "where-object", "sort-object", "format-table", "format-list",
                   "out-string", "get-date", "write-output", "write-host"}
GIT_CONSULTA = {"status", "log", "diff", "show", "rev-parse", "rev-list", "ls-files", "ls-tree", "ls-remote", "show-ref", "blame", "describe",
                "shortlog", "grep", "cat-file", "merge-base", "name-rev", "for-each-ref", "whatchanged", "range-diff", "version", "help"}
FIND_ESCRIBE = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}


def _git_consulta(args: list[str]) -> bool:
    j = 0
    while j < len(args) and args[j].startswith("-"):
        j += 2 if args[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if j >= len(args):
        return True
    sub, resto = args[j], args[j + 1:]
    posic = [a for a in resto if not a.startswith("-")]
    if any(a.startswith("--output") for a in resto):
        return False
    if sub in GIT_CONSULTA:
        return True
    if sub == "branch":
        return not posic and not any(a in ("-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy", "--force",
                                           "--unset-upstream", "--edit-description") or a.startswith("--set-upstream") for a in resto)
    if sub == "remote":
        return not posic or posic[0] in ("show", "get-url")
    if sub == "config":
        return (any(a in ("--get", "--get-all", "--get-regexp", "--list", "-l") for a in resto)
                and not any(a in ("--unset", "--unset-all", "--add", "--replace-all", "--edit", "-e") for a in resto))
    if sub == "tag":
        return ("-l" in resto or "--list" in resto or not posic) and not any(a in ("-d", "--delete", "-a", "-s", "-f", "-m", "-F") for a in resto)
    if sub in ("worktree", "stash"):
        return bool(posic) and posic[0] in ("list", "show")
    if sub == "reflog":
        return not posic or posic[0] == "show"
    return False


def _segmento_lectura(seg: list[str]) -> bool:
    resto, i = [], 0
    while i < len(seg):
        t = seg[i]
        if t in REDIRECCIONES or t in (">&", "<", "<<", "<<<") or (t.endswith(">") and set(t) <= set("0123456789&>|")):
            i += 2
            continue
        resto.append(t)
        i += 1
    while resto and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", resto[0]) or resto[0] in ("env", "time", "command")):
        resto.pop(0)
    if not resto:
        return True
    orden, args = re.sub(r"\.exe$", "", os.path.basename(resto[0]).lower()), resto[1:]
    posic = [a for a in args if not a.startswith("-")]
    if orden == "ssh":
        remoto = _comando_remoto_ssh(args)
        if not remoto:
            return True
        try:
            return all(_segmento_lectura(s) for s in _segmentos(remoto))
        except (ComandoIlegible, ValueError):
            return False
    if orden not in ORDENES_LECTURA:
        return False
    if orden == "find":
        return not FIND_ESCRIBE.intersection(args)
    if orden == "sort":
        return not any(a == "-o" or a.startswith("--output") or (a.startswith("-o") and len(a) > 2) for a in args)
    if orden == "uniq":
        return len(posic) <= 1
    if orden == "tree":
        return "-o" not in args
    if orden == "date":
        return not any(a in ("-s", "--set") or a.startswith("--set=") for a in args) and all(p.startswith("+") for p in posic)
    if orden == "hostname":
        return not posic
    if orden == "git":
        return _git_consulta(args)
    return True


def solo_lectura(comando: str) -> bool:
    """True si el comando de shell solo lee (B10): sin sustituciones, sin escrituras detectadas y con órdenes de una lista de consulta
    (git solo en sus formas de consulta). Lo que no se reconoce cuenta como un cambio."""
    if "$(" in comando or "`" in comando:
        return False
    try:
        if any(not o.startswith(GIT_C) and o.strip().lower() not in INOCUOS for o in objetivos_shell(comando, os.getcwd())):
            return False
        return all(_segmento_lectura(s) for s in _segmentos(comando))
    except ComandoIlegible:
        return False


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
