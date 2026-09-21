"""Carga un requisito desde un spec.md al registro SYPNOSE.

Lee la sección R<n> del spec, extrae EARS (blockquote) y comprobación (bash fence),
verifica autoría (Chat: trailer = rol en roles_por_linea), pasa la barrera,
hace backup_registro() ANTES de escribir, y registra evento con VIEJO/NUEVO/sha/autor.
Idempotente: si EARS y comprobación ya coinciden, 0 cambios.
Si el requisito cambia y hay tareas en espera_firma o hecha, aborta (requiere decisión humana).

F0.3: valida comprobacion (rechaza prosa, 'true', pytest sin --cov-fail-under).
       --auditar-deuda: listar requisitos heredados no conformes sin reescribirlos.

    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db T01 R1 specs/T01/spec.md
    python3 cargar_requisito.py --db ~/sypnose-f1/registry.db --auditar-deuda
"""
from __future__ import annotations

import argparse
import re
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
    "gh", "docker", "test", "diff", "sort", "wc", "awk", "sed", "find",
    "cat", "echo", "cd", "ls", "head", "tail",
    "SELECT", "EXPLAIN", "INSERT",
})


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def cargar_yaml_mapas() -> tuple[dict, dict]:
    datos = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    plan_por_linea = datos.get("plan_por_linea", {})
    roles_por_linea = datos.get("roles_por_linea", {})
    return plan_por_linea, roles_por_linea


def validar_comprobacion(comp: str, exigir_cobertura: bool = True) -> tuple[bool, str]:
    """Valida que la comprobacion sea un comando ejecutable.
    Rechaza: vacia, literal 'true', prosa, pytest sin --cov-fail-under.
    Returns (ok, motivo).
    """
    comp = comp.strip()
    if not comp:
        return False, "comprobacion vacia"
    if comp == "true":
        return False, "literal 'true' no demuestra nada"
    tokens = comp.split()
    primer_token = tokens[0]
    if "=" in primer_token and not primer_token.startswith("-"):
        if len(tokens) > 1:
            primer_token = tokens[1]
    pt = primer_token.strip('"\'')
    es_ejecutable = (
        pt in EJECUTABLES_CONOCIDOS
        or "/" in pt
        or "\\" in pt
        or pt.startswith("~")
        or pt.endswith(".py")
        or pt.endswith(".sh")
        or pt.endswith(".mjs")
        or pt.endswith(".js")
        or pt.endswith(".exe")
    )
    if not es_ejecutable:
        return False, f"primer token '{primer_token}' no es ejecutable — parece prosa"
    if exigir_cobertura and "--cov-fail-under" not in comp:
        ejecuta_pytest = (
            pt == "pytest"
            or (pt in ("python", "python3") and "-m pytest" in comp)
            or (pt.endswith(".exe") and "-m pytest" in comp)
        )
        if ejecuta_pytest:
            return False, "pytest sin --cov-fail-under: bateria incompleta para tarea de codigo"
    return True, "ok"


def auditar_deuda(conn) -> list[tuple[str, str, str, str]]:
    """Escanea todos los requisitos y devuelve los no conformes.
    Returns list of (plan_id, ref, comprobacion, motivo).
    """
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
    ap.add_argument("--delegado", action="store_true",
                    help="omite validación de autoría (Chat: trailer) para specs escritos por delegación del lead")
    ap.add_argument("--sin-exigir-cobertura", action="store_true",
                    help="no exigir --cov-fail-under en pytest (para tareas no-codigo)")
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
        if args.delegado:
            print(f"[WARN] autoría: Chat: {spec_autor} ≠ {rol_esperado} — aceptado por --delegado")
        else:
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

        if existente:
            conn.execute(
                "UPDATE requisito SET ears=?, comprobacion=? WHERE plan_id=? AND ref=?",
                (ears, comprobacion, plan_id, ref),
            )
            accion = "requisito_actualizado"
            detalle = (
                f"{ref} · spec_sha: {spec_sha[:12]} · autor: {spec_autor} · {viejo_nuevo}"
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
                f"ears: {ears!r} · comprobacion: {comprobacion!r}"
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
