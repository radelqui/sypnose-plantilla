"""TRASPASO-4 A4: firma humana, firma de tareas y nombre publico.

    python3 firmar.py firma   --db DB --nodo sol:coforge:rag-banking-agent --actor H:carlos
    python3 firmar.py tarea   --db DB --plan PLAN-CS-T01 --ids 9 33 48 --actor H:carlos --detalle "texto"
    python3 firmar.py nombre  --db DB --actor H:carlos --nombre "Carlos (Lead)"
    python3 firmar.py nombre  --db DB --actor IA:02-backend-api:claude-sonnet-5 --nombre "Agente backend"
    python3 firmar.py listar  --db DB
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import verificar_repo_limpio

FUENTE = "plantilla/firmar.py"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-firma.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def conectar(db_str: str) -> tuple[sqlite3.Connection, Path]:
    db_path = Path(db_str).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn, db_path


def verificar_evento_verificado(conn, tarea_id):
    """F0.1 D7: exige evento verificado posterior a tarea_entregada con
    actor == tarea.verificada_por. Sin este evento la firma no procede."""
    row = conn.execute(
        "SELECT verificada_por, agente, plan_id FROM tarea WHERE id=?", (tarea_id,)
    ).fetchone()
    if not row:
        return False, f"tarea {tarea_id} no existe"
    vp, agente, plan_id = row
    if not vp:
        return False, "verificada_por es NULL"

    entrega = conn.execute(
        "SELECT id, cuando FROM evento WHERE accion='tarea_entregada' "
        "AND plan_id=? AND detalle LIKE ? ORDER BY id DESC LIMIT 1",
        (plan_id, f"tarea {tarea_id} %"),
    ).fetchone()
    if not entrega:
        return False, f"no hay evento tarea_entregada para tarea {tarea_id} en {plan_id}"

    verificado = conn.execute(
        "SELECT id, actor, cuando, detalle FROM evento WHERE accion='verificado' "
        "AND plan_id=? AND detalle LIKE ? AND cuando > ? ORDER BY id DESC LIMIT 1",
        (plan_id, f"tarea {tarea_id} %", entrega[1]),
    ).fetchone()
    if not verificado:
        return False, (
            f"no hay evento verificado posterior a la entrega (evento {entrega[0]}) "
            f"para tarea {tarea_id} en {plan_id}"
        )
    detalle_v = verificado[3] if len(verificado) > 3 else ""
    if detalle_v and ": NO CUMPLE" in detalle_v:
        return False, (
            f"veredicto NO CUMPLE para tarea {tarea_id} (evento {verificado[0]})"
        )
    if verificado[1] != vp:
        return False, (
            f"verificada_por={vp} pero evento verificado {verificado[0]} "
            f"es de actor {verificado[1]}"
        )
    return True, f"evento verificado {verificado[0]} por {verificado[1]} posterior a entrega {entrega[0]}"


def cmd_firma(args):
    verificar_repo_limpio()
    conn, db_path = conectar(args.db)
    actor = conn.execute("SELECT id, clase FROM actor WHERE id=?", (args.actor,)).fetchone()
    if not actor:
        sys.exit(f"[FALLO] actor {args.actor} no existe")
    if actor[1] != "humano":
        sys.exit(f"[FALLO] solo humanos pueden firmar (D4); {args.actor} es {actor[1]}")
    if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (args.nodo,)).fetchone():
        sys.exit(f"[FALLO] nodo {args.nodo} no existe")

    ya = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='firma' AND vigente=1",
        (args.nodo,),
    ).fetchone()
    if ya:
        print(f"[INFO] ya existe firma vigente: {ya[1]}")
        if not args.force:
            sys.exit("usa --force para versionar la firma existente")

    b = backup(conn, db_path)
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if ya:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (ya[0],))

        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
            (args.nodo, "firma", f"{args.actor} · {ts}", "declarado", FUENTE, args.actor, ts),
        )
        detalle_ev = args.detalle if args.detalle else f"firmado por {args.actor}"
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
            (ts, args.actor, "firma_humana", args.nodo, detalle_ev),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] {args.nodo} firmado por {args.actor} a las {ts}")


def asegurar_nodo_actor(conn, actor_id, actor_escritor):
    """Crea nodo tipo 'actor' si no existe (afirmacion.nodo_id requiere FK)."""
    if conn.execute("SELECT 1 FROM nodo WHERE id=?", (actor_id,)).fetchone():
        return False
    actor = conn.execute("SELECT clase, rol FROM actor WHERE id=?", (actor_id,)).fetchone()
    if not actor:
        return False
    ts = ahora()
    conn.execute(
        "INSERT INTO nodo (id, tipo, nombre, ambito, vitalidad, descubierto_en, descubierto_por) "
        "VALUES (?, 'actor', ?, 'coforge-santander', 'activo', ?, ?)",
        (actor_id, f"{actor[0]}:{actor[1]}" if actor[1] else actor[0], ts, FUENTE),
    )
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
        (ts, actor_escritor, "alta_nodo_actor", actor_id, f"nodo actor creado para afirmaciones"),
    )
    return True


def cmd_nombre(args):
    verificar_repo_limpio()
    conn, db_path = conectar(args.db)
    if not conn.execute("SELECT 1 FROM actor WHERE id=?", (args.actor,)).fetchone():
        sys.exit(f"[FALLO] actor {args.actor} no existe")

    ya = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='nombre_publico' AND vigente=1",
        (args.actor,),
    ).fetchone()

    if ya and ya[1] == args.nombre:
        print(f"[INFO] nombre_publico ya es '{args.nombre}'")
        return

    b = backup(conn, db_path)
    print(f"[backup] {b}")

    ts = ahora()
    actor_escritor = args.actor if conn.execute(
        "SELECT clase FROM actor WHERE id=?", (args.actor,)
    ).fetchone()[0] == "humano" else "IA:05-arquitecto-sypnose:claude-opus-4-6"

    conn.execute("BEGIN IMMEDIATE")
    try:
        asegurar_nodo_actor(conn, args.actor, actor_escritor)

        if ya:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (ya[0],))

        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
            (args.actor, "nombre_publico", args.nombre, "propuesto", FUENTE, actor_escritor, ts),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
            (ts, actor_escritor, "nombre_publico_asignado", args.actor, f"nombre_publico = {args.nombre}"),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] {args.actor} → nombre_publico = '{args.nombre}'")


def cmd_tarea(args):
    """Firma (espera_firma -> hecha) una o mas tareas con actor humano (D4)."""
    verificar_repo_limpio()
    conn, db_path = conectar(args.db)

    actor = conn.execute("SELECT id, clase FROM actor WHERE id=?", (args.actor,)).fetchone()
    if not actor:
        sys.exit(f"[FALLO] actor {args.actor} no existe")
    if actor[1] != "humano":
        sys.exit(f"[FALLO] solo humanos pueden firmar tareas (D4); {args.actor} es {actor[1]}")

    tareas = []
    for tid in args.ids:
        row = conn.execute(
            "SELECT id, plan_id, req_ref, titulo, progreso, agente, verificada_por "
            "FROM tarea WHERE id=? AND plan_id=?",
            (tid, args.plan),
        ).fetchone()
        if not row:
            sys.exit(f"[FALLO] tarea {tid} no existe en {args.plan}")
        t_id, t_plan, t_ref, t_titulo, t_prog, t_agente, t_verif = row
        if t_prog != "espera_firma":
            sys.exit(f"[FALLO] tarea {tid} progreso={t_prog}, esperado espera_firma")
        if not t_verif:
            sys.exit(f"[FALLO] tarea {tid} sin verificada_por (D7)")
        if t_verif == t_agente:
            sys.exit(f"[FALLO] tarea {tid} verificada_por={t_verif} == agente (D7: quien ejecuta no juzga)")

        ok_ev, motivo_ev = verificar_evento_verificado(conn, t_id)
        if not ok_ev:
            sys.exit(f"[FALLO] tarea {tid} D7 evento verificado: {motivo_ev}")

        tareas.append((t_id, t_ref, t_titulo, t_verif))
        print(f"[validada] tarea {t_id} ({t_ref}): {t_titulo} — verificada por {t_verif} ({motivo_ev})")

    b = backup(conn, db_path)
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for t_id, t_ref, t_titulo, t_verif in tareas:
            conn.execute("UPDATE tarea SET progreso='hecha' WHERE id=?", (t_id,))
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, args.actor, "firma_tarea", args.plan,
                 f"tarea {t_id} ({t_ref}): {t_titulo} — {args.detalle}"),
            )
            print(f"[firmada] tarea {t_id} → hecha")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    print(f"[OK] {len(tareas)} tareas firmadas por {args.actor}")


def cmd_listar(args):
    conn, _ = conectar(args.db)
    firmas = conn.execute(
        "SELECT nodo_id, valor, cuando FROM afirmacion WHERE campo='firma' AND vigente=1 ORDER BY cuando DESC"
    ).fetchall()
    nombres = conn.execute(
        "SELECT nodo_id, valor FROM afirmacion WHERE campo='nombre_publico' AND vigente=1 ORDER BY nodo_id"
    ).fetchall()
    print(f"Firmas vigentes: {len(firmas)}")
    for nid, val, cuando in firmas:
        print(f"  {nid}: {val}")
    print(f"\nNombres publicos: {len(nombres)}")
    for nid, val in nombres:
        print(f"  {nid} → {val}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_firma = sub.add_parser("firma")
    p_firma.add_argument("--db", required=True)
    p_firma.add_argument("--nodo", required=True, help="nodo a firmar (sol:coforge:rag-banking-agent)")
    p_firma.add_argument("--actor", required=True, help="actor humano (H:carlos)")
    p_firma.add_argument("--detalle", default="", help="texto detalle para el evento (default: 'firmado por <actor>')")
    p_firma.add_argument("--force", action="store_true", help="versionar firma existente")

    p_tarea = sub.add_parser("tarea")
    p_tarea.add_argument("--db", required=True)
    p_tarea.add_argument("--plan", required=True, help="plan_id, ej. PLAN-CS-T01")
    p_tarea.add_argument("--ids", nargs="+", type=int, required=True, help="ids de tareas a firmar")
    p_tarea.add_argument("--actor", required=True, help="actor humano (H:carlos)")
    p_tarea.add_argument("--detalle", required=True, help="texto de detalle para el evento")

    p_nombre = sub.add_parser("nombre")
    p_nombre.add_argument("--db", required=True)
    p_nombre.add_argument("--actor", required=True, help="actor (IA:02-backend-api:... o H:carlos)")
    p_nombre.add_argument("--nombre", required=True, help="nombre publico para la vista")

    p_list = sub.add_parser("listar")
    p_list.add_argument("--db", required=True)

    args = ap.parse_args()
    {"firma": cmd_firma, "tarea": cmd_tarea, "nombre": cmd_nombre, "listar": cmd_listar}[args.cmd](args)


if __name__ == "__main__":
    main()
