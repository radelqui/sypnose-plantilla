"""Barrera de integridad compartida para scripts que escriben en el registro SYPNOSE.

Todo script que modifique el registro debe llamar a verificar_repo_limpio() antes
de escribir. La función comprueba que cada fichero canónico (CANONICOS) esté
rastreado en git y sin cambios (working tree + staged).

Para scripts que leen la oferta: verificar_oferta_canonica() compara hash y commit.
oferta_commit = último commit que tocó oferta-coforge.txt (no HEAD), así un commit
de scripts no obliga a re-registrar.

Decisión lead 15-sep-2026. Corrección 07-verificador: oferta.yaml modificable sin commit.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PLANTILLA_DIR = Path(__file__).resolve().parent
NODO_PLANTILLA = "plantilla:microservicio-ia"

CANONICOS = ["oferta-coforge.txt", "oferta.yaml", "precios.yaml"]

OFERTA_PATH = PLANTILLA_DIR / "oferta-coforge.txt"
OFERTA_YAML = PLANTILLA_DIR / "oferta.yaml"
PRECIOS_PATH = PLANTILLA_DIR / "precios.yaml"


def verificar_repo_limpio() -> None:
    verificar_sin_delete()
    for f in CANONICOS:
        try:
            r = subprocess.run(
                ["git", "-C", str(PLANTILLA_DIR), "ls-files", "--error-unmatch", f],
                capture_output=True, text=True, timeout=10,
            )
        except FileNotFoundError:
            sys.exit("[FALLO] git no encontrado; plantilla/ debe ser su propio repo git")
        except subprocess.TimeoutExpired:
            sys.exit(f"[FALLO] git timeout comprobando {f}")
        if r.returncode != 0:
            sys.exit(f"[FALLO] {f} no está rastreado en el repo plantilla. Haz git add + commit.")

        r = subprocess.run(
            ["git", "-C", str(PLANTILLA_DIR), "diff", "--quiet", "HEAD", "--", f],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            sys.exit(f"[FALLO] {f} tiene cambios sin commit. Haz git add + commit primero.")

        r = subprocess.run(
            ["git", "-C", str(PLANTILLA_DIR), "diff", "--cached", "--quiet", "--", f],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            sys.exit(f"[FALLO] {f} tiene cambios staged sin commit. Haz git commit primero.")


def hash_fichero(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


def obtener_commit_oferta() -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "log", "-1", "--format=%H", "--", "oferta-coforge.txt"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit("[FALLO] no se encontró commit para oferta-coforge.txt en el repo plantilla")
    return r.stdout.strip()


CAMPO_HASH = {
    "oferta-coforge.txt": "oferta_hash",
    "oferta.yaml": "hash:oferta.yaml",
    "precios.yaml": "hash:precios.yaml",
}


def obtener_plantilla_commit() -> str:
    r = subprocess.run(
        ["git", "-C", str(PLANTILLA_DIR), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 or not r.stdout.strip():
        sys.exit("[FALLO] no se encontró HEAD en el repo plantilla")
    return r.stdout.strip()


def verificar_canonicos_registrados(conn) -> None:
    for f in CANONICOS:
        campo = CAMPO_HASH[f]
        contenido = (PLANTILLA_DIR / f).read_text(encoding="utf-8")
        h = hash_fichero(contenido)
        reg = conn.execute(
            "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
            (NODO_PLANTILLA, campo),
        ).fetchone()
        if not reg:
            sys.exit(f"[FALLO] no hay {campo} registrado. Ejecuta 'raiz.py sync --registrar-hash'.")
        if reg[0] != h:
            sys.exit(f"[FALLO] {f}: hash ({h}) ≠ registrado ({reg[0]}). Commit + sync --registrar-hash.")

    commit = obtener_commit_oferta()
    reg_commit = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='oferta_commit' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_commit:
        sys.exit("[FALLO] no hay oferta_commit registrado. Ejecuta 'raiz.py sync --registrar-hash'.")
    if reg_commit[0] != commit:
        sys.exit(f"[FALLO] commit oferta ({commit[:12]}) ≠ registrado ({reg_commit[0][:12]}). sync --registrar-hash.")

    pc = obtener_plantilla_commit()
    reg_pc = conn.execute(
        "SELECT valor FROM afirmacion WHERE nodo_id=? AND campo='plantilla_commit' AND vigente=1",
        (NODO_PLANTILLA,),
    ).fetchone()
    if not reg_pc:
        sys.exit("[FALLO] no hay plantilla_commit registrado. Ejecuta 'raiz.py sync --registrar-hash'.")
    if reg_pc[0] != pc:
        sys.exit(f"[FALLO] plantilla HEAD ({pc[:12]}) ≠ registrado ({reg_pc[0][:12]}). sync --registrar-hash.")


_RE_ACTOR07_ID = re.compile(r"^IA:07-verificador:[a-z0-9.-]+$")
_RE_HUMANO_ID = re.compile(r"^H:[a-z0-9._-]+$", re.IGNORECASE)


def actor07_valido(actor_id: str, conn, _seen: set | None = None) -> bool:
    """An IA:07-verificador:* actor is valid only if ratified by a human or by a valid 07 actor.

    Uses exact nodo_id match on actor_ratificado events only. The signer
    must be a registered human (actor table, clase='humano') or a recursively
    valid IA:07-verificador:* actor. Actor IDs must match a strict format.
    """
    if not _RE_ACTOR07_ID.match(actor_id):
        return False
    if _seen is None:
        _seen = set()
    if actor_id in _seen:
        return False
    _seen.add(actor_id)
    rows = conn.execute(
        "SELECT actor FROM evento "
        "WHERE accion = 'actor_ratificado' "
        "AND nodo_id = ? "
        "AND actor != ?",
        (actor_id, actor_id),
    ).fetchall()
    for (signer,) in rows:
        if signer.startswith("H:"):
            if conn.execute(
                "SELECT 1 FROM actor WHERE id = ? AND clase = 'humano'",
                (signer,),
            ).fetchone():
                return True
            continue
        if _RE_ACTOR07_ID.match(signer) and actor07_valido(signer, conn, _seen):
            return True
    return False


def backup_registro(conn: sqlite3.Connection, db_path: Path, sufijo: str = "pre") -> Path:
    """Backup ANTES de cualquier escritura. Devuelve la ruta del backup.

    Todos los scripts deben llamar a esta función antes de BEGIN IMMEDIATE.
    El sufijo identifica el script que hizo el backup.
    """
    destino = db_path.with_name(
        f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{sufijo}.db"
    )
    with sqlite3.connect(str(destino)) as dst:
        conn.backup(dst)
    if not destino.exists() or destino.stat().st_size == 0:
        sys.exit(f"[FALLO] backup vacío o no creado: {destino}")
    print(f"[backup] {destino} ({destino.stat().st_size} bytes)")
    return destino


_RE_DELETE_PROHIBIDO = re.compile(
    r"\bDELETE\s+FROM\s+(evidencia|evento|afirmacion|relacion|ancla)\b",
    re.IGNORECASE,
)

HISTORICO_DIR = PLANTILLA_DIR / "historico"


def verificar_sin_delete() -> None:
    """Abort if any plantilla script contains DELETE FROM on protected tables."""
    violaciones = []
    for d in (PLANTILLA_DIR, HISTORICO_DIR):
        if not d.exists():
            continue
        for py in d.glob("*.py"):
            texto = py.read_text(encoding="utf-8", errors="replace")
            for m in _RE_DELETE_PROHIBIDO.finditer(texto):
                linea = texto[:m.start()].count("\n") + 1
                violaciones.append(f"{py.name}:{linea}: {m.group(0)}")
    if violaciones:
        sys.exit(
            "[FALLO] DELETE FROM en tabla protegida (regla: solo INSERT):\n  "
            + "\n  ".join(violaciones)
        )


def extraer_carpeta(actor_id: str) -> str:
    partes = actor_id.split(":")
    return partes[1] if len(partes) >= 2 else actor_id


def verificar_d7_entrega(conn, tarea_id: int, actor_ejecutor: str) -> None:
    row = conn.execute("SELECT agente FROM tarea WHERE id=?", (tarea_id,)).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {tarea_id} no existe")
    agente = row[0]
    carpeta_actor = extraer_carpeta(actor_ejecutor)
    carpeta_agente = extraer_carpeta(agente)
    if carpeta_actor != carpeta_agente:
        sys.exit(
            f"[FALLO] D7 compuerta: actor ({actor_ejecutor}, carpeta={carpeta_actor}) "
            f"no es el agente de la tarea (agente={agente}, carpeta={carpeta_agente}). "
            f"Solo el agente de la tarea puede entregarla."
        )


def verificar_d7_verificador(conn, verificador: str) -> None:
    if _RE_HUMANO_ID.match(verificador):
        if not conn.execute(
            "SELECT 1 FROM actor WHERE id=? AND clase='humano'", (verificador,),
        ).fetchone():
            sys.exit(
                f"[FALLO] D7 compuerta: verificador humano ({verificador}) no registrado en tabla actor"
            )
        return
    if not _RE_ACTOR07_ID.match(verificador):
        sys.exit(
            f"[FALLO] D7 compuerta: verificador ({verificador}) no es IA:07-verificador:* ni H:*"
        )
    if not actor07_valido(verificador, conn):
        sys.exit(
            f"[FALLO] D7 compuerta: verificador ({verificador}) no está ratificado"
        )


def verificar_d7_auto_verificacion(conn, tarea_id: int, verificador: str) -> None:
    row = conn.execute("SELECT agente FROM tarea WHERE id=?", (tarea_id,)).fetchone()
    if not row:
        sys.exit(f"[FALLO] tarea {tarea_id} no existe")
    agente = row[0]
    if agente and agente.startswith("IA:07-verificador:") and verificador.startswith("IA:07-verificador:"):
        sys.exit(
            f"[FALLO] D7b compuerta: agente ({agente}) y verificador ({verificador}) son el mismo rol "
            f"(07-verificador). Tareas de 07 las verifica un humano (H:*)."
        )


def verificar_oferta_canonica(conn, h: str) -> None:
    verificar_canonicos_registrados(conn)


def procedencia() -> str:
    """F0.5 R6: host, usuario de sistema y pid del proceso.

    Unico punto de insercion para trazabilidad de escrituras al registro.
    Todos los scripts DEBEN incluir esta cadena en el detalle de sus eventos
    via registrar_evento() o manualmente.
    """
    return f"host={platform.node()} user={os.getenv('USER', os.getenv('USERNAME', '?'))} pid={os.getpid()}"


def registrar_evento(
    conn: sqlite3.Connection,
    cuando: str,
    actor: str,
    accion: str,
    detalle: str,
    plan_id: str | None = None,
    nodo_id: str | None = None,
) -> int:
    """F0.5 R6: punto unico de INSERT INTO evento con procedencia automatica.

    Devuelve el rowid del evento insertado. La procedencia (host/user/pid) se
    anade al final del detalle sin que el script llamante tenga que repetirlo.
    """
    detalle_completo = f"{detalle} [{procedencia()}]"
    cols = ["cuando", "actor", "accion", "detalle"]
    vals = [cuando, actor, accion, detalle_completo]
    if plan_id is not None:
        cols.append("plan_id")
        vals.append(plan_id)
    if nodo_id is not None:
        cols.append("nodo_id")
        vals.append(nodo_id)
    placeholders = ",".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO evento ({','.join(cols)}) VALUES ({placeholders})",
        vals,
    )
    return cur.lastrowid


_RE_BACKUP_DATE = re.compile(r"(\d{8})-(\d{4,6})")
_PROTEGIDOS = ("pre-compuerta", "pre-retro")


def rotar_backups(db_path: Path, dry_run: bool = True) -> dict:
    """Rotate backup files: keep first of each day + last 20 + protected.

    Default is --dry-run (report only). Pass dry_run=False to delete.
    Protected: filenames containing 'pre-compuerta' or 'pre-retro'.

        python3 barrera.py rotar --db ~/sypnose-f1/registry.db [--ejecutar]
    """
    backup_dir = db_path.parent
    backups = sorted(backup_dir.glob("registry-backup-*.db"))
    if not backups:
        print("[rotar] no hay backups")
        return {"kept": 0, "deleted": 0, "freed_mb": 0}

    protected = set()
    for b in backups:
        if any(p in b.name for p in _PROTEGIDOS):
            protected.add(b)

    last_20 = set(backups[-20:])

    by_day: dict[str, list[Path]] = {}
    for b in backups:
        m = _RE_BACKUP_DATE.search(b.name)
        if m:
            day = m.group(1)
            by_day.setdefault(day, []).append(b)
        else:
            protected.add(b)

    first_of_day = set()
    for day, files in by_day.items():
        first_of_day.add(files[0])

    keep = protected | last_20 | first_of_day
    to_delete = [b for b in backups if b not in keep]

    total_bytes = sum(b.stat().st_size for b in backups)
    delete_bytes = sum(b.stat().st_size for b in to_delete)
    keep_bytes = total_bytes - delete_bytes

    print(f"[rotar] {len(backups)} backups, {total_bytes / 1e9:.1f} GB total")
    print(f"  protegidos: {len(protected)}")
    print(f"  ultimos 20: {len(last_20)}")
    print(f"  primero de cada dia: {len(first_of_day)} ({len(by_day)} dias)")
    print(f"  a conservar: {len(keep)} ({keep_bytes / 1e9:.1f} GB)")
    print(f"  a eliminar: {len(to_delete)} ({delete_bytes / 1e9:.1f} GB)")

    if dry_run:
        print("\n  --dry-run (default): no se borra nada")
        if to_delete:
            print("  primeros 10 que se borrarian:")
            for b in to_delete[:10]:
                print(f"    {b.name} ({b.stat().st_size / 1e6:.0f} MB)")
    else:
        for b in to_delete:
            b.unlink()
        print(f"\n  [OK] {len(to_delete)} backups eliminados, {delete_bytes / 1e6:.0f} MB liberados")

    return {
        "kept": len(keep),
        "deleted": len(to_delete) if not dry_run else 0,
        "freed_mb": int(delete_bytes / 1e6) if not dry_run else 0,
        "would_free_mb": int(delete_bytes / 1e6),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="barrera.py — utilidades de integridad")
    sub = ap.add_subparsers(dest="cmd")
    rot = sub.add_parser("rotar", help="rotar backups (--dry-run por defecto)")
    rot.add_argument("--db", required=True, help="ruta a registry.db")
    rot.add_argument("--ejecutar", action="store_true",
                     help="borrar de verdad (sin esto solo reporta)")
    args = ap.parse_args()
    if args.cmd == "rotar":
        db_path = Path(args.db).expanduser().resolve()
        if not db_path.exists():
            sys.exit(f"[FALLO] {db_path} no existe")
        rotar_backups(db_path, dry_run=not args.ejecutar)
    else:
        ap.print_help()

