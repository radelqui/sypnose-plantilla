"""UserPromptSubmit (B2): antepone la EARS literal de la tarea en cada turno. Solo consulta el registro si la sesión está ABORTADA."""
from __future__ import annotations

import brief
import comun


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    estado = comun.asegurar_estado(entrada, cfg)
    notas = []
    if estado.get("abortado"):
        estado = brief.construir_estado(entrada, cfg)
    else:
        # B12 (lead, 15-sep): el requisito, la tarea y los permitidos vigentes salen del registro en cada prompt. La foto del estado solo
        # sirve de respaldo para seguir conversando con el registro caído.
        try:
            estado, notas = brief.refrescar_trabajo(estado, entrada, cfg, cambiar_si_entregada=True)
        except comun.RegistroCaido as e:
            notas = [f"no se pudo confirmar el requisito vigente: registro caído ({e}); se muestra el guardado "
                     f"({estado.get('requisito_confirmado') or estado.get('creado')})"]
    if comun.tipo_aborto(estado) == "registro_caido":
        comun.bloquear(f"CAPARAZÓN ABORTADO: túnel 7101 caído. Remedio: `{comun.comando_tunel(cfg)}`\n{estado['motivo']}")
    if comun.tipo_aborto(estado) == "sin_tarea":
        # B10 (lead, 15-sep): un humano nunca se queda sin poder hablar con su chat; el prompt pasa con el aviso.
        aviso = "\n".join([comun.aviso_sin_tarea(estado, cfg), *notas])
        comun.salir_json({"systemMessage": aviso, "hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                                         "additionalContext": f"{aviso}\nDetalle: {estado['motivo']}"}})
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
    listado = brief.listado_tareas(estado.get("tareas_trabajables") or [])
    if listado:
        contexto = f"{contexto}\n{listado}"
    if notas:
        contexto = f"Cambios del caparazón: {' · '.join(notas)}\n{contexto}"
    if not estado.get("brief_entregado"):
        # Sesión sin SessionStart (abierta antes de instalar el caparazón): el brief completo llega con el primer prompt, una sola vez.
        contexto = f"{estado['brief']}\n\n{contexto}"
        comun.actualizar_estado(sid, lambda e: e.update(brief_entregado=comun.ahora(), brief_via="UserPromptSubmit"))
    salida = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": contexto}}
    aviso = "\n".join(x for x in (" · ".join(notas), comun.aviso_cola(cfg, sid)) if x)
    if aviso:
        salida["systemMessage"] = aviso
    comun.salir_json(salida)


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
