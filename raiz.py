"""TRASPASO-4 A2 (D3 v4): operaciones sobre raíces linea_oferta.

    python3 raiz.py add     --db DB
    python3 raiz.py edit    --db DB --id T01 [--alcance]
    python3 raiz.py retirar --db DB --id T03
    python3 raiz.py listar  --db DB
    python3 raiz.py sync    --db DB [--registrar-hash]

D3 v4: plantilla/ es su propio repo git. La oferta canónica es UNA ruta fija
(oferta-coforge.txt junto a este script). No existe --oferta.
El fichero debe estar commiteado (git -C plantilla status limpio).
Dos afirmaciones canónicas en el nodo plantilla:
  - oferta_hash: SHA-256 truncado a 16 hex del contenido
  - oferta_commit: git rev-parse HEAD del repo plantilla
edit/add/sync comparan AMBOS antes de escribir. Si difieren → exit ≠0.
sync --registrar-hash actualiza ambas (solo si git status limpio).
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/raiz.py"
NODO_PLANTILLA = "plantilla:microservicio-ia"
COLECCION = "plantilla-microservicio-ia"
SOL_ID = "sol:coforge:rag-banking-agent"
OFERTA_PATH = Path(__file__).resolve().parent / "oferta-coforge.txt"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-raiz.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def nodo_id(linea_id: str) -> str:
    return f"linea:coforge:{linea_id}"


def conectar(db_path_str: str, actor: str) -> tuple[sqlite3.Connection, Path]:
    db_path = Path(db_path_str).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (actor,)).fetchone():
        sys.exit(f"[FALLO] actor {actor} no existe")
    return conn, db_path


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


def hash_oferta(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


PLANTILLA_DIR = OFERTA_PATH.parent


def verificar_git_limpio() -> None:
    """Aborta si el repo plantilla tiene cualquier cambio sin commit (tracked files)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(PLANTILLA_DIR), "diff", "--quiet", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        sys.exit("[FALLO] git no encontrado; plantilla/ debe ser su propio repo git")
    except subprocess.TimeoutExpired:
        sys.exit("[FALLO] git diff timeout")
    if r.returncode != 0:
        cambios = subprocess.run(
            ["git", "-C", str(PLANTILLA_DIR), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        sys.exit(f"[FALLO] repo plantilla tiene cambios sin commit:\n{cambios.stdout.strip()}\n"
                 f"Haz 'git add + git commit' antes de ejecutar raiz.py.")
    staged = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "diff", "--cached", "--quiet"],
        capture_output=True, text=True, timeout=10,
    )
    if staged.returncode != 0:
        sys.exit("[FALLO] repo plantilla tiene cambios staged sin commit. Haz 'git commit' primero.")


def obtener_commit_head() -> str:
    """Devuelve el SHA del HEAD del repo plantilla."""
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] git rev-parse HEAD falló: {r.stderr.strip()}")
    return r.stdout.strip()


def verificar_hash_canonico(conn: sqlite3.Connection, h: str) -> None:
    reg_hash = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='oferta_hash' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_hash:
        sys.exit("[FALLO] no hay oferta_hash registrado. Ejecuta 'sync --registrar-hash' primero.")
    if reg_hash[0] != h:
        sys.exit(f"[FALLO] hash del fichero ({h}) no coincide con el canónico ({reg_hash[0]}). "
                 f"Si el cambio es intencional, haz commit y ejecuta 'sync --registrar-hash'.")

    commit_actual = obtener_commit_head()
    reg_commit = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='oferta_commit' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_commit:
        sys.exit("[FALLO] no hay oferta_commit registrado. Ejecuta 'sync --registrar-hash' primero.")
    if reg_commit[0] != commit_actual:
        sys.exit(f"[FALLO] commit HEAD ({commit_actual[:12]}) no coincide con el registrado ({reg_commit[0][:12]}). "
                 f"Si el cambio es intencional, haz commit y ejecuta 'sync --registrar-hash'.")


