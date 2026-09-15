"""TRASPASO-4 A3: calcula coste por sesión desde transcripts JSONL y lo escribe en tarea.coste.

Lee ficheros JSONL de transcripts de Claude Code, suma input+output tokens por sesión,
aplica precios de precios.yaml y actualiza tarea.coste en el registro.

Modos:
    # Resumen de un transcript (no escribe BD)
    python3 calcular_coste.py --transcript sesion.jsonl --resumen

    # Asignar coste a UNA tarea concreta
    python3 calcular_coste.py --db registry.db --transcript sesion.jsonl --plan PLAN-CS-T01 --req R1

    # Distribuir coste entre todas las tareas de un agente
    python3 calcular_coste.py --db registry.db --transcript sesion.jsonl --agente IA:02-backend-api

    # Recalcular plan.coste_real = suma(tarea.coste) para todos los planes
    python3 calcular_coste.py --db registry.db --actualizar-planes
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from barrera import PRECIOS_PATH, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup(conn: sqlite3.Connection, db_path: Path) -> Path:
    destino = db_path.with_name(f"registry-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}-coste.db")
    dst = sqlite3.connect(destino)
    with dst:
        conn.backup(dst)
    dst.close()
    return destino


def cargar_precios() -> dict:
    if not PRECIOS_PATH.exists():
        sys.exit(f"[FALLO] no encuentro {PRECIOS_PATH}")
    d = yaml.safe_load(PRECIOS_PATH.read_text(encoding="utf-8"))
    return d["modelos"]


def sumar_tokens(ruta_jsonl: Path) -> dict:
    totales: dict[str, dict] = {}
    with open(ruta_jsonl, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            if obj.get("type") != "assistant" or "message" not in obj:
                continue
            msg = obj["message"]
            modelo = msg.get("model", "desconocido")
            usage = msg.get("usage", {})
            if modelo not in totales:
                totales[modelo] = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "turnos": 0}
            t = totales[modelo]
            t["input"] += usage.get("input_tokens", 0)
            t["output"] += usage.get("output_tokens", 0)
            t["cache_write"] += usage.get("cache_creation_input_tokens", 0)
            t["cache_read"] += usage.get("cache_read_input_tokens", 0)
            t["turnos"] += 1
    return totales


def calcular_usd(totales: dict, precios: dict) -> float:
    coste = 0.0
    for modelo, t in totales.items():
        p = precios.get(modelo)
        if not p:
            for clave, val in precios.items():
                if modelo.startswith(clave.rsplit("-", 1)[0]):
                    p = val
                    break
        if not p:
            print(f"  ! modelo {modelo} sin precio, usando sonnet como fallback")
            p = precios.get("claude-sonnet-5", {"input": 3.0, "output": 15.0})
        input_total = t["input"] + t["cache_write"]
        cache_read = t["cache_read"]
        output_total = t["output"]
        coste += (input_total / 1_000_000) * p["input"]
        coste += (cache_read / 1_000_000) * p["input"] * 0.1
        coste += (output_total / 1_000_000) * p["output"]
    return coste


def imprimir_resumen(transcript: Path, totales: dict, coste_usd: float):
    print(f"[transcript] {transcript.name}")
    for modelo, t in sorted(totales.items()):
        print(f"  {modelo}: {t['turnos']} turnos · input={t['input']:,} · cache_w={t['cache_write']:,} · cache_r={t['cache_read']:,} · output={t['output']:,}")
    print(f"\n  COSTE TOTAL: ${coste_usd:.4f} USD")


def escribir_tarea(conn, plan_id, req_ref, coste_usd, transcript_name):
    tarea = conn.execute(
        "SELECT id, coste FROM tarea WHERE plan_id=? AND req_ref=?", (plan_id, req_ref)
    ).fetchone()
    if not tarea:
        return None
    tarea_id, coste_anterior = tarea
    conn.execute("UPDATE tarea SET coste=? WHERE id=?", (coste_usd, tarea_id))
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ahora(), ACTOR, "coste_actualizado", plan_id,
         f"tarea {tarea_id}: ${coste_anterior:.4f} → ${coste_usd:.4f} (transcript {transcript_name})"),
    )
    return tarea_id, coste_anterior


def actualizar_planes(conn):
    planes = conn.execute(
        "SELECT id, coste_real FROM plan WHERE id LIKE 'PLAN-CS-T%' ORDER BY id"
    ).fetchall()
    cambios = 0
    for plan_id, coste_anterior in planes:
        suma = conn.execute(
            "SELECT COALESCE(SUM(coste), 0) FROM tarea WHERE plan_id=?", (plan_id,)
        ).fetchone()[0]
        if abs(suma - coste_anterior) > 0.0001:
            conn.execute("UPDATE plan SET coste_real=? WHERE id=?", (suma, plan_id))
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
                (ahora(), ACTOR, "coste_real_actualizado", plan_id,
                 f"plan.coste_real: ${coste_anterior:.4f} → ${suma:.4f}"),
            )
            print(f"  {plan_id}: ${coste_anterior:.4f} → ${suma:.4f}")
            cambios += 1
        else:
            print(f"  {plan_id}: ${suma:.4f} (sin cambio)")
    return cambios


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", default=None, help="ruta al JSONL del transcript")
    ap.add_argument("--db", default=None, help="ruta a registry.db")
    ap.add_argument("--plan", default=None, help="plan_id de la tarea (ej. PLAN-CS-T01)")
    ap.add_argument("--req", default="R1", help="ref del requisito")
    ap.add_argument("--agente", default=None, help="prefijo del agente (ej. IA:02-backend-api)")
    ap.add_argument("--resumen", action="store_true", help="solo imprime resumen, no escribe BD")
    ap.add_argument("--actualizar-planes", action="store_true", help="recalcula plan.coste_real = suma(tarea.coste)")
    args = ap.parse_args()

    if not args.transcript and not args.actualizar_planes:
        sys.exit("[FALLO] necesitas --transcript o --actualizar-planes")

    if args.db and not args.resumen:
        verificar_repo_limpio()

    if args.actualizar_planes:
        if not args.db:
            sys.exit("[FALLO] --actualizar-planes necesita --db")
        db_path = Path(args.db).expanduser()
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        print("[actualizar-planes] recalculando plan.coste_real...")
        cambios = actualizar_planes(conn)
        conn.commit()
        conn.close()
        print(f"\n[OK] {cambios} planes actualizados")
        if not args.transcript:
            return

    precios = cargar_precios()
    transcript = Path(args.transcript)
    if not transcript.exists():
        sys.exit(f"[FALLO] no existe {transcript}")
    totales = sumar_tokens(transcript)

    if not totales:
        sys.exit("[FALLO] no se encontraron turnos de asistente en el transcript")

    coste_usd = calcular_usd(totales, precios)
    imprimir_resumen(transcript, totales, coste_usd)

    if args.resumen or not args.db:
        return

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    if args.agente:
        tareas = conn.execute(
            "SELECT id, plan_id, req_ref, agente FROM tarea WHERE agente LIKE ? AND plan_id LIKE 'PLAN-CS-T%'",
            (args.agente + "%",),
        ).fetchall()
        if not tareas:
            sys.exit(f"[FALLO] no hay tareas para agente {args.agente}*")
        coste_por_tarea = coste_usd / len(tareas)
        print(f"\n[distribuir] ${coste_usd:.4f} ÷ {len(tareas)} tareas = ${coste_por_tarea:.4f} cada una")
        for tid, pid, rref, ag in tareas:
            resultado = escribir_tarea(conn, pid, rref, coste_por_tarea, transcript.name)
            if resultado:
                print(f"  [OK] tarea {resultado[0]} ({pid}/{rref}): ${resultado[1]:.4f} → ${coste_por_tarea:.4f}")
        conn.commit()
        conn.close()
        print(f"\n[OK] {len(tareas)} tareas actualizadas para {args.agente}")

    elif args.plan:
        resultado = escribir_tarea(conn, args.plan, args.req, coste_usd, transcript.name)
        if not resultado:
            sys.exit(f"[FALLO] no existe tarea para {args.plan}/{args.req}")
        conn.commit()
        conn.close()
        print(f"[OK] tarea {resultado[0]} ({args.plan}/{args.req}): coste actualizado a ${coste_usd:.4f}")

    else:
        sys.exit("[FALLO] necesitas --plan o --agente para escribir en BD")


if __name__ == "__main__":
    main()
