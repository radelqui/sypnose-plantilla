"""Fase 4: crea y abre PLAN-CS-M2 con requisitos y tareas.

    python3 fase4_abrir_m2.py --db ~/sypnose-f1/registry.db

Acciones en una transacción:
  1. INSERT plan PLAN-CS-M2 (estado=abierto, dueno=H:carlos)
  2. INSERT requisitos R0 y R1
  3. INSERT 4 tareas (R0 spec para 05, R1 para 01/02/05)
  4. Bloquear tareas R1 tras R0
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
PLAN_ID = "PLAN-CS-M2"

PLAN = {
    "id": PLAN_ID,
    "clase": "mantener",
    "que": "Esqueleto de microservicio reutilizable",
    "para": "Reutilizar CI/CD, Docker, K8s y seguridad sin código nuevo",
    "porque": "Fase 4 TRASPASO-5: probar que la plantilla genera un segundo microservicio sin tocar nada fuera del dominio",
    "afecta": "plantilla/microservicio/, instanciar_microservicio.py, segundo microservicio como-estoy-hecho",
    "estado": "abierto",
    "autor": ACTOR,
    "dueno": "H:carlos",
    "worktree": "C:/MICD/Coforge Santander/plantilla/wt-M2",
}

REQUISITOS = [
    {
        "ref": "R0",
        "ears": (
            "Cuando se ejecute python plantilla/microservicio/instanciar_microservicio.py demo-x "
            "--puerto 8010 en un directorio vacío, el sistema DEBERÁ dejar un repo en el que "
            "make test está en verde y docker build . termina bien, sin editar ningún fichero a mano."
        ),
        "comprobacion": (
            "cd /tmp && rm -rf demo-x && python plantilla/microservicio/instanciar_microservicio.py "
            "demo-x --puerto 8010 && cd demo-x && make test"
        ),
    },
    {
        "ref": "R1",
        "ears": (
            "Cuando se compare el microservicio generado con el esqueleto "
            "(git diff --stat <tag esqueleto>..HEAD -- . ':!app/<dominio>' ':!tests/<dominio>'), "
            "el resultado DEBERÁ ser vacío (0 ficheros fuera de la lógica de negocio)."
        ),
        "comprobacion": (
            "cd /tmp && rm -rf demo-x && python plantilla/microservicio/instanciar_microservicio.py "
            "demo-x --puerto 8010 && cd demo-x && make test && echo 'INSTANCIAR OK'"
        ),
    },
]

TAREAS = [
    {
        "ref": "R0",
        "titulo": "Spec M2: EARS R0-R1 con comprobación literal",
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
        "progreso": "pendiente",
    },
    {
        "ref": "R1",
        "titulo": "Extraer ci.yml, Dockerfile y k8s/ al esqueleto plantilla/microservicio/ con marca de origen",
        "agente": "IA:01-git-cicd:claude-sonnet-5",
        "progreso": "bloqueada",
    },
    {
        "ref": "R1",
        "titulo": "Extraer app/core, app/api/health, app/security y tests base al esqueleto; rag-banking-agent sigue en verde",
        "agente": "IA:02-backend-api:claude-sonnet-5",
        "progreso": "bloqueada",
    },
    {
        "ref": "R1",
        "titulo": "instanciar_microservicio.py genera repo con make test en verde",
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
        "progreso": "bloqueada",
    },
]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 4: abrir PLAN-CS-M2")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    verificar_repo_limpio()
    verificar_canonicos_registrados(conn)

    if conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        print(f"[INFO] {PLAN_ID} ya existe")
        row = conn.execute("SELECT estado, dueno, worktree FROM plan WHERE id=?", (PLAN_ID,)).fetchone()
        print(f"  estado={row[0]}, dueno={row[1]}, worktree={row[2]}")
        tareas = conn.execute("SELECT id, req_ref, titulo, progreso, agente FROM tarea WHERE plan_id=?", (PLAN_ID,)).fetchall()
        for t in tareas:
            print(f"  tarea {t[0]}: {t[1]} {t[3]} → {t[4]}")
        conn.close()
        return

    ts = ahora()
    print(f"[1/4] crear plan {PLAN_ID}")
    print(f"  clase={PLAN['clase']}, dueno={PLAN['dueno']}, worktree={PLAN['worktree']}")

    print(f"\n[2/4] requisitos")
    for r in REQUISITOS:
        print(f"  {r['ref']}: {r['ears'][:80]}...")

    print(f"\n[3/4] tareas")
    for i, t in enumerate(TAREAS):
        print(f"  ({i}): {t['ref']} {t['progreso']} → {t['agente']}: {t['titulo'][:60]}")

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    b = backup_registro(conn, db_path, "fase4-m2")
    print(f"\n[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (PLAN["id"], PLAN["clase"], PLAN["que"], PLAN["para"], PLAN["porque"],
             PLAN["afecta"], PLAN["estado"], PLAN["autor"], PLAN["dueno"], PLAN["worktree"], ts),
        )
        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_abierto", PLAN_ID,
             "Fase 4 TRASPASO-5: esqueleto de microservicio reutilizable; abierto por delegación"),
        )

        for r in REQUISITOS:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (PLAN_ID, r["ref"], r["ears"], r["comprobacion"]),
            )

        r0_id = None
        tarea_ids = []
        for t in TAREAS:
            cur = conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (PLAN_ID, t["ref"], t["titulo"], t["progreso"], t["agente"]),
            )
            tid = cur.lastrowid
            tarea_ids.append(tid)
            if t["ref"] == "R0":
                r0_id = tid
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ts, ACTOR, "tarea_creada", PLAN_ID,
                 f"tarea {tid}: {t['titulo']} (agente {t['agente']})"),
            )

        for tid in tarea_ids:
            row = conn.execute("SELECT progreso FROM tarea WHERE id=?", (tid,)).fetchone()
            if row and row[0] == "bloqueada" and r0_id:
                conn.execute("UPDATE tarea SET bloqueada_por=? WHERE id=?", (r0_id, tid))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\n[4/4] resultado")
    print(f"  plan {PLAN_ID} abierto")
    for i, tid in enumerate(tarea_ids):
        t = TAREAS[i]
        blq = f" (bloqueada por tarea {r0_id})" if t["progreso"] == "bloqueada" else ""
        print(f"  tarea {tid}: {t['ref']} {t['progreso']}{blq} → {t['agente']}")
    print(f"\n[OK] {PLAN_ID} con {len(tarea_ids)} tareas")


if __name__ == "__main__":
    main()
