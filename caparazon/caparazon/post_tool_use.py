"""PostToolUse (B4): evento en vivo al registro por cada herramienta (ruta, hora, tokens y coste del turno) + auditoría git del cerco.
Si el registro no responde, la sesión se para (continue:false)."""
from __future__ import annotations

import json
import re

import cerco
import comun

MAX_SALIDA = 20000
ESCRITURAS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def ruta_de(datos: dict) -> str:
    for clave in ("file_path", "notebook_path", "path", "url", "pattern"):
        if datos.get(clave):
            return str(datos[clave])
    return str(datos.get("command", ""))[:160]


def salida_de(respuesta) -> tuple[str, bool]:
    if isinstance(respuesta, dict):
        partes = [str(respuesta.get(k) or "") for k in ("stdout", "stderr", "output")]
        return "\n".join(p for p in partes if p), bool(respuesta.get("interrupted"))
    return str(respuesta or ""), False


def parar(mensaje: str) -> None:
    comun.salir_json({"continue": False, "stopReason": mensaje})


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    sid = entrada.get("session_id") or "sin-sesion"
    herramienta = entrada.get("tool_name", "?")
    datos = entrada.get("tool_input") or {}
    try:
        comun.salud(cfg)
    except comun.RegistroCaido as e:
        previo = comun.leer_estado(sid) or {}
        comun.guardar_pendientes(comun.ops_bloqueo(previo.get("actor") or comun.actor_de(cfg, None), "registro",
                                                   comun.plan_de(previo, cfg), f"sesión {sid[:8]} parada tras {herramienta}: registro caído ({e})"))
        parar(f"REGISTRO SYPNOSE CAÍDO: sesión parada tras {herramienta} (FAIL LOUD). {e}. Túnel: {comun.comando_tunel(cfg)}")
    previo = comun.asegurar_estado(entrada, cfg)
    uso = comun.uso_turno(entrada.get("transcript_path"))
    cuando = comun.ahora()
    modelo_nuevo = None
    if previo.get("modelo") in (None, "desconocido"):
        modelo_nuevo = uso["modelo"] or comun.modelo_en_transcript(entrada.get("transcript_path"))
    salida, interrumpido = salida_de(entrada.get("tool_response"))
    comando = str(datos.get("command", ""))
    actuales = None
    if not previo.get("abortado") and (herramienta in ESCRITURAS or herramienta in ("Bash", "PowerShell")):
        actuales = cerco.cambios_git(previo["worktree"])
    nuevos_fuera: list[str] = []

    def cambio(e: dict) -> None:
        if modelo_nuevo:
            e.update(modelo=modelo_nuevo, modelo_fuente="transcript", actor=comun.actor_de(cfg, modelo_nuevo))
        if herramienta in ("Bash", "PowerShell"):
            e.setdefault("comandos", []).append({"cuando": cuando, "herramienta": herramienta, "comando": comando,
                                                 "salida": salida[-MAX_SALIDA:], "interrumpido": interrumpido})
            e["comandos"] = e["comandos"][-60:]
            if re.search(r"\bgit\b.*\bcommit\b", comando):
                e.setdefault("escrituras", []).append({"cuando": cuando, "herramienta": herramienta, "ruta": "git commit"})
        if herramienta in ESCRITURAS:
            e.setdefault("escrituras", []).append({"cuando": cuando, "herramienta": herramienta, "ruta": ruta_de(datos)})
        if herramienta.endswith("send_message") and "ENTREGA" in json.dumps(datos, ensure_ascii=False):
            e["aviso_07"] = {"cuando": cuando, "herramienta": herramienta}
        if actuales is not None:
            for rel in sorted(actuales - set(e.get("sucios_inicio", []))):
                if rel not in e.setdefault("cambios_vistos", []):
                    e["cambios_vistos"].append(rel)
                    e.setdefault("escrituras", []).append({"cuando": cuando, "herramienta": f"git:{herramienta}", "ruta": rel})
                if not cerco.rel_permitida(rel, e["permitidos"]) and rel not in e.setdefault("fuera_avisados", []):
                    e["fuera_avisados"].append(rel)
                    nuevos_fuera.append(rel)
        coste = comun.coste_usd(uso, e.get("modelo"))
        if coste is not None:
            e.setdefault("coste_turnos", {})[entrada.get("prompt_id") or "sin-prompt"] = round(coste, 6)

    estado = comun.actualizar_estado(sid, cambio)
    plan_id = comun.plan_de(estado, cfg)
    coste = comun.coste_usd(uso, estado.get("modelo"))
    detalle = (f"ruta={ruta_de(datos)} · hora={cuando} · tokens_turno=in:{uso['input']}/out:{uso['output']}/"
               f"cache_w:{uso['cache_creation']}/cache_r:{uso['cache_read']} · coste_turno_usd="
               + (f"{coste:.4f}" if coste is not None else "n/d")
               + f" · coste_sesion_usd={sum(estado.get('coste_turnos', {}).values()):.4f} · dur_ms={entrada.get('duration_ms', 'n/d')} · sesion={sid[:8]}")
    ops = []
    if modelo_nuevo:
        ops += [{"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": modelo_nuevo},
                comun.op_evento(estado["actor"], "modelo_observado", f"modelo real {modelo_nuevo} leído del transcript", plan_id)]
    ops.append(comun.op_evento(estado["actor"], f"herramienta:{herramienta}", detalle, plan_id, cuando))
    if nuevos_fuera:
        ops += comun.ops_bloqueo(estado["actor"], "cerco", plan_id,
                                 f"auditoría git tras {herramienta}: cambios fuera de archivos_permitidos {nuevos_fuera}")
    try:
        comun.emitir(cfg, ops)
    except comun.RegistroCaido as e:
        parar(f"REGISTRO SYPNOSE CAÍDO al registrar {herramienta}: sesión parada (FAIL LOUD). {e}")
    except comun.RegistroRechazo as e:
        parar(f"El registro rechazó el evento de {herramienta}: sesión parada. {e}")
    if nuevos_fuera:
        comun.bloquear(f"CERCO (auditoría git): {herramienta} dejó cambios fuera de archivos_permitidos en {estado['worktree']}: "
                       f"{', '.join(nuevos_fuera)}. Reviértelos con `git checkout -- <ruta>` o `git clean -f -- <ruta>`. Registrado como bloqueo:cerco.")


if __name__ == "__main__":
    comun.ejecutar(main, parar)
