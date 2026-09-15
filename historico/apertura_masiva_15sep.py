"""Apertura masiva de planes 15-sep-2026 por orden del lead.

Abre planes T02,T03,T05,T07(ya),T08,T10,T12,T13,T14,T15 con worktrees,
reasigna agentes de tareas a los chats correctos y bloquea R1 tras R0.

Guardia idempotente: evento 'apertura_masiva_15sep'.

    python3 historico/apertura_masiva_15sep.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
EVENTO_GUARDIA = "apertura_masiva_15sep"

PLANES = [
    # (plan_id, worktree, chat_prefix)
    ("PLAN-CS-T02", "C:/MICD/Coforge Santander/04-agentes/wt", "IA:04-agentes:"),
    ("PLAN-CS-T03", "C:/MICD/Coforge Santander/02-backend-api/wt-T03", "IA:02-backend-api:"),
    ("PLAN-CS-T05", "C:/MICD/Coforge Santander/02-backend-api/wt-T05", "IA:02-backend-api:"),
    ("PLAN-CS-T08", "C:/MICD/Coforge Santander/03-datos-rag/wt", "IA:03-datos-rag:"),
    ("PLAN-CS-T10", "C:/MICD/Coforge Santander/02-backend-api/wt-T10", "IA:02-backend-api:"),
    ("PLAN-CS-T12", "C:/MICD/Coforge Santander/04-agentes/wt-T12", "IA:04-agentes:"),
    ("PLAN-CS-T13", "C:/MICD/Coforge Santander/01-git-cicd/wt-T13", "IA:01-git-cicd:"),
    ("PLAN-CS-T14", "C:/MICD/Coforge Santander/01-git-cicd/wt-T14", "IA:01-git-cicd:"),
    ("PLAN-CS-T15", "C:/MICD/Coforge Santander/02-backend-api/wt-T15", "IA:02-backend-api:"),
]

AGENT_MAP = {
    "IA:02-backend-api:": "IA:02-backend-api:claude-sonnet-5",
    "IA:01-git-cicd:": "IA:01-git-cicd:claude-sonnet-5",
    "IA:03-datos-rag:": "IA:03-datos-rag:claude-sonnet-5",
    "IA:04-agentes:": "IA:04-agentes:claude-sonnet-5",
}

DETALLE = "abierto por 05-arquitecto por orden del lead, delegación de Carlos (POC, 15-sep)"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    ya = conn.execute("SELECT 1 FROM evento WHERE accion=?", (EVENTO_GUARDIA,)).fetchone()
    if ya:
        print(f"[idempotente] evento {EVENTO_GUARDIA} ya existe. 0 cambios.")
        conn.close()
        return

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    planes_abiertos = []
    agentes_reasignados = []
    tareas_bloqueadas = []

    for plan_id, worktree, chat_prefix in PLANES:
        row = conn.execute(
            "SELECT estado, worktree FROM plan WHERE id=?", (plan_id,),
        ).fetchone()
        if not row:
            print(f"[SKIP] {plan_id} no existe")
            continue
        estado, wt_actual = row
        if estado == "abierto":
            print(f"[SKIP] {plan_id} ya abierto (wt={wt_actual})")
            continue
        if estado != "propuesto":
            print(f"[SKIP] {plan_id} estado={estado}")
            continue
        planes_abiertos.append((plan_id, worktree))

        target_agent = AGENT_MAP.get(chat_prefix)
        if not target_agent:
            print(f"[WARN] no agent mapping for {chat_prefix}")
            continue

        tareas = conn.execute(
            "SELECT id, req_ref, agente, progreso FROM tarea WHERE plan_id=? ORDER BY req_ref",
            (plan_id,),
        ).fetchall()

        r0_id = None
        for tid, ref, agente, progreso in tareas:
            if not agente.startswith(chat_prefix):
                agentes_reasignados.append((tid, plan_id, ref, agente, target_agent))
            if ref == "R0":
                r0_id = tid
            elif ref != "R0" and r0_id and progreso == "pendiente":
                tareas_bloqueadas.append((tid, plan_id, ref, r0_id))

    print(f"\n[resumen] {len(planes_abiertos)} planes a abrir, {len(agentes_reasignados)} agentes a reasignar, {len(tareas_bloqueadas)} tareas a bloquear\n")

    for p, w in planes_abiertos:
        print(f"  [abrir] {p} → {w}")
    for tid, pid, ref, old, new in agentes_reasignados:
        print(f"  [reasignar] tarea {tid} ({pid}/{ref}): {old} → {new}")
    for tid, pid, ref, r0 in tareas_bloqueadas:
        print(f"  [bloquear] tarea {tid} ({pid}/{ref}) detrás de {r0}")

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "apertura-masiva")
    print(f"[backup] {b}")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for plan_id, worktree in planes_abiertos:
            conn.execute(
                "UPDATE plan SET estado='abierto', dueno='H:carlos', worktree=?, abierto_en=? WHERE id=?",
                (worktree, ts, plan_id),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "plan_abierto", plan_id, DETALLE),
            )
            print(f"  [OK] {plan_id} abierto")

        for tid, pid, ref, old_agent, new_agent in agentes_reasignados:
            conn.execute("UPDATE tarea SET agente=? WHERE id=?", (new_agent, tid))
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "tarea_reasignada", pid,
                 f"tarea {tid} ({ref}): agente {old_agent} → {new_agent} (reasignación por chat)"),
            )
            print(f"  [OK] tarea {tid} → {new_agent}")

        for tid, pid, ref, r0_id in tareas_bloqueadas:
            conn.execute(
                "UPDATE tarea SET progreso='bloqueada', bloqueada_por=? WHERE id=?",
                (r0_id, tid),
            )
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "tarea_bloqueada", pid,
                 f"tarea {tid} ({ref}) bloqueada por tarea {r0_id} (R0)"),
            )
            print(f"  [OK] tarea {tid} bloqueada por {r0_id}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, detalle) VALUES (?,?,?,?)",
            (ts, ACTOR, EVENTO_GUARDIA,
             f"{len(planes_abiertos)} planes abiertos, {len(agentes_reasignados)} agentes reasignados, "
             f"{len(tareas_bloqueadas)} tareas bloqueadas"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\n[OK] apertura masiva: {len(planes_abiertos)} planes, {len(agentes_reasignados)} reasignaciones, {len(tareas_bloqueadas)} bloqueos")


if __name__ == "__main__":
    main()
