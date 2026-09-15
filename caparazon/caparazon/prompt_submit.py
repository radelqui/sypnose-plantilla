"""UserPromptSubmit (B2): antepone la EARS literal de la tarea en cada turno. Bloquea el prompt si el registro cae o la sesión está abortada."""
from __future__ import annotations

import brief
import comun


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    try:
        comun.salud(cfg)
    except comun.RegistroCaido as e:
        previo = comun.leer_estado(entrada.get("session_id") or "") or {}
        comun.guardar_pendientes(comun.ops_bloqueo(previo.get("actor") or comun.actor_de(cfg, None), "registro",
                                                   comun.plan_de(previo, cfg), f"prompt bloqueado: registro caído ({e})"))
        comun.bloquear(f"REGISTRO SYPNOSE CAÍDO: prompt bloqueado (FAIL LOUD).\n{e}\nTúnel: {comun.comando_tunel(cfg)}")
    estado = comun.asegurar_estado(entrada, cfg)
    if estado.get("abortado"):
        estado = brief.construir_estado(entrada, cfg)
    if estado.get("abortado"):
        comun.bloquear(f"CAPARAZÓN ABORTADO: prompt bloqueado.\n{estado['motivo']}")
    p, t, r = estado["plan"], estado["tarea"], estado["requisito"]
    contexto = (f"Requisito vigente de la tarea {t['id']} ({p['id']}/{r['ref']}), texto literal del registro SYPNOSE: {r['ears']}\n"
                f"Comprobación: {r['comprobacion']}\n"
                f"Archivos permitidos dentro de {estado['worktree']}: {', '.join(estado['permitidos'])}")
    comun.salir_json({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": contexto}})


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
