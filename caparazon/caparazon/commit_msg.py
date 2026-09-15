"""git commit-msg (B5): exige al pie Chat:, Model:, Plan: y Tarea:. Rechaza el commit y deja bloqueo:commit-msg en el registro."""
from __future__ import annotations

import re
import sys

import comun

CAMPOS = ("Chat", "Model", "Plan", "Tarea")


def main() -> None:
    cfg = comun.config()
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        lineas = [l for l in f.read().splitlines() if not l.startswith("#")]
    campos = {}
    for linea in lineas[1:]:
        m = re.match(r"^(Chat|Model|Plan|Tarea):[ \t]*(.*?)\s*$", linea)
        if m:
            campos[m.group(1)] = m.group(2)
    estado = comun.ultimo_estado() or {}
    plan_vigente = None if estado.get("abortado") else (estado.get("plan") or {}).get("id")
    tarea = estado.get("tarea") if plan_vigente else None
    fallos = [f"falta '{k}:' al pie" for k in CAMPOS if not campos.get(k)]
    if campos.get("Chat") and campos["Chat"] != cfg["carpeta"]:
        fallos.append(f"Chat: debe ser {cfg['carpeta']} (llegó '{campos['Chat']}')")
    if campos.get("Model") and not re.fullmatch(r"claude-[a-z0-9.-]+", campos["Model"]):
        fallos.append(f"Model: debe ser el id del modelo, p. ej. claude-sonnet-5 (llegó '{campos['Model']}')")
    if plan_vigente and campos.get("Plan") and campos["Plan"] != plan_vigente:
        fallos.append(f"Plan: debe ser el plan abierto {plan_vigente} (llegó '{campos['Plan']}')")
    if tarea and campos.get("Tarea") and campos["Tarea"] not in (str(tarea["id"]), f"{plan_vigente}/{tarea['req_ref']}"):
        fallos.append(f"Tarea: debe ser {tarea['id']} o {plan_vigente}/{tarea['req_ref']} (llegó '{campos['Tarea']}')")
    actor = estado.get("actor") or comun.actor_de(cfg, None)
    plan = comun.plan_de(estado, cfg)
    try:
        comun.salud(cfg)
    except comun.RegistroCaido as e:
        comun.guardar_pendientes(comun.ops_bloqueo(actor, "registro", plan, f"commit rechazado: registro caído ({e})"))
        sys.stderr.write(f"COMMIT RECHAZADO: REGISTRO SYPNOSE CAÍDO (FAIL LOUD). {e}\n")
        sys.exit(1)
    if not fallos:
        sys.exit(0)
    asunto = lineas[0][:120] if lineas else ""
    try:
        r = comun.emitir(cfg, comun.ops_bloqueo(actor, "commit-msg", plan, f"commit rechazado en {cfg['worktree']} ('{asunto}'): " + "; ".join(fallos)))
        nota = f"Registrado en SYPNOSE: evento {r['resultados'][0]['id']} bloqueo:commit-msg + evidencia."
    except (comun.RegistroCaido, comun.RegistroRechazo) as e:
        nota = f"(No registrado: {e}.)"
    sys.stderr.write("COMMIT RECHAZADO por el caparazón:\n - " + "\n - ".join(fallos)
                     + f"\nPie obligatorio:\n  Chat: {cfg['carpeta']}\n  Model: <modelo real>\n  Plan: {plan_vigente or '<plan abierto>'}\n"
                     + f"  Tarea: {tarea['id'] if tarea else '<id de tarea>'}\n{nota}\n")
    sys.exit(1)


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: (sys.stderr.write(f"COMMIT RECHAZADO: {m}\n"), sys.exit(1)))
