"""Registra afirmaciones transcript sobre cada plan cerrado.

Para cada plan cerrado, encuentra el chat dueño (agente de la tarea) y
enlaza al fichero transcripts/<chat>/<sesion>.md commiteado en plantilla.

    python3 cargar_transcripts.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import PLANTILLA_DIR, backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
TRANSCRIPTS_DIR = PLANTILLA_DIR / "transcripts"

PLAN_TO_NODO = {
    "PLAN-CS-M2": "sol:coforge:rag-banking-agent",
    "PLAN-CS2-M": "sol:coforge:como-estoy-hecho",
}

AGENT_TO_CHAT = {
    "01-git-cicd": "01-git-cicd",
    "02-backend-api": "02-backend-api",
    "03-datos-rag": "03-datos-rag",
    "04-agentes": "04-agentes",
    "05-arquitecto-sypnose": "05-arquitecto-sypnose",
    "07-verificador": "07-verificador",
    "08-caparazon": "08-caparazon",
    "09-sypnose-vista": "09-sypnose-vista",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def extract_chat(agente: str) -> str | None:
    for prefix, chat in AGENT_TO_CHAT.items():
        if f":{prefix}:" in agente or agente.endswith(f":{prefix}"):
            return chat
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    if not TRANSCRIPTS_DIR.exists():
        sys.exit(f"[FALLO] directorio transcripts no existe: {TRANSCRIPTS_DIR}")

    chat_files: dict[str, list[str]] = {}
    for chat_dir in sorted(TRANSCRIPTS_DIR.iterdir()):
        if chat_dir.is_dir():
            files = sorted(f.name for f in chat_dir.glob("*.md"))
            if files:
                chat_files[chat_dir.name] = files

    print(f"[transcripts] {len(chat_files)} chats con ficheros:")
    for chat, files in chat_files.items():
        print(f"  {chat}: {len(files)} sesiones")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    closed_plans = [
        r[0] for r in conn.execute(
            "SELECT id FROM plan WHERE estado='cerrado' AND id LIKE 'PLAN-CS%' ORDER BY id"
        ).fetchall()
    ]
    print(f"\n[planes cerrados] {len(closed_plans)}: {', '.join(closed_plans)}")

    plan_chats: dict[str, set[str]] = {}
    for plan_id in closed_plans:
        agents = conn.execute(
            "SELECT DISTINCT agente FROM tarea WHERE plan_id=? AND agente IS NOT NULL",
            (plan_id,),
        ).fetchall()
        chats = set()
        for (agente,) in agents:
            chat = extract_chat(agente)
            if chat and chat in chat_files:
                chats.add(chat)
        plan_chats[plan_id] = chats

    if not args.dry_run:
        backup_registro(conn, db_path, "transcripts")

    altas = []
    existian = []

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        for plan_id in closed_plans:
            import re
            m = re.match(r"PLAN-CS-T(\d+)", plan_id)
            if m:
                nodo_id = f"linea:coforge:T{m.group(1).lstrip('0') or '0'}"
            else:
                nodo_id = PLAN_TO_NODO.get(plan_id)
            if not nodo_id:
                print(f"  [skip] {plan_id}: sin nodo mapeado")
                continue
            if not conn.execute("SELECT 1 FROM nodo WHERE id=?", (nodo_id,)).fetchone():
                print(f"  [skip] {plan_id}: nodo {nodo_id} no existe")
                continue

            chats = plan_chats.get(plan_id, set())
            if not chats:
                print(f"  [skip] {plan_id}: sin chat con transcript")
                continue
            for chat in sorted(chats):
                for fname in chat_files[chat]:
                    ruta = f"transcripts/{chat}/{fname}"
                    existing = conn.execute(
                        "SELECT 1 FROM afirmacion WHERE nodo_id=? AND campo=? AND valor=?",
                        (nodo_id, f"transcript:{plan_id}", ruta),
                    ).fetchone()
                    if existing:
                        existian.append(f"{nodo_id} ({plan_id}): {ruta}")
                        continue
                    conn.execute(
                        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
                        "VALUES (?, ?, ?, 'observado', ?, ?, ?)",
                        (nodo_id, f"transcript:{plan_id}", ruta, "plantilla/cargar_transcripts.py", ACTOR, ts),
                    )
                    altas.append(f"{nodo_id} ({plan_id}): {ruta}")

        if altas:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'transcript_cargado', NULL, NULL, ?)",
                (ts, ACTOR, f"{len(altas)} afirmaciones transcript sobre {len(closed_plans)} planes cerrados"),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\naltas: {len(altas)} · ya existían: {len(existian)}")
    for a in altas:
        print(f"  + {a}")
    if args.dry_run:
        print("\n--dry-run: transacción deshecha")

    conn.close()


if __name__ == "__main__":
    main()