def cargar_oferta() -> tuple[list[dict], str]:
    sys.path.insert(0, str(Path(__file__).parent))
    from parser_oferta import extraer_lineas
    if not OFERTA_PATH.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_PATH}")
    texto = OFERTA_PATH.read_text(encoding="utf-8")
    return extraer_lineas(texto), hash_oferta(texto)


def cmd_add(args):
    verificar_git_limpio()
    lineas_parser, h = cargar_oferta()
    conn, db_path = conectar(args.db, args.actor)
    verificar_hash_canonico(conn, h)

    existentes = conn.execute(
        "SELECT id FROM nodo WHERE tipo='linea_oferta' AND id LIKE 'linea:coforge:%' ORDER BY id"
    ).fetchall()
    ids_existentes = {nid.split(":")[-1] for (nid,) in existentes}

    nuevas = [l for l in lineas_parser if l["id"] not in ids_existentes]
    if not nuevas:
        print("[INFO] todas las líneas del parser ya existen en BD")
        return

    b = backup(conn, db_path)
    print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    try:
        for linea in nuevas:
            nid = nodo_id(linea["id"])
            conn.execute(
                "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
                "VALUES (?, 'linea_oferta', ?, 'plantilla', 'activo', ?, 'humano')",
                (nid, linea["texto"], ahora()),
            )
            evento(conn, args.actor, "alta_linea_oferta",
                   f"add {linea['id']}: {linea['texto'][:120]}", nodo_id=nid)
            conn.execute(
                "INSERT INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)",
                (COLECCION, nid),
            )
            if linea.get("seccion"):
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                    (nid, "seccion", linea["seccion"], "observado", FUENTE, args.actor, ahora()),
                )
            print(f"  + {linea['id']}: {linea['texto'][:100]}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] {len(nuevas)} raíces creadas desde el parser")
    conn.close()


