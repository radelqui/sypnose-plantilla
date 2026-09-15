"""TRASPASO-4 A4: firma humana y nombre público como afirmaciones.

    python3 firmar.py firma   --db DB --nodo sol:coforge:rag-banking-agent --actor H:carlos
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
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, nodo_id, detalle) VALUES (?,?,?,?,?)",
            (ts, args.actor, "firma_humana", args.nodo, f"firmado por {args.actor}"),
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
    print(f"\nNombres públicos: {len(nombres)}")
    for nid, val in nombres:
        print(f"  {nid} → {val}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_firma = sub.add_parser("firma")
    p_firma.add_argument("--db", required=True)
    p_firma.add_argument("--nodo", required=True, help="nodo a firmar (sol:coforge:rag-banking-agent)")
    p_firma.add_argument("--actor", required=True, help="actor humano (H:carlos)")
    p_firma.add_argument("--force", action="store_true", help="versionar firma existente")

    p_nombre = sub.add_parser("nombre")
    p_nombre.add_argument("--db", required=True)
    p_nombre.add_argument("--actor", required=True, help="actor (IA:02-backend-api:... o H:carlos)")
    p_nombre.add_argument("--nombre", required=True, help="nombre público para la vista")

    p_list = sub.add_parser("listar")
    p_list.add_argument("--db", required=True)

    args = ap.parse_args()
    {"firma": cmd_firma, "nombre": cmd_nombre, "listar": cmd_listar}[args.cmd](args)


if __name__ == "__main__":
    main()
