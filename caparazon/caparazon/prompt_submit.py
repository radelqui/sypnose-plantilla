"""UserPromptSubmit (B2): antepone la EARS literal de la tarea en cada turno. Solo consulta el registro si la sesión está ABORTADA."""
from __future__ import annotations

import brief
import comun


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    estado = comun.asegurar_estado(entrada, cfg)
    if estado.get("abortado"):
        estado = brief.construir_estado(entrada, cfg)
    if estado.get("abortado"):
        comun.bloquear(f"CAPARAZÓN ABORTADO: prompt bloqueado.\n{estado['motivo']}")
    sid = estado["session_id"]
    if estado.get("modelo") in (None, "desconocido"):
        observado = comun.modelo_en_transcript(entrada.get("transcript_path"))
        if observado:
            estado = comun.actualizar_estado(sid, lambda e: e.update(modelo=observado, modelo_fuente="transcript",
                                                                     actor=comun.actor_de(cfg, observado)))
            comun.encolar(sid, [{"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": observado},
                                comun.op_evento(estado["actor"], "modelo_observado", f"modelo real {observado} leído del transcript",
                                                estado["plan"]["id"])])
    p, t, r = estado["plan"], estado["tarea"], estado["requisito"]
    contexto = (f"Requisito vigente de la tarea {t['id']} ({p['id']}/{r['ref']}), texto literal del registro SYPNOSE: {r['ears']}\n"
                f"Comprobación: {r['comprobacion']}\n"
                f"Archivos permitidos dentro de {estado['worktree']}: {', '.join(estado['permitidos'])}")
    if not estado.get("brief_entregado"):
        # Sesión sin SessionStart (abierta antes de instalar el caparazón): el brief completo llega con el primer prompt, una sola vez.
        contexto = f"{estado['brief']}\n\n{contexto}"
        comun.actualizar_estado(sid, lambda e: e.update(brief_entregado=comun.ahora(), brief_via="UserPromptSubmit"))
    salida = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": contexto}}
    aviso = comun.aviso_cola(cfg, sid)
    if aviso:
        salida["systemMessage"] = aviso
    comun.salir_json(salida)


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
