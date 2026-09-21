"""F0.6 R7: comprobar hash del esquema de registry.db.

Calcula sha256 del .schema completo, compara con el ultimo esquema_hash
registrado en afirmacion. Si difiere (o es la primera vez), registra evento
esquema_hash y la afirmacion nueva (versionada). Muestra las diferencias
linea a linea y detecta DROP TRIGGER / nuevos triggers.

    python3 comprobar_esquema.py --db ~/sypnose-f1/registry.db [--registrar]

Sin --registrar solo compara e imprime. Con --registrar, escribe en la BD.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, procedencia, registrar_evento

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
NODO = "plantilla:microservicio-ia"
CAMPO = "esquema_hash"
FUENTE = "plantilla/comprobar_esquema.py"


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def obtener_esquema(conn):
    rows = conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name").fetchall()
    return "\n".join(r[0] for r in rows)


def hash_esquema(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def extraer_triggers(texto):
    triggers = {}
    for linea in texto.split("\n"):
        stripped = linea.strip()
        if stripped.upper().startswith("CREATE TRIGGER"):
            parts = stripped.split()
            for i, p in enumerate(parts):
                if p.upper() in ("TRIGGER", "EXISTS") and i + 1 < len(parts):
                    continue
                if p.upper() not in ("CREATE", "TRIGGER", "IF", "NOT", "EXISTS"):
                    triggers[p] = stripped
                    break
    return triggers


def diff_esquemas(viejo, nuevo):
    lineas_viejas = set(viejo.strip().split("\n")) if viejo else set()
    lineas_nuevas = set(nuevo.strip().split("\n"))
    eliminadas = lineas_viejas - lineas_nuevas
    anadidas = lineas_nuevas - lineas_viejas
    return eliminadas, anadidas


def main():
    ap = argparse.ArgumentParser(description="F0.6 comprobar hash esquema registry.db")
    ap.add_argument("--db", required=True)
    ap.add_argument("--registrar", action="store_true", help="registrar el hash nuevo (escribir en BD)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    esquema = obtener_esquema(conn)
    h = hash_esquema(esquema)
    triggers = extraer_triggers(esquema)

    print(f"[esquema] {len(esquema)} chars, {len(esquema.split(chr(10)))} lineas, {len(triggers)} triggers")
    print(f"[hash] {h}")
    print(f"[triggers] {', '.join(sorted(triggers.keys()))}")

    reg = conn.execute(
        "SELECT id, valor, cuando FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
        (NODO, CAMPO),
    ).fetchone()

    if reg:
        reg_id, reg_hash, reg_cuando = reg
        print(f"\n[registrado] {reg_hash} ({reg_cuando})")

        if reg_hash == h:
            print("[OK] esquema sin cambios")
            conn.close()
            return

        print(f"[CAMBIO] hash difiere: registrado={reg_hash[:16]}... actual={h[:16]}...")

        viejo_esquema = conn.execute(
            "SELECT evidencia FROM afirmacion WHERE id=?", (reg_id,)
        ).fetchone()
        viejo_texto = viejo_esquema[0] if viejo_esquema and viejo_esquema[0] else ""

        eliminadas, anadidas = diff_esquemas(viejo_texto, esquema)

        if eliminadas:
            print(f"\n  LINEAS ELIMINADAS ({len(eliminadas)}):")
            for l in sorted(eliminadas):
                print(f"    - {l[:120]}")
                if "TRIGGER" in l.upper():
                    print(f"      *** DROP TRIGGER detectado ***")

        if anadidas:
            print(f"\n  LINEAS ANADIDAS ({len(anadidas)}):")
            for l in sorted(anadidas):
                print(f"    + {l[:120]}")
                if "TRIGGER" in l.upper():
                    print(f"      *** NUEVO TRIGGER detectado ***")

        triggers_viejos = extraer_triggers(viejo_texto) if viejo_texto else {}
        triggers_eliminados = set(triggers_viejos.keys()) - set(triggers.keys())
        triggers_nuevos = set(triggers.keys()) - set(triggers_viejos.keys())

        if triggers_eliminados:
            print(f"\n  DROP TRIGGER: {', '.join(sorted(triggers_eliminados))}")
        if triggers_nuevos:
            print(f"\n  NUEVOS TRIGGERS: {', '.join(sorted(triggers_nuevos))}")

    else:
        print("\n[PRIMERA VEZ] no hay esquema_hash registrado")

    if not args.registrar:
        print("\n[INFO] usa --registrar para escribir el hash nuevo en la BD")
        conn.close()
        return

    backup_registro(conn, db_path, "pre-esquema-hash")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if reg:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (reg[0],))

        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, evidencia) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (NODO, CAMPO, h, "observado", FUENTE, ACTOR, ts, esquema),
        )

        detalle_cambio = ""
        if reg:
            viejo_esquema = conn.execute(
                "SELECT evidencia FROM afirmacion WHERE id=?", (reg[0],)
            ).fetchone()
            viejo_texto = viejo_esquema[0] if viejo_esquema and viejo_esquema[0] else ""
            triggers_viejos = extraer_triggers(viejo_texto) if viejo_texto else {}
            triggers_eliminados = set(triggers_viejos.keys()) - set(triggers.keys())
            triggers_nuevos = set(triggers.keys()) - set(triggers_viejos.keys())
            if triggers_eliminados:
                detalle_cambio += f" DROP TRIGGER: {','.join(sorted(triggers_eliminados))}."
            if triggers_nuevos:
                detalle_cambio += f" NUEVOS: {','.join(sorted(triggers_nuevos))}."

        registrar_evento(
            conn, ts, ACTOR, "esquema_hash",
            f"hash esquema {h[:16]}... ({len(triggers)} triggers).{detalle_cambio}"
            f"{' Anterior: ' + reg[1][:16] + '...' if reg else ' Primera vez.'}",
            nodo_id=NODO,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid = conn.execute("SELECT max(id) FROM evento WHERE accion='esquema_hash'").fetchone()[0]
    print(f"\n[OK] esquema_hash registrado: {h[:16]}...")
    print(f"[evento] {eid}")
    conn.close()


if __name__ == "__main__":
    main()