def cmd_edit(args):
    verificar_git_limpio()
    lineas_parser, h = cargar_oferta()
    linea_parser = next((l for l in lineas_parser if l["id"] == args.id), None)
    if not linea_parser:
        sys.exit(f"[FALLO] {args.id} no existe en el parser (oferta-coforge.txt). Edita primero el fichero fuente.")

    conn, db_path = conectar(args.db, args.actor)
    verificar_hash_canonico(conn, h)

    nid = nodo_id(args.id)
    actual = conn.execute("SELECT nombre, vitalidad FROM nodo WHERE id=?", (nid,)).fetchone()
    if not actual:
        sys.exit(f"[FALLO] no existe {nid}")
    if actual[1] in ("inactivo_por_diseno",):
        sys.exit(f"[FALLO] {nid} está derogada (inactivo_por_diseno)")

    texto_anterior = actual[0]
    nuevo_texto = linea_parser["texto"]
    if texto_anterior == nuevo_texto:
        print(f"[INFO] texto idéntico entre parser y BD, nada que cambiar")
        return

    print(f"[diff] {args.id}:")
    print(f"  BD    : {texto_anterior}")
    print(f"  parser: {nuevo_texto}")

    b = backup(conn, db_path)
    print(f"[backup] {b}")
    tipo_cambio = "cambio_alcance" if args.alcance else "retoque"

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("UPDATE nodo SET nombre=? WHERE id=?", (nuevo_texto, nid))
        evento(conn, args.actor, f"linea_modificada:{tipo_cambio}",
               f"edit {args.id}: {texto_anterior[:80]} → {nuevo_texto[:80]}", nodo_id=nid)

        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) VALUES (?,?,?,?,?,?,?,0)",
            (nid, "texto_anterior", texto_anterior, "observado", FUENTE, args.actor, ahora()),
        )

        if args.alcance:
            stats = {"rel_inferido": 0, "afirm_invalidadas": 0, "revisar": 0, "tareas_devueltas": 0}

            cubren = conn.execute(
                "SELECT origen, destino FROM relacion WHERE destino=? AND tipo='cubre'",
                (nid,),
            ).fetchall()
            for orig, dest in cubren:
                conn.execute(
                    "UPDATE relacion SET certeza='inferido' WHERE origen=? AND destino=? AND tipo='cubre'",
                    (orig, dest),
                )
                evento(conn, args.actor, "relacion_inferida_por_alcance",
                       f"cubre {orig}→{dest} → inferido por cambio alcance en {args.id}", nodo_id=orig)
                stats["rel_inferido"] += 1

            nodos_que_cubren = [orig for orig, _ in cubren]
            for nodo_cub in nodos_que_cubren:
                otras_lineas = conn.execute(
                    "SELECT COUNT(*) FROM relacion WHERE origen=? AND tipo='cubre' AND destino!=? "
                    "AND destino IN (SELECT id FROM nodo WHERE tipo='linea_oferta')",
                    (nodo_cub, nid),
                ).fetchone()[0]

                if otras_lineas == 0:
                    afirms = conn.execute(
                        "SELECT id, campo, valor FROM afirmacion WHERE nodo_id=? AND vigente=1 "
                        "AND (campo LIKE 'escrito_por%' OR campo LIKE 'tecnico:%')",
                        (nodo_cub,),
                    ).fetchall()
                    for aid, acampo, avalor in afirms:
                        conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
                        conn.execute(
                            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (nodo_cub, acampo, avalor, "inferido", FUENTE, args.actor, ahora()),
                        )
                        stats["afirm_invalidadas"] += 1
                else:
                    conn.execute(
                        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (nodo_cub, "revisar_por_cambio", args.id, "inferido", FUENTE, args.actor, ahora()),
                    )
                    stats["revisar"] += 1

            plan_linea_campo = f"plan_linea:{args.id}"
            planes_afectados = conn.execute(
                "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                (SOL_ID, plan_linea_campo),
            ).fetchall()
            for (plan_id_val,) in planes_afectados:
                tareas = conn.execute(
                    "SELECT id FROM tarea WHERE plan_id=? AND progreso NOT IN ('devuelta','retirada')",
                    (plan_id_val,),
                ).fetchall()
                for (tid,) in tareas:
                    conn.execute("UPDATE tarea SET progreso='devuelta' WHERE id=?", (tid,))
                    evento(conn, args.actor, "tarea_devuelta_alcance",
                           f"tarea {tid} devuelta por cambio de alcance en {args.id}",
                           nodo_id=nid, plan_id=plan_id_val)
                    stats["tareas_devueltas"] += 1

            print(f"[cascada] rel→inferido: {stats['rel_inferido']}, "
                  f"afirm invalidadas/recreadas: {stats['afirm_invalidadas']}, "
                  f"revisar_por_cambio: {stats['revisar']}, "
                  f"tareas→devuelta: {stats['tareas_devueltas']}")

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] raíz {args.id} editada ({tipo_cambio})")
    conn.close()


def cmd_retirar(args):
    conn, db_path = conectar(args.db, args.actor)
    nid = nodo_id(args.id)
    actual = conn.execute("SELECT nombre, vitalidad FROM nodo WHERE id=?", (nid,)).fetchone()
    if not actual:
        sys.exit(f"[FALLO] no existe {nid}")
    if actual[1] == "inactivo_por_diseno":
        sys.exit(f"[FALLO] {nid} ya está derogada")

    b = backup(conn, db_path)
    print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("UPDATE nodo SET vitalidad='inactivo_por_diseno' WHERE id=?", (nid,))
        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
            (nid, "estado_raiz", "derogada", "observado", FUENTE, args.actor, ahora()),
        )
        evento(conn, args.actor, "linea_derogada",
               f"retirar {args.id}: {actual[0][:120]} → inactivo_por_diseno + estado_raiz=derogada",
               nodo_id=nid)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] raíz {args.id} derogada (vitalidad=inactivo_por_diseno, afirmación estado_raiz=derogada, nada borrado)")
    conn.close()


def cmd_listar(args):
    conn, _ = conectar(args.db, args.actor)
    rows = conn.execute(
        "SELECT id, nombre, vitalidad FROM nodo WHERE tipo='linea_oferta' ORDER BY id"
    ).fetchall()
    print(f"{len(rows)} raíces linea_oferta:")
    for nid, nombre, vit in rows:
        marca = " [DEROGADA]" if vit == "inactivo_por_diseno" else ""
        lid = nid.split(":")[-1]
        print(f"  {lid}{marca}: {nombre}")
    conn.close()


