"""TRASPASO-4 A3: calcula coste por sesión desde transcripts JSONL y lo escribe en tarea.coste.

Lee ficheros JSONL de transcripts de Claude Code, suma input+output tokens por sesión,
aplica precios de precios.yaml y actualiza tarea.coste en el registro.

    python3 calcular_coste.py --db ~/sypnose-f1/registry.db --transcript sesion.jsonl --plan PLAN-CS-T01 --req R1
    python3 calcular_coste.py --transcript sesion.jsonl --resumen   # solo imprime, no escribe BD
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def cargar_precios(ruta: Path) -> dict:
    d = yaml.safe_load(ruta.read_text(encoding="utf-8"))
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True, help="ruta al JSONL del transcript")
    ap.add_argument("--precios", default=None, help="ruta a precios.yaml (default: mismo directorio)")
    ap.add_argument("--db", default=None, help="ruta a registry.db (omitir para solo resumen)")
    ap.add_argument("--plan", default=None, help="plan_id de la tarea (ej. PLAN-CS-T01)")
    ap.add_argument("--req", default="R1", help="ref del requisito")
    ap.add_argument("--resumen", action="store_true", help="solo imprime resumen, no escribe BD")
    args = ap.parse_args()

    transcript = Path(args.transcript)
    precios_path = Path(args.precios) if args.precios else transcript.parent / "precios.yaml"
    if not precios_path.exists():
        precios_path = Path(__file__).parent / "precios.yaml"
    if not precios_path.exists():
        sys.exit(f"[FALLO] no encuentro precios.yaml en {precios_path}")

    precios = cargar_precios(precios_path)
    totales = sumar_tokens(transcript)

    if not totales:
        sys.exit("[FALLO] no se encontraron turnos de asistente en el transcript")

    print(f"[transcript] {transcript.name}")
    for modelo, t in sorted(totales.items()):
        print(f"  {modelo}: {t['turnos']} turnos · input={t['input']:,} · cache_w={t['cache_write']:,} · cache_r={t['cache_read']:,} · output={t['output']:,}")

    coste_usd = calcular_usd(totales, precios)
    print(f"\n  COSTE TOTAL: ${coste_usd:.4f} USD")

    if args.resumen or not args.db or not args.plan:
        return

    import sqlite3
    from datetime import datetime, timezone
    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    tarea = conn.execute(
        "SELECT id, coste FROM tarea WHERE plan_id=? AND req_ref=?", (args.plan, args.req)
    ).fetchone()
    if not tarea:
        sys.exit(f"[FALLO] no existe tarea para {args.plan}/{args.req}")

    tarea_id, coste_anterior = tarea
    conn.execute("UPDATE tarea SET coste=? WHERE id=?", (coste_usd, tarea_id))
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
        (ts, "IA:05-arquitecto-sypnose:claude-opus-5", "coste_actualizado", args.plan,
         f"tarea {tarea_id}: ${coste_anterior:.4f} → ${coste_usd:.4f} (transcript {transcript.name})"),
    )
    conn.commit()
    conn.close()
    print(f"[OK] tarea {tarea_id} ({args.plan}/{args.req}): coste actualizado a ${coste_usd:.4f}")


if __name__ == "__main__":
    main()
