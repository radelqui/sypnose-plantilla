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
    if estado.get("modelo") in (None, "desconocido"):
        observado = comun.modelo_en_transcript(entrada.get("transcript_path"))
        if observado:
            def cambio(e: dict) -> None:
                e.update(modelo=observado, modelo_fuente="transcript", actor=comun.actor_de(cfg, observado))

            estado = comun.actualizar_estado(estado["session_id"], cambio)
            try:
                comun.emitir(cfg, [{"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": observado},
                                   comun.op_evento(estado["actor"], "modelo_observado", f"modelo real {observado} leído del transcript",
                                                   estado["plan"]["id"])])
            except (comun.RegistroCaido, comun.RegistroRechazo) as e:
                comun.bloquear(f"REGISTRO SYPNOSE: no se pudo registrar el modelo real ({e}); prompt bloqueado (FAIL LOUD).")
    p, t, r = estado["plan"], estado["tarea"], estado["requisito"]
    contexto = (f"Requisito vigente de la tarea {t['id']} ({p['id']}/{r['ref']}), texto literal del registro SYPNOSE: {r['ears']}\n"
                f"Comprobación: {r['comprobacion']}\n"
                f"Archivos permitidos dentro de {estado['worktree']}: {', '.join(estado['permitidos'])}")
    comun.salir_json({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": contexto}})


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
