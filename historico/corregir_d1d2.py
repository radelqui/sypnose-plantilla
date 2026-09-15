"""Decisiones D1 + D2 del lead (15-sep-2026).

D1: Un solo juego de planes por línea:
    - PLAN-T-01..12 → rechazado (duplicado de PLAN-CS-Txx)
    - plan_linea afirmaciones → de PLAN-T-* a PLAN-CS-T*
    - microservicio-2 → colección retirada, PLAN-M2-T* → rechazado

D2: R0 bootstrap por plan PLAN-CS-T (donde falte):
    - requisito R0 con EARS de arranque
    - tarea R0 "Definir requisito y comprobación de la línea"

    python3 corregir_d1d2.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "historico" else Path(__file__).resolve().parent))
from barrera import verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-5"
FUENTE = "plantilla/corregir_d1d2.py"
SOL_ID = "sol:coforge:rag-banking-agent"

PLAN_T_TO_CS = {
    "PLAN-T-01": ("PLAN-CS-T01", "T01"),
    "PLAN-T-02": ("PLAN-CS-T02", "T02"),
    "PLAN-T-03": ("PLAN-CS-T03", "T03"),
    "PLAN-T-04": ("PLAN-CS-T04", "T04"),
    "PLAN-T-05": ("PLAN-CS-T05", "T05"),
    "PLAN-T-06": ("PLAN-CS-T06", "T06"),
    "PLAN-T-07": ("PLAN-CS-T07", "T07"),
    "PLAN-T-08": ("PLAN-CS-T08", "T08"),
    "PLAN-T-09": ("PLAN-CS-T09", "T09"),
    "PLAN-T-10": ("PLAN-CS-T10", "T10"),
    "PLAN-T-11": ("PLAN-CS-T11", "T13"),
    "PLAN-T-12": ("PLAN-CS-T12", "T12"),
}

LINEA_TO_PLAN_CS = {linea: cs for _, (cs, linea) in PLAN_T_TO_CS.items()}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-d1d2.db")
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    ya = conn.execute("SELECT 1 FROM evento WHERE actor=? AND accion='plan_rechazado' AND plan_id='PLAN-T-01' LIMIT 1", (ACTOR,)).fetchone()
    if ya:
        sys.exit("[INFO] corregir_d1d2 ya fue aplicado (evento plan_rechazado PLAN-T-01 existe). Nada que hacer.")

    if not args.dry_run:
        b = backup(conn, db_path)
        print(f"[backup] {b}")

    conn.execute("BEGIN IMMEDIATE")
    cambios = []

    try:
        # ─── D1a: rechazar PLAN-T-01..12 ───
        print("[D1a] Rechazando PLAN-T-01..12...")
        for plan_t, (plan_cs, _) in PLAN_T_TO_CS.items():
            rc = conn.execute(
                "UPDATE plan SET estado='rechazado', motivo_rechazo=? WHERE id=? AND estado!='rechazado'",
                (f"duplicado de {plan_cs}; el molde ya no lleva planes", plan_t),
            ).rowcount
            if rc:
                evento(conn, ACTOR, "plan_rechazado",
                       f"{plan_t} rechazado: duplicado de {plan_cs}", plan_id=plan_t)
                cambios.append(f"rechazado {plan_t} (duplicado de {plan_cs})")

        # ─── D1b: mover plan_linea de PLAN-T a PLAN-CS-T ───
        print("[D1b] Moviendo plan_linea a PLAN-CS-T...")
        old_pl = conn.execute(
            "SELECT id, campo, valor FROM afirmacion WHERE nodo_id=? AND campo LIKE 'plan_linea:%' AND vigente=1",
            (SOL_ID,),
        ).fetchall()
        for aid, campo, valor_old in old_pl:
            linea = campo.split(":")[1]
            nuevo_plan = LINEA_TO_PLAN_CS.get(linea)
            if not nuevo_plan:
                continue
            if valor_old == nuevo_plan:
                continue
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (aid,))
            conn.execute(
                "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) VALUES (?,?,?,?,?,?,?)",
                (SOL_ID, campo, nuevo_plan, "observado", FUENTE, ACTOR, ahora()),
            )
            cambios.append(f"{campo}: {valor_old} → {nuevo_plan}")
        if old_pl:
            evento(conn, ACTOR, "plan_linea_redirigida",
                   f"plan_linea de PLAN-T → PLAN-CS-T ({len(old_pl)} afirmaciones)", nodo_id=SOL_ID)

        # ─── D1c: retirar microservicio-2 ───
        print("[D1c] Retirando microservicio-2...")
        rc = conn.execute(
            "UPDATE coleccion SET estado='retirada' WHERE id='microservicio-2' AND estado='activa'"
        ).rowcount
        if rc:
            evento(conn, ACTOR, "coleccion_retirada",
                   "microservicio-2 retirada: prueba del molde v1")
            cambios.append("coleccion microservicio-2 → retirada")

        m2_planes = conn.execute(
            "SELECT id FROM plan WHERE id LIKE 'PLAN-M2-%' AND estado!='rechazado'"
        ).fetchall()
        for (pid,) in m2_planes:
            conn.execute(
                "UPDATE plan SET estado='rechazado', motivo_rechazo='prueba del molde v1' WHERE id=?",
                (pid,),
            )
            evento(conn, ACTOR, "plan_rechazado",
                   f"{pid} rechazado: prueba del molde v1", plan_id=pid)
            cambios.append(f"rechazado {pid}")

        # ─── D2: R0 bootstrap por plan PLAN-CS-T ───
        print("[D2] Añadiendo R0 bootstrap a PLAN-CS-T...")
        cs_planes = conn.execute(
            "SELECT id FROM plan WHERE id LIKE 'PLAN-CS-T%' ORDER BY id"
        ).fetchall()
        for (pid,) in cs_planes:
            ya = conn.execute(
                "SELECT 1 FROM requisito WHERE plan_id=? AND ref='R0'", (pid,)
            ).fetchone()
            if ya:
                continue

            agente_row = conn.execute(
                "SELECT agente FROM tarea WHERE plan_id=? AND req_ref='R1'", (pid,)
            ).fetchone()
            agente = agente_row[0] if agente_row else "IA:02-backend-api:claude-sonnet-5"
            rol = agente.split(":")[1] if ":" in agente else "desconocido"

            ears = (f"Antes de escribir código para esta línea, el rol {rol} "
                    f"DEBE registrar el requisito comprobable de su solución (R1+) "
                    f"con su comprobación ejecutable")
            comprobacion = f"SELECT COUNT(*) FROM requisito WHERE plan_id='{pid}' AND ref<>'R0' → ≥1"

            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (pid, "R0", ears, comprobacion),
            )
            conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) VALUES (?,?,?,?,?)",
                (pid, "R0", "Definir requisito y comprobación de la línea", "pendiente", agente),
            )
            evento(conn, ACTOR, "r0_bootstrap_creado",
                   f"R0 + tarea para {pid} (agente {agente})", plan_id=pid)
            cambios.append(f"R0 + tarea en {pid}")

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

    # Verificación
    print("\n[verificación]")
    r = conn.execute("SELECT COUNT(*) FROM plan WHERE id LIKE 'PLAN-T-%' AND estado='rechazado'").fetchone()[0]
    print(f"  PLAN-T rechazados: {r}/12")
    r = conn.execute(
        "SELECT campo, valor FROM afirmacion WHERE nodo_id=? AND campo LIKE 'plan_linea:%' AND vigente=1 ORDER BY campo",
        (SOL_ID,),
    ).fetchall()
    print(f"  plan_linea vigentes en sol ({len(r)}):")
    for campo, valor in r:
        print(f"    {campo} → {valor}")
    r = conn.execute("SELECT estado FROM coleccion WHERE id='microservicio-2'").fetchone()
    print(f"  microservicio-2 estado: {r[0] if r else 'N/A'}")
    r = conn.execute("SELECT COUNT(*) FROM plan WHERE id LIKE 'PLAN-M2-%' AND estado='rechazado'").fetchone()[0]
    print(f"  PLAN-M2 rechazados: {r}/12")
    r = conn.execute("SELECT COUNT(*) FROM requisito WHERE plan_id LIKE 'PLAN-CS-T%' AND ref='R0'").fetchone()[0]
    print(f"  R0 en PLAN-CS-T: {r}/12")
    r = conn.execute("SELECT COUNT(*) FROM tarea WHERE plan_id LIKE 'PLAN-CS-T%' AND req_ref='R0'").fetchone()[0]
    print(f"  tareas R0 en PLAN-CS-T: {r}/12")

    conn.close()


if __name__ == "__main__":
    main()
