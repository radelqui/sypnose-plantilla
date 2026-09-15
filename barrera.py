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


def verificar_oferta_canonica(conn, h: str) -> None:
    verificar_canonicos_registrados(conn)
