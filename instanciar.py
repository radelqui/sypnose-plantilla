"""TRASPASO-4 D2 v3: instanciar el molde para un nuevo proyecto.

El molde (plantilla-microservicio-ia) tiene 15 raíces linea_oferta y NADA más (sin requisitos).
Instanciar crea: colección, nodo solución (sin cubre: queda "vacío"),
15 planes PLAN-<SIGLA>-T01..15 en propuesto con R0 bootstrap + tarea.

Roles: se leen de oferta.yaml sección roles_por_linea. Si una línea no tiene rol → ABORTA.
Oferta: ruta fija (oferta-coforge.txt junto a este script). No existe --oferta.
Git status limpio + oferta_hash + oferta_commit verificados antes de escribir.
R0 lifecycle: 07-verificador pone tarea en espera_firma cuando comprobación R0 dé ≥1;
              la tarea pasa a hecha SOLO con firma de Carlos (D4: solo humanos → declarado).

    python3 instanciar.py --db ~/sypnose-f1/registry.db --slug bedrock-agent --sigla BA
    python3 instanciar.py --db ~/sypnose-f1/registry.db --slug bedrock-agent --sigla BA --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/instanciar.py"
COLECCION_MOLDE = "plantilla-microservicio-ia"
NODO_PLANTILLA = "plantilla:microservicio-ia"
OFERTA_PATH = Path(__file__).resolve().parent / "oferta-coforge.txt"
OFERTA_YAML = Path(__file__).resolve().parent / "oferta.yaml"
PLANTILLA_DIR = OFERTA_PATH.parent


def cargar_roles() -> dict[str, tuple[str, str]]:
    if not OFERTA_YAML.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_YAML}")
    data = yaml.safe_load(OFERTA_YAML.read_text(encoding="utf-8"))
    mapping = data.get("roles_por_linea")
    if not mapping:
        sys.exit("[FALLO] oferta.yaml no tiene sección roles_por_linea")
    return {lid: (v["rol"], v["modelo"]) for lid, v in mapping.items()}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def hash_oferta(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


def verificar_git_limpio() -> None:
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
                 f"Haz 'git add + git commit' antes de ejecutar instanciar.py.")
    staged = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "diff", "--cached", "--quiet"],
        capture_output=True, text=True, timeout=10,
    )
    if staged.returncode != 0:
        sys.exit("[FALLO] repo plantilla tiene cambios staged sin commit. Haz 'git commit' primero.")


def obtener_commit_head() -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        sys.exit(f"[FALLO] git rev-parse HEAD falló: {r.stderr.strip()}")
    return r.stdout.strip()


def verificar_oferta_canonica(conn: sqlite3.Connection, h: str) -> None:
    reg_hash = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='oferta_hash' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_hash:
        sys.exit("[FALLO] no hay oferta_hash registrado. Ejecuta 'raiz.py sync --registrar-hash' primero.")
    if reg_hash[0] != h:
        sys.exit(f"[FALLO] hash del fichero ({h}) no coincide con el canónico ({reg_hash[0]}).")

    commit_actual = obtener_commit_head()
    reg_commit = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='oferta_commit' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_commit:
        sys.exit("[FALLO] no hay oferta_commit registrado. Ejecuta 'raiz.py sync --registrar-hash' primero.")
    if reg_commit[0] != commit_actual:
        sys.exit(f"[FALLO] commit HEAD ({commit_actual[:12]}) no coincide con el registrado ({reg_commit[0][:12]}).")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-instanciar.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def evento(conn, actor, accion, detalle, nodo_id=None, plan_id=None):
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
        (ahora(), actor, accion, nodo_id, plan_id, detalle),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--slug", required=True, help="identificador del proyecto (ej. bedrock-agent)")
    ap.add_argument("--sigla", required=True, help="sigla corta para planes (ej. BA → PLAN-BA-T01)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_git_limpio()

    sys.path.insert(0, str(Path(__file__).parent))
    from parser_oferta import extraer_lineas

    if not OFERTA_PATH.exists():
        sys.exit(f"[FALLO] no existe {OFERTA_PATH}")
    texto = OFERTA_PATH.read_text(encoding="utf-8")
    lineas = extraer_lineas(texto)
    if not lineas:
        sys.exit("[FALLO] el parser no extrajo ninguna línea")
    h = hash_oferta(texto)

    roles = cargar_roles()
    sin_rol = [l["id"] for l in lineas if l["id"] not in roles]
    if sin_rol:
        sys.exit(f"[FALLO] líneas sin rol en oferta.yaml roles_por_linea: {', '.join(sin_rol)}. "
                 f"Añádelas antes de instanciar.")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_oferta_canonica(conn, h)

    col_id = args.slug
    sol_id = f"sol:{args.slug}"

    if conn.execute("SELECT 1 FROM coleccion WHERE id=?", (col_id,)).fetchone():
        sys.exit(f"[FALLO] colección '{col_id}' ya existe")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    cambios = []

    try:
        conn.execute(
            "INSERT INTO coleccion (id, nombre, regla) VALUES (?, ?, ?)",
            (col_id, col_id, f"pendiente-sintaxis-E11: pertenencia por ancla (instancia de {COLECCION_MOLDE})"),
        )
        cambios.append(f"coleccion {col_id}")

        conn.execute(
            "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
            "VALUES (?, 'solucion', ?, ?, 'activo', ?, 'humano')",
            (sol_id, f"{args.slug} (instancia de {COLECCION_MOLDE})", col_id, ahora()),
        )
        conn.execute("INSERT INTO ancla (coleccion_id, nodo_id) VALUES (?, ?)", (col_id, sol_id))
        evento(conn, ACTOR, "instancia_creada",
               f"colección {col_id} + solución {sol_id} desde molde {COLECCION_MOLDE}", nodo_id=sol_id)
        cambios.append(f"nodo {sol_id} + ancla")

        for linea in lineas:
            lid = linea["id"]
            plan_id = f"PLAN-{args.sigla}-{lid}"
            rol, modelo = roles[lid]
            agente = f"IA:{rol}:{modelo}"

            conn.execute(
                "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor) VALUES (?,?,?,?,?,?,?,?)",
                (plan_id, "mantener",
                 f"[{col_id}] {linea['texto'][:200]}",
                 f"linea:coforge:{lid}",
                 "línea de la oferta",
                 rol,
                 "propuesto",
                 ACTOR),
            )
            conn.execute(
                "INSERT INTO plan_objetivo (plan_id, nodo_id, papel) VALUES (?, ?, 'objetivo')",
                (plan_id, sol_id),
            )

            ears_r0 = (f"Antes de escribir código para esta línea, el rol {rol} "
                       f"DEBE registrar el requisito comprobable de su solución (R1+) "
                       f"con su comprobación ejecutable")
            comprobacion_r0 = f"SELECT COUNT(*) FROM requisito WHERE plan_id='{plan_id}' AND ref<>'R0' → ≥1"

            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, "R0", ears_r0, comprobacion_r0),
            )
            conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (plan_id, "R0", "Definir requisito y comprobación de la línea", "pendiente", agente),
            )

            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (sol_id, f"plan_linea:{lid}", plan_id, "observado", FUENTE, ACTOR, ahora()),
            )

            evento(conn, ACTOR, "plan_instanciado",
                   f"{plan_id}: {linea['texto'][:100]}", nodo_id=sol_id, plan_id=plan_id)
            cambios.append(f"{plan_id} + R0 + tarea")

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[resumen] {len(cambios)} cambios:")
    for c in cambios:
        print(f"  + {c}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")
        conn.close()
        return

    print("\n[verificación]")
    c1 = conn.execute("SELECT COUNT(*) FROM plan WHERE id LIKE ? AND estado='propuesto'",
                       (f"PLAN-{args.sigla}-%",)).fetchone()[0]
    print(f"  planes propuesto: {c1}/{len(lineas)}")
    c2 = conn.execute("SELECT COUNT(*) FROM requisito WHERE plan_id LIKE ? AND ref='R0'",
                       (f"PLAN-{args.sigla}-%",)).fetchone()[0]
    print(f"  R0 requisitos: {c2}/{len(lineas)}")
    c3 = conn.execute("SELECT COUNT(*) FROM tarea WHERE plan_id LIKE ? AND req_ref='R0'",
                       (f"PLAN-{args.sigla}-%",)).fetchone()[0]
    print(f"  tareas R0: {c3}/{len(lineas)}")
    c4 = conn.execute("SELECT COUNT(*) FROM relacion WHERE origen=? AND tipo='cubre'",
                       (sol_id,)).fetchone()[0]
    print(f"  relaciones cubre: {c4} (debe ser 0)")

    conn.close()


if __name__ == "__main__":
    main()
