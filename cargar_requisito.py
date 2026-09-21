"""Carga un requisito desde un spec.md al registro SYPNOSE.

F0.3 v3: validacion robusta con formato canonico.
  Formato: [cd "<ruta>" && ]<comando>[ → <valor esperado>]
  - cd prefix y → sufijo separados antes de validar el comando.
  - Basename sin extension para detectar ejecutables (.exe, paths).
  - Prohibidos fuera de comillas: # ; && || \\n > < -> == $(…) `…` ${…}
  - SQL (SELECT/EXPLAIN): > y < permitidos (operadores de comparacion, no redireccion).
  - Asignaciones de entorno (VAR=val) delante del comando: rechazadas.
  - Primer token: ejecutable conocido o ruta (nunca prosa).
  - Comandos triviales rechazados: echo, true, test, :, bash/sh -c trivial.
  - pytest: --cov-fail-under como token real >= 85; -k (incluso pegado) y :: prohibidos.
  - --sin-exigir-cobertura: solo lineas_de_proceso con --motivo.
  - --auditar-deuda: listar no conformes sin reescribir.

    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db T01 R1 specs/T01/spec.md
    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db --auditar-deuda
"""
from __future__ import annotations

import argparse
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import (
    PLANTILLA_DIR,
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"

EJECUTABLES_CONOCIDOS = frozenset({
    "python3", "python", "pytest", "bash", "sh", "node", "npm", "npx",
    "make", "curl", "wget", "grep", "egrep", "fgrep", "sqlite3", "git",
    "gh", "docker", "diff", "sort", "wc", "awk", "sed", "find",
    "cat", "head", "tail", "ls",
    "SELECT", "EXPLAIN",
})

COMANDOS_TRIVIALES = frozenset({"echo", "true", "test", ":"})
COV_UMBRAL_MINIMO = 85


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def cargar_yaml_mapas() -> tuple[dict, dict]:
    datos = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    plan_por_linea = datos.get("plan_por_linea", {})
    roles_por_linea = datos.get("roles_por_linea", {})
    return plan_por_linea, roles_por_linea


def _fuera_de_comillas(texto: str) -> str:
    out, q = [], None
    for c in texto:
        if q is None:
            if c in ("'", '"'):
                q = c
            else:
                out.append(c)
        elif c == q:
            q = None
    return "".join(out)


def _separar_formato_canonico(comp: str) -> tuple[str, str | None, str | None]:
    """Parse [cd "<ruta>" && ]<comando>[ → <valor esperado>].
    Returns (comando, cd_prefix, expected_value).
    """
    comando = comp
    cd_prefix = None
    expected = None

    m = re.match(r'^cd\s+"[^"]*"\s+&&\s+', comando)
    if m:
        cd_prefix = m.group()
        comando = comando[m.end():]

    q = None
    for i, c in enumerate(comando):
        if q is None:
            if c in ("'", '"'):
                q = c
            elif comando[i:].startswith(" → "):
                expected = comando[i + 3:].strip()
                comando = comando[:i].strip()
                break
        elif c == q:
            q = None

    return comando, cd_prefix, expected


def _detectar_prohibido(comp: str, *, es_sql: bool = False) -> str | None:
    ext = _fuera_de_comillas(comp)
    if "\n" in ext:
        return "salto de linea (multi-comando)"
    for pat, desc in [
        ("#", "comentario (#)"),
        ("&&", "encadenamiento (&&)"),
        ("||", "supresion de error (||)"),
        (";", "separador (;)"),
    ]:
        if pat in ext:
            return desc
    if "→" in ext:
        return "prosa con flecha (→)"
    if "->" in ext:
        return "prosa con flecha (->)"
    if "==" in ext:
        return "prosa con comparacion (==)"
    if not es_sql:
        if ">" in ext:
            return "redireccion (>)"
        if "<" in ext:
            return "redireccion (<)"
    return None


def _detectar_sustitucion(comp: str) -> str | None:
    """Reject $(…), backticks and ${…} outside single quotes."""
    sq = False
    i = 0
    while i < len(comp):
        c = comp[i]
        if sq:
            if c == "'":
                sq = False
        elif c == "'":
            sq = True
        elif c == "`":
            return "sustitucion de comando con backticks"
        elif c == "$" and i + 1 < len(comp):
            nc = comp[i + 1]
            if nc == "(":
                return "sustitucion de comando $()"
            if nc == "{":
                return "expansion de variable ${}"
        i += 1
    return None


def _basename_sin_ext(token: str) -> str:
    base = Path(token).name if ("/" in token or "\\" in token) else token
    if base.lower().endswith((".exe", ".cmd", ".bat")):
        base = base.rsplit(".", 1)[0]
    return base


def _lineas_no_codigo() -> set[str]:
    datos = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    return set(datos.get("lineas_de_proceso", []))


def validar_comprobacion(comp: str, exigir_cobertura: bool = True) -> tuple[bool, str]:
    comp = comp.strip()
    if not comp:
        return False, "comprobacion vacia"
    if comp.lower() in ("true", "false"):
        return False, f"literal '{comp}' no demuestra nada"

    comando, cd_prefix, expected = _separar_formato_canonico(comp)
    if not comando:
        return False, "comprobacion sin comando tras separar formato canonico"

    primer_word = comando.split()[0].upper() if comando.split() else ""
    es_sql = primer_word in ("SELECT", "EXPLAIN")

    prohibido = _detectar_prohibido(comando, es_sql=es_sql)
    if prohibido:
        return False, f"prohibido: {prohibido}"

    sub = _detectar_sustitucion(comando)
    if sub:
        return False, f"prohibido: {sub}"

    try:
        lex = shlex.shlex(comando, posix=True)
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError as e:
        return False, f"no parseable como comando: {e}"

    if not tokens:
        return False, "comprobacion vacia tras parseo"

    primer_token = tokens[0]

    if "=" in primer_token and not primer_token.startswith("-") and not primer_token.startswith("$"):
        return False, f"asignacion de entorno '{primer_token.split('=')[0]}=' delante del comando"

    pt = _basename_sin_ext(primer_token)

    if pt in COMANDOS_TRIVIALES:
        return False, f"comando trivial '{pt}' no demuestra conformidad"

    if pt in ("bash", "sh"):
        try:
            idx_c = next(i for i, t in enumerate(tokens) if t == "-c")
            if idx_c + 1 < len(tokens):
                inner = tokens[idx_c + 1].strip()
                inner_first = inner.split()[0] if inner.split() else inner
                if inner_first in COMANDOS_TRIVIALES or inner in ("exit 0", "exit", "false"):
                    return False, f"{pt} -c con comando trivial: '{inner}'"
        except StopIteration:
            pass

    es_ejecutable = (
        pt in EJECUTABLES_CONOCIDOS
        or "/" in primer_token
        or "\\" in primer_token
        or primer_token.startswith("~")
        or primer_token.startswith(".")
        or primer_token.endswith((".py", ".sh", ".mjs", ".js", ".exe"))
    )
    if not es_ejecutable:
        return False, f"primer token '{primer_token}' no es ejecutable — parece prosa"

    ext = _fuera_de_comillas(comando)
    if pt not in ("SELECT", "EXPLAIN"):
        for i, c in enumerate(ext):
            if c == "(" and (i == 0 or ext[i - 1] != "$"):
                return False, "texto libre con parentesis: la comprobacion debe ser un comando puro"

    pipe_indices = [i for i, t in enumerate(tokens) if t == "|"]
    if pipe_indices:
        last_pipe = pipe_indices[-1]
        if last_pipe + 1 < len(tokens):
            ultimo = _basename_sin_ext(tokens[last_pipe + 1])
            if ultimo in COMANDOS_TRIVIALES:
                return False, f"pipe a comando trivial '{ultimo}'"

    if exigir_cobertura:
        ejecuta_pytest = (
            pt == "pytest"
            or (pt in ("python", "python3") and "pytest" in tokens)
        )
        if ejecuta_pytest:
            cov_value = None
            for i, t in enumerate(tokens):
                if t.startswith("--cov-fail-under="):
                    try:
                        cov_value = int(t.split("=", 1)[1])
                    except ValueError:
                        return False, f"--cov-fail-under valor no numerico: '{t}'"
                    break
                elif t == "--cov-fail-under" and i + 1 < len(tokens):
                    try:
                        cov_value = int(tokens[i + 1])
                    except ValueError:
                        return False, f"--cov-fail-under valor no numerico: '{tokens[i + 1]}'"
                    break
            if cov_value is None:
                return False, "pytest sin --cov-fail-under: bateria incompleta"
            if cov_value < COV_UMBRAL_MINIMO:
                return False, f"--cov-fail-under={cov_value} < {COV_UMBRAL_MINIMO}: umbral insuficiente"

            for t in tokens:
                if t == "-k" or (t.startswith("-k") and not t.startswith("--k")):
                    return False, "-k selecciona tests: la bateria completa debe pasar"
                if "::" in t:
                    return False, "'::' selecciona un solo test: la bateria completa debe pasar"

    return True, "ok"


def auditar_deuda(conn) -> list[tuple[str, str, str, str]]:
    rows = conn.execute(
        "SELECT plan_id, ref, comprobacion FROM requisito ORDER BY plan_id, ref"
    ).fetchall()
    deuda = []
    for plan_id, ref, comp in rows:
        if not comp:
            deuda.append((plan_id, ref, "(NULL)", "comprobacion vacia"))
            continue
        ok, motivo = validar_comprobacion(comp, exigir_cobertura=True)
        if not ok:
            deuda.append((plan_id, ref, comp[:80], motivo))
    return deuda


def obtener_spec_sha(spec_rel: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%H", "--", spec_rel],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"[FALLO] no hay commit para {spec_rel} en el repo plantilla")
    return r.stdout.strip()


def obtener_spec_autor(spec_rel: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%(trailers:key=Chat,valueonly)", "--", spec_rel],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] no se pudo leer trailers de {spec_rel}")
    autor = r.stdout.strip()
    if not autor:
        sys.exit(f"[FALLO] último commit de {spec_rel} no tiene trailer 'Chat:'")
    return autor


def extraer_seccion_r(texto: str, ref: str) -> str:
    patron = re.compile(rf"^## {re.escape(ref)}\b.*$", re.MULTILINE)
    m = patron.search(texto)
    if not m:
        sys.exit(f"[FALLO] sección '## {ref}' no encontrada en el spec")
    inicio = m.end()
    siguiente = re.search(r"^## ", texto[inicio:], re.MULTILINE)
    if siguiente:
        return texto[inicio:inicio + siguiente.start()]
    return texto[inicio:]


def extraer_ears(seccion: str) -> str:
    lineas = seccion.split("\n")
    en_ears = False
    ears_lineas = []
    for linea in lineas:
        if re.match(r"\*\*EARS", linea):
            en_ears = True
            continue
        if en_ears:
            if linea.startswith(">"):
                ears_lineas.append(linea.lstrip("> ").rstrip())
            elif ears_lineas and not linea.strip():
                break
            elif ears_lineas:
                break
    if not ears_lineas:
        sys.exit("[FALLO] bloque EARS (blockquote >) no encontrado en la sección")
    return " ".join(ears_lineas)


def extraer_comprobacion(seccion: str) -> str:
    m = re.search(r"\*\*Comprobación[^*]*\*\*", seccion)
    if not m:
        sys.exit("[FALLO] '**Comprobación ...**' no encontrado en la sección")
    resto = seccion[m.end():]
    fence = re.search(r"```(?:bash)?\s*\n(.*?)```", resto, re.DOTALL)
    if not fence:
        sys.exit("[FALLO] bloque ```bash``` no encontrado tras Comprobación")
    return fence.group(1).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga requisito desde spec.md al registro")
    ap.add_argument("sigla", nargs="?", help="sigla de la línea, ej. T01")
    ap.add_argument("linea", nargs="?", help="referencia del requisito, ej. R1")
    ap.add_argument("spec", nargs="?", help="ruta al spec.md relativa a plantilla/")
    ap.add_argument("--db", required=True, help="ruta a registry.db")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--actor", default=ACTOR)

    ap.add_argument("--sin-exigir-cobertura", action="store_true",
                    help="no exigir --cov-fail-under en pytest (solo lineas_de_proceso)")
    ap.add_argument("--motivo",
                    help="motivo obligatorio cuando se usa --sin-exigir-cobertura")
    ap.add_argument("--auditar-deuda", action="store_true",
                    help="listar requisitos existentes con comprobacion no conforme")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    if args.auditar_deuda:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        deuda = auditar_deuda(conn)
        conn.close()
        if not deuda:
            print("[OK] 0 requisitos no conformes")
            return
        print(f"[DEUDA] {len(deuda)} requisitos no conformes:")
        for plan_id, ref, comp, motivo in deuda:
            print(f"  {plan_id:16} {ref:4} {motivo}")
            print(f"{'':20}     comprobacion: {comp}")
        sys.exit(1)

    if not args.sigla or not args.linea or not args.spec:
        sys.exit("[FALLO] se requiere sigla, linea y spec (usa --auditar-deuda para auditar sin cargar)")

    if args.sin_exigir_cobertura:
        lineas_nc = _lineas_no_codigo()
        if args.sigla not in lineas_nc:
            sys.exit(
                f"[FALLO] --sin-exigir-cobertura solo para lineas_de_proceso "
                f"declaradas en oferta.yaml ({', '.join(sorted(lineas_nc))}); "
                f"{args.sigla} no es una de ellas"
            )
        if not args.motivo:
            sys.exit("[FALLO] --sin-exigir-cobertura requiere --motivo")

    spec_path = PLANTILLA_DIR / args.spec
    if not spec_path.exists():
        sys.exit(f"[FALLO] spec no encontrado: {spec_path}")

    plan_por_linea, roles_por_linea = cargar_yaml_mapas()

    plan_id = None
    for pid, lid in plan_por_linea.items():
        if lid == args.sigla:
            plan_id = pid
            break
    if not plan_id:
        sys.exit(f"[FALLO] sigla {args.sigla} no encontrada en plan_por_linea de oferta.yaml")

    rol_esperado = roles_por_linea.get(args.sigla, {}).get("rol")
    if not rol_esperado:
        sys.exit(f"[FALLO] sigla {args.sigla} no tiene rol en roles_por_linea de oferta.yaml")

    ref = args.linea
    spec_rel = args.spec

    spec_sha = obtener_spec_sha(spec_rel)
    spec_autor = obtener_spec_autor(spec_rel)

    print(f"[spec] {spec_rel} (sha {spec_sha[:12]})")
    print(f"[autor] Chat: {spec_autor}")
    print(f"[rol esperado] {rol_esperado}")

    if spec_autor != rol_esperado:
        sys.exit(
            f"[FALLO] autoría: último commit de {spec_rel} es Chat: {spec_autor}, "
            f"pero roles_por_linea exige {rol_esperado} para {args.sigla}"
        )
    else:
        print("[autoría] OK")

    texto = spec_path.read_text(encoding="utf-8")
    seccion = extraer_seccion_r(texto, ref)
    ears = extraer_ears(seccion)
    comprobacion = extraer_comprobacion(seccion)

    print(f"[plan_id] {plan_id}")
    print(f"[ref] {ref}")
    print(f"[ears] {ears[:80]}{'...' if len(ears) > 80 else ''}")
    print(f"[comprobacion] {comprobacion}")

    ok_comp, motivo_comp = validar_comprobacion(
        comprobacion, exigir_cobertura=not args.sin_exigir_cobertura
    )
    if not ok_comp:
        sys.exit(f"[FALLO] comprobacion rechazada: {motivo_comp}\n  comprobacion: {comprobacion}")
    print("[validacion] OK")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    existente = conn.execute(
        "SELECT ears, comprobacion FROM requisito WHERE plan_id=? AND ref=?",
        (plan_id, ref),
    ).fetchone()

    tareas_afectadas = []
    if existente:
        ears_actual, comp_actual = existente
        if ears_actual == ears and comp_actual == comprobacion:
            print(f"[idempotente] {plan_id} {ref} ya tiene EARS y comprobación idénticos. 0 cambios.")
            conn.close()
            return

        tareas_afectadas = conn.execute(
            "SELECT id, progreso, verificada_por FROM tarea "
            "WHERE plan_id=? AND req_ref=? AND progreso IN ('espera_firma','hecha')",
            (plan_id, ref),
        ).fetchall()

    if args.dry_run:
        print("[dry-run] habría escrito:")
        if existente:
            print(f"  UPDATE requisito WHERE plan_id={plan_id} AND ref={ref}")
            print(f"  VIEJO ears: {ears_actual[:60]}...")
            print(f"  NUEVO ears: {ears[:60]}...")
            if tareas_afectadas:
                for tid, prog, ver in tareas_afectadas:
                    print(f"  CASCADE tarea {tid} ({prog}) → devuelta")
        else:
            print(f"  INSERT INTO requisito ({plan_id}, {ref}, ...)")
        conn.close()
        return

    b = backup_registro(conn, db_path, "requisito")

    conn.execute("BEGIN IMMEDIATE")
    try:
        viejo_nuevo = (
            f"VIEJO ears: {ears_actual!r} · VIEJO comprobacion: {comp_actual!r} · "
            f"NUEVO ears: {ears!r} · NUEVO comprobacion: {comprobacion!r}"
        ) if existente else None

        sin_cob_detalle = ""
        if args.sin_exigir_cobertura:
            sin_cob_detalle = f" · sin_exigir_cobertura=1, motivo={args.motivo!r}"

        if existente:
            conn.execute(
                "UPDATE requisito SET ears=?, comprobacion=? WHERE plan_id=? AND ref=?",
                (ears, comprobacion, plan_id, ref),
            )
            accion = "requisito_actualizado"
            detalle = (
                f"{ref} · spec_sha: {spec_sha[:12]} · autor: {spec_autor} · {viejo_nuevo}"
                f"{sin_cob_detalle}"
            )
            print(f"[update] {plan_id} {ref}")

            for tid, prog, ver in tareas_afectadas:
                conn.execute(
                    "UPDATE tarea SET progreso='devuelta', verificada_por=NULL WHERE id=?",
                    (tid,),
                )
                nota_firma = ""
                if prog == "hecha":
                    nota_firma = " (firma humana invalidada: el texto verificado ya no es el vigente)"
                conn.execute(
                    "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                    (
                        ahora(),
                        args.actor,
                        "requisito_cambiado",
                        plan_id,
                        f"tarea {tid} ({prog}→devuelta){nota_firma} · spec_sha: {spec_sha[:12]} · autor: {spec_autor} · {viejo_nuevo}",
                    ),
                )
                print(f"[cascade] tarea {tid} ({prog} → devuelta){nota_firma}")
        else:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, ref, ears, comprobacion),
            )
            accion = "requisito_cargado"
            detalle = (
                f"{ref} · spec_sha: {spec_sha[:12]} · autor: {spec_autor} · "
                f"ears: {ears!r} · comprobacion: {comprobacion!r}{sin_cob_detalle}"
            )
            print(f"[insert] {plan_id} {ref}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ahora(), args.actor, accion, plan_id, detalle),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[OK] {plan_id} {ref} cargado desde {spec_rel} (sha {spec_sha[:12]}, autor {spec_autor})")


if __name__ == "__main__":
    main()
