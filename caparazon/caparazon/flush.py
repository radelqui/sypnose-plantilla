"""Envía la cola local del caparazón al registro SYPNOSE y a la KB.
Hook async de PostToolUse: `flush.py --si-toca 60` (solo si pasaron 60 s desde el último intento de esa sesión).
A mano: `flush.py --todas` o `flush.py --sesion <session_id>`."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import comun


def segundos_desde(iso: str | None) -> float:
    if not iso:
        return float("inf")
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--si-toca", type=float, default=None)
    ap.add_argument("--sesion")
    ap.add_argument("--todas", action="store_true")
    args = ap.parse_args()
    cfg = comun.config()
    if args.todas:
        print(json.dumps(comun.vaciar_todas(cfg, "manual"), ensure_ascii=False))
        return
    sid = args.sesion or (comun.leer_stdin().get("session_id") if not sys.stdin.isatty() else None) or "sin-sesion"
    if args.si_toca is None:
        print(json.dumps(comun.vaciar(cfg, sid, "manual"), ensure_ascii=False))
    elif segundos_desde(comun.estado_cola(sid).get("ultimo_intento")) >= args.si_toca:
        comun.vaciar(cfg, sid, "periodico")


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: (sys.stderr.write(m + "\n"), sys.exit(1)))