def cmd_sync(args):
    """Compara oferta-coforge.txt (ruta fija) con nodos en BD. Exit ≠0 si hay discrepancias."""
    verificar_git_limpio()
    sys.path.insert(0, str(Path(__file__).parent))
    from parser_oferta import extraer_lineas

    if not OFERTA_PATH.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_PATH}")
    texto = OFERTA_PATH.read_text(encoding="utf-8")
    lineas = extraer_lineas(texto)
    h = hash_oferta(texto)

    conn, db_path = conectar(args.db, args.actor)

    commit_head = obtener_commit_head()

    if args.registrar_hash:
        for campo, valor_nuevo in [("oferta_hash", h), ("oferta_commit", commit_head)]:
            registrado = conn.execute(
                "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
                (NODO_PLANTILLA, campo),
            ).fetchone()
            if registrado and registrado[1] == valor_nuevo:
                print(f"[{campo}] ya registrado: {valor_nuevo[:16]}")
            else:
                if registrado:
                    conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (registrado[0],))
                conn.execute(
                    "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                    (NODO_PLANTILLA, campo, valor_nuevo, "observado", FUENTE, ACTOR, ahora()),
                )
                print(f"[{campo}] registrado: {valor_nuevo[:16]}")
        # Invalidar el antiguo campo hash_oferta si existe (renombrado a oferta_hash)
        old = conn.execute(
            "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='hash_oferta' AND vigente=1",
            (NODO_PLANTILLA,),
        ).fetchone()
        if old:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (old[0],))
        evento(conn, ACTOR, "oferta_canonizada",
               f"oferta_hash={h}, oferta_commit={commit_head[:12]}",
               nodo_id=NODO_PLANTILLA)
    else:
        verificar_hash_canonico(conn, h)

    rows = conn.execute(
        "SELECT id, nombre FROM nodo WHERE tipo='linea_oferta' AND vitalidad!='inactivo_por_diseno' ORDER BY id"
    ).fetchall()

    print(f"[sync] oferta: {len(lineas)} líneas (hash {h}), BD: {len(rows)} nodos activos")
    discrepancias = 0
    for linea in lineas:
        nid = f"linea:coforge:{linea['id']}"
        bd_row = next((r for r in rows if r[0] == nid), None)
        if not bd_row:
            print(f"  ! {linea['id']}: en oferta pero NO en BD")
            discrepancias += 1
        elif bd_row[1] != linea["texto"]:
            print(f"  ! {linea['id']}: texto difiere")
            print(f"    oferta : {linea['texto'][:100]}")
            print(f"    BD     : {bd_row[1][:100]}")
            discrepancias += 1
    for nid, nombre in rows:
        lid = nid.split(":")[-1]
        if not any(l["id"] == lid for l in lineas):
            print(f"  ! {lid}: en BD pero NO en oferta")
            discrepancias += 1

    conn.close()
    if discrepancias == 0:
        print("[OK] parser y registro coinciden")
    else:
        print(f"[FALLO] {discrepancias} discrepancias")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", default=ACTOR)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--db", required=True)

    p_edit = sub.add_parser("edit")
    p_edit.add_argument("--db", required=True)
    p_edit.add_argument("--id", required=True, help="id de la línea (T01, T16...)")
    p_edit.add_argument("--alcance", action="store_true", help="cambio de alcance → cascada acotada")

    p_ret = sub.add_parser("retirar")
    p_ret.add_argument("--db", required=True)
    p_ret.add_argument("--id", required=True)

    p_list = sub.add_parser("listar")
    p_list.add_argument("--db", required=True)

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--db", required=True)
    p_sync.add_argument("--registrar-hash", action="store_true",
                        help="registra/actualiza el hash canónico de la oferta en el registro")

    args = ap.parse_args()
    {"add": cmd_add, "edit": cmd_edit, "retirar": cmd_retirar,
     "listar": cmd_listar, "sync": cmd_sync}[args.cmd](args)


if __name__ == "__main__":
    main()
