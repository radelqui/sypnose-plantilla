"""TRASPASO-4 A2: crea nodo solución, relaciones cubre, plan_objetivo, afirmaciones para la vista.

Mapeos canónicos se leen de oferta.yaml (plan_por_linea, cubre_por_evidencia).
Nunca heurísticas; todo explícito y bajo barrera hash.

    python3 enlazar_solucion.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import PLANTILLA_DIR, actor07_valido, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/enlazar_solucion.py"
COLECCION = "plantilla-microservicio-ia"
NODO_PLANTILLA = "plantilla:microservicio-ia"
SOL_ID = "sol:coforge:rag-banking-agent"
SOL_NOMBRE = "rag-banking-agent (Coforge/Santander)"
PROY_ID = "proy:vmi3211028:rag-banking-agent"
OFERTA_TITULO = "Python Developer + IA · Coforge / Santander"
REPO_URL = "https://github.com/radelqui/rag-banking-agent"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def insertar_si_nuevo(conn, sql, args, etiqueta, altas, existian):
    if conn.execute(sql, args).rowcount == 1:
        altas.append(etiqueta)
        return True
    existian.append(etiqueta)
    return False


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


REPO_RAG = Path(__file__).resolve().parent.parent / "rag-banking-agent"
REPO_SLUG = "vmi3211028:rag-banking-agent"
AMBITO_PROY = "vmi3211028"


def nodo_id_para_ruta(ruta: str) -> str:
    """Converts a repo-relative path to a node ID. ** suffix → dir:, else mod:."""
    if ruta.endswith("/**"):
        return f"dir:{REPO_SLUG}:{ruta[:-3]}"
    return f"mod:{REPO_SLUG}:{ruta}"


def _dir_id(path: str) -> str:
    return f"dir:{REPO_SLUG}:{path}"


def asegurar_contiene(conn, nid: str, actor: str, altas: list, existian: list):
    """Ensures a contiene chain from PROY_ID down to nid, creating intermediate dirs as needed."""
    parts = nid.split(":", 3)
    if len(parts) < 4:
        return
    ruta = parts[3]
    segs = ruta.split("/")
    if len(segs) <= 1:
        padre_id = PROY_ID
    else:
        padre_path = "/".join(segs[:-1])
        padre_id = _dir_id(padre_path)
        if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (padre_id,)).fetchone():
            conn.execute(
                "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                "VALUES (?, 'carpeta', ?, ?, 'activo', ?, ?)",
                (padre_id, padre_path, AMBITO_PROY, ahora(), FUENTE),
            )
            evento(conn, actor, "alta_nodo", f"carpeta intermedia {padre_id}", nodo_id=padre_id)
            altas.append(f"nodo {padre_id}")
        asegurar_contiene(conn, padre_id, actor, altas, existian)
    rc = conn.execute(
        "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
        "VALUES (?, ?, 'contiene', 'observado', ?, ?)",
        (padre_id, nid, FUENTE, ahora()),
    ).rowcount
    if rc == 1:
        altas.append(f"contiene {padre_id} → {nid}")
    else:
        existian.append(f"contiene {padre_id} → {nid}")


def ruta_existe_en_repo(ruta: str, sha: str) -> bool:
    """Checks whether a file or directory exists at a pinned sha in the rag-banking-agent repo."""
    if ruta.endswith("/**"):
        dir_path = ruta[:-3]
        r = subprocess.run(
            ["git", "-C", str(REPO_RAG), "ls-tree", "--name-only", sha, dir_path + "/"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    r = subprocess.run(
        ["git", "-C", str(REPO_RAG), "cat-file", "-e", f"{sha}:{ruta}"],
        capture_output=True, text=True, timeout=10,
    )
    return r.returncode == 0

NODO_A_RUTA = {
    "dir:": lambda nid: nid.split(":", 3)[-1] if nid.count(":") >= 3 else None,
    "mod:": lambda nid: nid.split(":", 3)[-1] if nid.count(":") >= 3 else None,
}

AGENTE_A_RAMA = {
    "IA:00-lead": "main",
    "IA:01-git-cicd": "chat/01-git-cicd",
    "IA:02-backend-api": "chat/02-backend-api",
    "IA:03-datos-rag": "chat/03-datos-rag",
    "IA:04-agentes": "chat/04-agentes",
    "IA:05-arquitecto-sypnose": "chat/05-arquitecto-sypnose",
    "IA:06-frontend": "chat/06-frontend",
}


def nodo_id_a_ruta(nodo_id: str):
    for prefijo, fn in NODO_A_RUTA.items():
        if nodo_id.startswith(prefijo):
            return fn(nodo_id)
    return None


def agente_a_rama(agente: str) -> str:
    for prefijo, rama in AGENTE_A_RAMA.items():
        if agente.startswith(prefijo):
            return rama
    return "main"


def obtener_commit_fichero(ruta: str, rama: str) -> str | None:
    if not REPO_RAG.exists():
        return None
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_RAG), "log", "-1", "--format=%H", rama, "--", ruta],
            capture_output=True, text=True, timeout=10,
        )
        sha = r.stdout.strip()
        return sha if sha else None
    except Exception:
        return None


def afirmar(conn, actor, nodo_id, campo, valor, certeza="observado"):
    ya = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1", (nodo_id, campo)
    ).fetchall()
    if any(v == valor for _, v in ya):
        return False
    for fid, _ in ya:
        conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (fid,))
    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
        (nodo_id, campo, valor, certeza, FUENTE, actor, ahora()),
    )
    evento(conn, actor, "afirmacion_creada", f"{campo} = {valor[:120]}", nodo_id=nodo_id)
    return True


CERTEZAS_VALIDAS = {"observado", "inferido", "propuesto"}


def cargar_oferta_yaml():
    if not OFERTA_YAML.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_YAML}")
    with open(OFERTA_YAML, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    plan_por_linea = doc.get("plan_por_linea")
    if not plan_por_linea:
        sys.exit("[FALLO] oferta.yaml no contiene plan_por_linea")
    cubre_raw = doc.get("cubre_por_evidencia")
    if not cubre_raw:
        sys.exit("[FALLO] oferta.yaml no contiene cubre_por_evidencia")
    if isinstance(cubre_raw, list):
        cubre_map = {lid: "observado" for lid in cubre_raw}
    elif isinstance(cubre_raw, dict):
        cubre_map = cubre_raw
    else:
        sys.exit("[FALLO] cubre_por_evidencia debe ser lista o mapa línea→certeza")
    for lid, certeza in cubre_map.items():
        if certeza not in CERTEZAS_VALIDAS:
            sys.exit(f"[FALLO] certeza inválida '{certeza}' para línea {lid}")
    archivos = doc.get("archivos_por_linea", {})
    lineas_proceso = set(doc.get("lineas_de_proceso", []))
    return plan_por_linea, cubre_map, archivos, lineas_proceso


# ── Certeza calculation from sources ──

RE_FILE_SHA = re.compile(r"^(.+)@([0-9a-f]{6,40})$")
RE_SECTION = re.compile(r"^(.+)#(.+)@([0-9a-f]{6,40})$")
RE_GH_RUN = re.compile(r"^gh:run:(\d+)$")
RE_VERIFICADOR = re.compile(r"^07-verificador/.+")
RE_COMPROBACION = re.compile(r"^comprobacion:.+@([0-9a-f]{6,40})$")
RE_PLAN_REF = re.compile(r"^plan:(.+)$")
RE_GIT_REPO = re.compile(r"^git:(.+)$")
RE_EVENTO = re.compile(r"^evento:(\d+)$")
RE_GIT_COMMIT = re.compile(r"^git:commit:([0-9a-f]{6,40})$")
GH_REPO = "radelqui/rag-banking-agent"
PROYECTO_DIR = PLANTILLA_DIR.parent


def _git_object_exists(repo: Path, ref: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", ref],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _git_heading_exists(repo: Path, sha: str, path: str, section: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "show", f"{sha}:{path}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return False
        pattern = re.compile(r"^#+\s*" + re.escape(section) + r"\s*$", re.IGNORECASE | re.MULTILINE)
        return bool(pattern.search(r.stdout))
    except Exception:
        return False


def _gh_run_success(run_id: str) -> bool:
    """A run is success if conclusion=success, OR if status=waiting with
    jobs 'test' and 'build-and-push' concluded success and job 'deploy'
    in waiting (human approval gate). Any other state is not success."""
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{GH_REPO}/actions/runs/{run_id}",
             "--jq", '{conclusion: (.conclusion // "none"), status: (.status // "none")}'],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return False
        import json as _json
        data = _json.loads(r.stdout.strip())
        conclusion = data.get("conclusion", "")
        status = data.get("status", "")
        if conclusion == "success":
            return True
        if status != "waiting":
            return False
        # status=waiting: verify individual jobs
        rj = subprocess.run(
            ["gh", "api", f"repos/{GH_REPO}/actions/runs/{run_id}/jobs",
             "--jq", '[.jobs[] | {name: .name, conclusion: (.conclusion // "none"), status: .status}]'],
            capture_output=True, text=True, timeout=30,
        )
        if rj.returncode != 0:
            return False
        jobs = _json.loads(rj.stdout.strip())
        job_map = {j["name"]: j for j in jobs}
        test_ok = job_map.get("test", {}).get("conclusion") == "success"
        build_ok = job_map.get("build-and-push", {}).get("conclusion") == "success"
        deploy_waiting = job_map.get("deploy", {}).get("status") == "waiting"
        if test_ok and build_ok and deploy_waiting:
            return True
        return False
    except Exception:
        return False


def validar_fuente(fuente: str, conn=None, plan_id: str | None = None) -> tuple[bool, str]:
    """Returns (valid, reason). Unknown formats are invalid."""
    # plan:PLAN-ID → plan must exist in DB
    m = RE_PLAN_REF.match(fuente)
    if m:
        plan_id = m.group(1)
        if conn and conn.execute("SELECT 1 FROM plan WHERE id=?", (plan_id,)).fetchone():
            return True, "ok"
        return False, f"plan {plan_id} not found in DB"

    # 07-verificador/* → valid only if evento has matching row from a ratified 07 actor
    if RE_VERIFICADOR.match(fuente):
        if ".." in fuente:
            return False, "path traversal rejected"
        if not conn or not plan_id:
            return False, "needs DB connection and plan_id"
        rows = conn.execute(
            "SELECT actor FROM evento WHERE accion='evidencia_07' AND plan_id=? AND detalle=?",
            (plan_id, fuente),
        ).fetchall()
        found_valid = False
        unknown_actors = []
        for (actor,) in rows:
            if actor.startswith("IA:07-verificador:") and actor07_valido(actor, conn):
                found_valid = True
            elif "07-verificador" in actor:
                unknown_actors.append(actor)
        if found_valid:
            for ua in unknown_actors:
                print(f"  [WARN] unratified 07-verificador actor in events: {ua}")
            return True, "ok"
        if unknown_actors:
            return False, f"unratified 07-verificador actor(s): {', '.join(unknown_actors)}"
        return False, "no evidencia_07 event from a ratified actor 07"

    # evento:<id> → only for lineas_de_proceso; must be accion='verificado',
    # detalle contains CUMPLE (not NO CUMPLE), same plan, actor 07 ratified
    m = RE_EVENTO.match(fuente)
    if m:
        evento_id = int(m.group(1))
        if not conn:
            return False, "needs DB connection"
        row = conn.execute(
            "SELECT actor, accion, plan_id, detalle FROM evento WHERE rowid=?", (evento_id,)
        ).fetchone()
        if not row:
            return False, f"evento {evento_id} not found"
        actor, accion, ev_plan, detalle = row
        if accion != "verificado":
            return False, f"evento {evento_id} accion={accion}, expected verificado"
        if not detalle or "CUMPLE" not in detalle or "NO CUMPLE" in detalle:
            return False, f"evento {evento_id} detalle not CUMPLE"
        if plan_id and ev_plan and ev_plan != plan_id:
            return False, f"evento {evento_id} plan={ev_plan}, expected {plan_id}"
        if actor.startswith("IA:07-verificador:") and actor07_valido(actor, conn):
            return True, "ok"
        return False, f"evento {evento_id} actor {actor} not ratified 07"

    # git:commit:<sha> → commit must exist in rag-banking-agent
    m = RE_GIT_COMMIT.match(fuente)
    if m:
        sha = m.group(1)
        if _git_object_exists(REPO_RAG, sha):
            return True, "ok"
        return False, f"commit {sha} not found in rag-banking-agent"

    # git:<repo> → repo directory must exist and be a git repo
    m = RE_GIT_REPO.match(fuente)
    if m:
        repo_name = m.group(1)
        repo_path = PROYECTO_DIR / repo_name
        if repo_path.exists() and (repo_path / ".git").exists():
            return True, "ok"
        return False, f"repo {repo_name} not found at {repo_path}"

    # comprobacion:agent/wt@sha → commit must exist
    m = RE_COMPROBACION.match(fuente)
    if m:
        sha = m.group(1)
        if _git_object_exists(REPO_RAG, sha):
            return True, "ok"
        return False, f"commit {sha} not found"

    # file#section@sha → file and heading must exist
    m = RE_SECTION.match(fuente)
    if m:
        path, section, sha = m.groups()
        if not _git_object_exists(REPO_RAG, f"{sha}:{path}"):
            return False, f"file {path} not found at {sha}"
        if not _git_heading_exists(REPO_RAG, sha, path, section):
            return False, f"heading #{section} not found in {path}@{sha}"
        return True, "ok"

    # file@sha → file must exist at that commit
    m = RE_FILE_SHA.match(fuente)
    if m:
        path, sha = m.groups()
        if _git_object_exists(REPO_RAG, f"{sha}:{path}"):
            return True, "ok"
        return False, f"file {path} not found at {sha}"

    # gh:run:ID → conclusion must be success
    m = RE_GH_RUN.match(fuente)
    if m:
        run_id = m.group(1)
        if _gh_run_success(run_id):
            return True, "ok"
        return False, f"gh run {run_id} not success"

    # Unknown format → invalid
    return False, f"unrecognized source format"


def calcular_certeza(conn, plan_id: str) -> tuple[str, list[str]]:
    """Calculate certeza from evidence sources. Returns (certeza, reasons)."""
    filas = conn.execute(
        "SELECT rowid, fuente, dice FROM evidencia WHERE plan_id=? "
        "AND fuente NOT LIKE 'bloqueo:%' AND fuente NOT LIKE 'INVALIDA:%' "
        "AND fuente NOT LIKE 'entrega:%'",
        (plan_id,),
    ).fetchall()

    invalidas_fuente = set()
    invalidas_rowid = set()
    for row in conn.execute(
        "SELECT rowid, fuente FROM evidencia WHERE plan_id=? AND fuente LIKE 'INVALIDA:%'",
        (plan_id,),
    ).fetchall():
        inv_rid, inv_fuente = row
        target = inv_fuente.replace("INVALIDA:", "", 1)
        autorizado = conn.execute(
            "SELECT actor FROM evento "
            "WHERE accion='evidencia_invalidada' AND plan_id=? AND detalle=?",
            (plan_id, inv_fuente),
        ).fetchall()
        tiene_autorizacion = False
        for (actor_inv,) in autorizado:
            if actor_inv.startswith("H:"):
                if conn.execute(
                    "SELECT 1 FROM actor WHERE id=? AND clase='humano'",
                    (actor_inv,),
                ).fetchone():
                    tiene_autorizacion = True
                    break
            elif actor_inv.startswith("IA:07-verificador:") and actor07_valido(actor_inv, conn):
                tiene_autorizacion = True
                break
        if not tiene_autorizacion:
            sys.exit(
                f"[ERROR DATOS] {plan_id}: evidencia rowid={inv_rid} fuente={inv_fuente} "
                "sin evento evidencia_invalidada autorizado — aborto (marcador no autorizado)"
            )
        m_rowid = re.match(r"^rowid:(\d+)$", target)
        if m_rowid:
            invalidas_rowid.add(int(m_rowid.group(1)))
        else:
            invalidas_fuente.add(target)
    filas = [(rid, f, d) for rid, f, d in filas
             if f not in invalidas_fuente and rid not in invalidas_rowid]

    if not filas:
        return "propuesto", ["0 filas de evidencia real"]

    razones = []
    alguna_falla = False
    for _rid, fuente, dice in filas:
        if dice.upper().startswith("PARCIAL") or "estado: parcial" in dice.lower():
            alguna_falla = True
            razones.append(f"dice PARCIAL explícito: {fuente}")
        valida, motivo = validar_fuente(fuente, conn, plan_id)
        if not valida:
            alguna_falla = True
            razones.append(f"fuente inválida: {fuente} ({motivo})")

    if alguna_falla:
        return "inferido", razones
    return "observado", ["todas las fuentes válidas"]


CERTEZA_ORDEN = {"propuesto": 0, "inferido": 1, "observado": 2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--actor", default=ACTOR)
    ap.add_argument("--rag-sha", help="pinned sha for rag-banking-agent (default: HEAD)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-certeza", action="store_true", help="skip certeza validation (use when pre-existing mismatch blocks unrelated work)")
    args = ap.parse_args()

    verificar_repo_limpio()

    if not REPO_RAG.exists() or not (REPO_RAG / ".git").exists():
        sys.exit(f"[FALLO] repo rag-banking-agent no encontrado en {REPO_RAG}; "
                 "necesario para validar fuentes file@sha")

    if args.rag_sha:
        rag_sha = args.rag_sha
    else:
        r = subprocess.run(
            ["git", "-C", str(REPO_RAG), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0 or not r.stdout.strip():
            sys.exit("[FALLO] no se pudo resolver HEAD de rag-banking-agent")
        rag_sha = r.stdout.strip()
    r = subprocess.run(
        ["git", "-C", str(REPO_RAG), "rev-parse", "--verify", f"{rag_sha}^{{commit}}"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit(f"[FALLO] rag-sha {rag_sha} no es un commit válido en rag-banking-agent")
    rag_sha = r.stdout.strip()
    print(f"[rag-sha] {rag_sha[:12]}")

    plan_por_linea, cubre_map, archivos_por_linea, lineas_proceso = cargar_oferta_yaml()
    cubre_set = set(cubre_map.keys())
    print(f"[oferta.yaml] plan_por_linea: {len(plan_por_linea)} entradas, cubre_por_evidencia: {len(cubre_set)} líneas")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] actor {args.actor} no existe")

    verificar_canonicos_registrados(conn)

    # Certeza calculada desde fuentes (lead decision X1v5)
    linea_a_plan = {v: k for k, v in plan_por_linea.items()}
    certeza_calculada = {}
    print("[certeza] calculando desde fuentes de evidencia...")
    for lid in sorted(cubre_set):
        plan_id = linea_a_plan.get(lid)
        if not plan_id:
            sys.exit(f"[FALLO] {lid}: sin plan en plan_por_linea")
        calc, razones = calcular_certeza(conn, plan_id)
        certeza_calculada[lid] = calc
        yaml_decl = cubre_map[lid]
        marca = "OK" if yaml_decl == calc else "!!"
        print(f"  {lid} ({plan_id}): calculado={calc}, yaml={yaml_decl} [{marca}]")
        for r in razones:
            if r != "todas las fuentes válidas":
                print(f"      → {r}")

    # Regla lead: yaml declara más que calculado → abortar
    errores = []
    for lid in sorted(cubre_set):
        yaml_decl = cubre_map[lid]
        calc = certeza_calculada[lid]
        if CERTEZA_ORDEN.get(yaml_decl, 0) > CERTEZA_ORDEN.get(calc, 0):
            errores.append(f"{lid}: yaml={yaml_decl} > calculado={calc}")
    if errores:
        for e in errores:
            print(f"  [FALLO] {e}")
        if not args.skip_certeza:
            sys.exit(f"[FALLO] {len(errores)} líneas con yaml declarando más certeza que la calculada")
        print(f"  [WARN] --skip-certeza: {len(errores)} errores de certeza ignorados, continuando")

    # Yaml es techo: calculado > yaml → WARN + mantener yaml (subir requiere humano tocando yaml)
    for lid in sorted(cubre_set):
        yaml_decl = cubre_map[lid]
        calc = certeza_calculada[lid]
        if CERTEZA_ORDEN.get(yaml_decl, 0) < CERTEZA_ORDEN.get(calc, 0):
            print(f"  [WARN] {lid}: calculado={calc} > yaml={yaml_decl}, se mantiene yaml (techo)")

    lineas = conn.execute(
        "SELECT id FROM nodo WHERE tipo='linea_oferta' ORDER BY id"
    ).fetchall()
    if not lineas:
        sys.exit("[FALLO] no hay nodos linea_oferta; ejecuta cargar_raices.py primero")
    print(f"[registro] {len(lineas)} linea_oferta encontradas")

    if not args.dry_run:
        b = backup_registro(conn, db_path, "enlaces")

    altas = []
    existian = []
    avisos = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        insertar_si_nuevo(
            conn,
            "INSERT OR IGNORE INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
            "VALUES (?, 'solucion', ?, 'coforge-santander', 'activo', ?, 'humano')",
            (SOL_ID, SOL_NOMBRE, ahora()),
            f"nodo {SOL_ID}", altas, existian,
        )
        if SOL_ID in [a.split()[-1] for a in altas if "nodo" in a]:
            evento(conn, args.actor, "alta_nodo", f"nodo solución {SOL_ID}", nodo_id=SOL_ID)

        # cubre: solo líneas en cubre_por_evidencia con certeza del mapa
        for (linea_id,) in lineas:
            sufijo = linea_id.replace("linea:coforge:", "")
            if sufijo not in cubre_set:
                continue
            certeza_yaml = cubre_map[sufijo]
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', ?, ?, ?)",
                (SOL_ID, linea_id, certeza_yaml, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                evento(conn, args.actor, "relacion_cubre",
                       f"{SOL_ID} cubre {linea_id} (certeza={certeza_yaml})", nodo_id=SOL_ID)
                altas.append(f"cubre {SOL_ID} → {linea_id} [{certeza_yaml}]")
            else:
                existian.append(f"cubre {SOL_ID} → {linea_id}")

        # reconciliar: actualizar certeza de cubre existentes según mapa
        cubre_en_bd = conn.execute(
            "SELECT destino, certeza FROM relacion WHERE origen=? AND tipo='cubre'",
            (SOL_ID,),
        ).fetchall()
        for destino, certeza_bd in cubre_en_bd:
            sufijo = destino.replace("linea:coforge:", "")
            if sufijo not in cubre_set:
                if certeza_bd != "propuesto":
                    conn.execute(
                        "UPDATE relacion SET certeza='propuesto' WHERE origen=? AND destino=? AND tipo='cubre'",
                        (SOL_ID, destino),
                    )
                    evento(conn, args.actor, "cubre_reconciliado",
                           f"cubre {SOL_ID}→{destino}: {certeza_bd} → propuesto (no en cubre_por_evidencia)",
                           nodo_id=SOL_ID)
                    altas.append(f"reconciliado cubre→{destino}: {certeza_bd} → propuesto")
            else:
                certeza_yaml = cubre_map[sufijo]
                if certeza_bd != certeza_yaml:
                    conn.execute(
                        "UPDATE relacion SET certeza=? WHERE origen=? AND destino=? AND tipo='cubre'",
                        (certeza_yaml, SOL_ID, destino),
                    )
                    evento(conn, args.actor, "certeza_actualizada",
                           f"cubre {SOL_ID}→{destino}: {certeza_bd} → {certeza_yaml}",
                           nodo_id=SOL_ID)
                    altas.append(f"certeza cubre→{destino}: {certeza_bd} → {certeza_yaml}")

        # cubre módulo/carpeta → línea (archivos_por_linea de oferta.yaml)
        cubre_arch_count = 0
        esperadas_mod = set()
        for lid, rutas in archivos_por_linea.items():
            linea_id = f"linea:coforge:{lid}"
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (linea_id,)).fetchone():
                continue
            sol_certeza = cubre_map.get(lid, "propuesto")
            for ruta in rutas:
                nid = nodo_id_para_ruta(ruta)
                esperadas_mod.add((nid, linea_id))
                existe = ruta_existe_en_repo(ruta, rag_sha)
                file_certeza = "observado" if existe else "propuesto"
                certeza = file_certeza if CERTEZA_ORDEN.get(file_certeza, 0) <= CERTEZA_ORDEN.get(sol_certeza, 0) else sol_certeza
                if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nid,)).fetchone():
                    tipo = "carpeta" if ruta.endswith("/**") else "modulo"
                    nombre = ruta.rstrip("/*")
                    conn.execute(
                        "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                        "VALUES (?, ?, ?, ?, 'activo', ?, ?)",
                        (nid, tipo, nombre, AMBITO_PROY, ahora(), FUENTE),
                    )
                    evento(conn, args.actor, "alta_nodo", f"nodo {tipo} {nid}", nodo_id=nid)
                    altas.append(f"nodo {nid}")
                asegurar_contiene(conn, nid, args.actor, altas, existian)
                existente = conn.execute(
                    "SELECT certeza FROM relacion WHERE origen=? AND destino=? AND tipo='cubre'",
                    (nid, linea_id),
                ).fetchone()
                if existente:
                    if existente[0] != certeza:
                        conn.execute(
                            "UPDATE relacion SET certeza=? WHERE origen=? AND destino=? AND tipo='cubre'",
                            (certeza, nid, linea_id),
                        )
                        evento(conn, args.actor, "cubre_reconciliado",
                               f"cubre {nid}→{linea_id}: {existente[0]} → {certeza}",
                               nodo_id=nid)
                        altas.append(f"reconciliado cubre {nid}→{linea_id}: {existente[0]} → {certeza}")
                    else:
                        existian.append(f"cubre {nid} → {linea_id}")
                else:
                    conn.execute(
                        "INSERT INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                        "VALUES (?, ?, 'cubre', ?, ?, ?)",
                        (nid, linea_id, certeza, FUENTE, ahora()),
                    )
                    evento(conn, args.actor, "relacion_cubre", f"{nid} cubre {linea_id} [{certeza}]", nodo_id=nid)
                    altas.append(f"cubre {nid} → {linea_id} [{certeza}]")
                    cubre_arch_count += 1

        # reconciliar ambito: nodos creados con ambito erróneo → ambito del proyecto
        ambito_fijos = conn.execute(
            "SELECT id FROM nodo WHERE (tipo='modulo' OR tipo='carpeta') "
            "AND id LIKE ? AND ambito='coforge-santander' AND vitalidad='activo'",
            (f"%{REPO_SLUG}:%",),
        ).fetchall()
        for (nid_fix,) in ambito_fijos:
            conn.execute("UPDATE nodo SET ambito=? WHERE id=?", (AMBITO_PROY, nid_fix))
            altas.append(f"ambito {nid_fix}: coforge-santander → {AMBITO_PROY}")

        # reconciliar módulo→línea: relaciones fuera del yaml → propuesto
        mod_en_bd = conn.execute(
            "SELECT origen, destino, certeza FROM relacion "
            "WHERE tipo='cubre' AND destino LIKE 'linea:coforge:%' "
            "AND origen != ? AND (origen LIKE 'mod:%' OR origen LIKE 'dir:%') "
            "AND fuente = ?",
            (SOL_ID, FUENTE),
        ).fetchall()
        for origen, destino, certeza_bd in mod_en_bd:
            if (origen, destino) not in esperadas_mod and certeza_bd != "propuesto":
                conn.execute(
                    "UPDATE relacion SET certeza='propuesto' WHERE origen=? AND destino=? AND tipo='cubre'",
                    (origen, destino),
                )
                evento(conn, args.actor, "cubre_reconciliado",
                       f"cubre {origen}→{destino}: {certeza_bd} → propuesto (fuera de archivos_por_linea)",
                       nodo_id=origen)
                altas.append(f"reconciliado cubre {origen}→{destino}: {certeza_bd} → propuesto")

        if cubre_arch_count:
            print(f"  [archivos_por_linea] {cubre_arch_count} relaciones cubre módulo→línea creadas")

        # sol → fichero (contiene): cada fichero de archivos_por_linea pertenece a la solución
        contiene_sol_count = 0
        for lid, rutas in archivos_por_linea.items():
            for ruta in rutas:
                nid = nodo_id_para_ruta(ruta)
                if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nid,)).fetchone():
                    continue
                rc = conn.execute(
                    "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                    "VALUES (?, ?, 'contiene', 'observado', ?, ?)",
                    (SOL_ID, nid, FUENTE, ahora()),
                ).rowcount
                if rc == 1:
                    altas.append(f"contiene {SOL_ID} → {nid}")
                    contiene_sol_count += 1
                else:
                    existian.append(f"contiene {SOL_ID} → {nid}")
        if contiene_sol_count:
            evento(conn, args.actor, "sol_contiene_ficheros",
                   f"{contiene_sol_count} relaciones contiene sol→fichero creadas", nodo_id=SOL_ID)
            print(f"  [sol→fichero] {contiene_sol_count} relaciones contiene creadas")

        # T01 API nodes (pre-existing from graphify, not file-based)
        api_nodos_t01 = [
            "api:vmi3211028:rag-banking-agent:POST:/consultar",
            "api:vmi3211028:rag-banking-agent:GET:/health/live",
            "api:vmi3211028:rag-banking-agent:GET:/health/ready",
        ]
        linea_t01 = "linea:coforge:T01"
        for mod in api_nodos_t01:
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (mod,)).fetchone():
                continue
            rc = conn.execute(
                "INSERT OR IGNORE INTO relacion (origen, destino, tipo, certeza, fuente, visto_en) "
                "VALUES (?, ?, 'cubre', 'observado', ?, ?)",
                (mod, linea_t01, FUENTE, ahora()),
            ).rowcount
            if rc == 1:
                evento(conn, args.actor, "relacion_cubre", f"{mod} cubre {linea_t01}", nodo_id=mod)
                altas.append(f"cubre {mod} → {linea_t01}")
            else:
                existian.append(f"cubre {mod} → {linea_t01}")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:puerto", "8000"):
            altas.append("afirmacion tecnico:puerto=8000")
        else:
            existian.append("afirmacion tecnico:puerto=8000")

        rutas = "GET /health/live, GET /health/ready, POST /api/v1/consultar"
        if afirmar(conn, args.actor, SOL_ID, "tecnico:rutas", rutas):
            altas.append(f"afirmacion tecnico:rutas={rutas}")
        else:
            existian.append(f"afirmacion tecnico:rutas")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:framework", "FastAPI + LlamaIndex + pgvector"):
            altas.append("afirmacion tecnico:framework")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:repo_url", REPO_URL):
            altas.append(f"afirmacion tecnico:repo_url={REPO_URL}")
        else:
            existian.append("afirmacion tecnico:repo_url")

        if afirmar(conn, args.actor, SOL_ID, "tecnico:rag_sha", rag_sha):
            altas.append(f"afirmacion tecnico:rag_sha={rag_sha[:12]}")
        else:
            existian.append("afirmacion tecnico:rag_sha")

        if afirmar(conn, args.actor, NODO_PLANTILLA, "oferta_titulo", OFERTA_TITULO):
            altas.append(f"afirmacion oferta_titulo en {NODO_PLANTILLA}")
        else:
            existian.append(f"afirmacion oferta_titulo en {NODO_PLANTILLA}")

        if afirmar(conn, args.actor, SOL_ID, "oferta_titulo", OFERTA_TITULO):
            altas.append(f"afirmacion oferta_titulo en {SOL_ID}")
        else:
            existian.append(f"afirmacion oferta_titulo en {SOL_ID}")

        # plan_objetivo: desde plan_por_linea de oferta.yaml (explícito, sin heurísticas)
        obj_altas = 0
        for plan_id, linea_sufijo in plan_por_linea.items():
            linea_id = f"linea:coforge:{linea_sufijo}"
            if not conn.execute("SELECT 1 FROM plan WHERE id=?", (plan_id,)).fetchone():
                avisos.append(f"plan_objetivo: plan {plan_id} no existe en DB, se omite")
                continue
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (linea_id,)).fetchone():
                avisos.append(f"plan_objetivo: {linea_id} no existe, se omite {plan_id}")
                continue
            rc = conn.execute(
                "INSERT OR IGNORE INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                (plan_id, linea_id),
            ).rowcount
            if rc == 1:
                altas.append(f"plan_objetivo {plan_id} → {linea_id}")
                obj_altas += 1
            else:
                existian.append(f"plan_objetivo {plan_id} → {linea_id}")

        if obj_altas > 0:
            evento(conn, args.actor, "plan_objetivo_lineas",
                   f"{obj_altas} PLAN-CS-T enlazados a linea_oferta como objetivo")

        # plan_linea auxiliar en solución (reverse de plan_por_linea: línea → plan)
        pl_altas = 0
        for plan_id, linea_sufijo in plan_por_linea.items():
            campo = f"plan_linea:{linea_sufijo}"
            if afirmar(conn, args.actor, SOL_ID, campo, plan_id):
                altas.append(f"plan_linea:{linea_sufijo} = {plan_id}")
                pl_altas += 1
            else:
                existian.append(f"plan_linea:{linea_sufijo}")
        if pl_altas > 0:
            evento(conn, args.actor, "plan_linea_sincronizada",
                   f"{pl_altas} plan_linea en solución desde plan_por_linea", nodo_id=SOL_ID)

        # commit por fichero
        escrito_por = conn.execute(
            "SELECT id, nodo_id, valor FROM afirmacion WHERE campo='escrito_por' AND vigente=1"
        ).fetchall()
        for afirm_id, nodo_id, agente in escrito_por:
            ya_commit = conn.execute(
                "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='commit' AND vigente=1",
                (nodo_id,),
            ).fetchone()
            if ya_commit:
                existian.append(f"commit ya existe para {nodo_id}")
                continue

            ruta = nodo_id_a_ruta(nodo_id)
            if not ruta:
                continue
            rama = agente_a_rama(agente)
            sha = obtener_commit_fichero(ruta, rama)
            if not sha:
                avisos.append(f"commit: sin sha para {ruta} en {rama}")
                continue

            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (nodo_id, "commit", sha, "observado", FUENTE, args.actor, ahora()),
            )
            altas.append(f"commit {sha[:12]} en {nodo_id}")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    for a in avisos:
        print(f"  ! {a}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")
        return

    q = lambda sql: conn.execute(sql).fetchone()[0]
    print("\n[comprobación]")
    print("  nodo solución existe  :", "SÍ" if conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone() else "NO")
    print("  relaciones cubre sol  :", q(f"SELECT COUNT(*) FROM relacion WHERE origen='{SOL_ID}' AND tipo='cubre'"))
    print("  relaciones cubre mod→línea:", q(f"SELECT COUNT(*) FROM relacion WHERE tipo='cubre' AND origen!='{SOL_ID}' AND destino LIKE 'linea:coforge:%'"))
    print("  afirmaciones tecnico  :", q(f"SELECT COUNT(*) FROM afirmacion WHERE nodo_id='{SOL_ID}' AND campo LIKE 'tecnico:%' AND vigente=1"))
    print("  plan_objetivo lineas  :", q("SELECT COUNT(*) FROM plan_objetivo WHERE plan_id LIKE 'PLAN-CS-T%' AND nodo_id LIKE 'linea:%'"))
    print("  afirmaciones commit   :", q("SELECT COUNT(*) FROM afirmacion WHERE campo='commit' AND vigente=1"))
    conn.close()


if __name__ == "__main__":
    main()
