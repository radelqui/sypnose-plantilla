"""PreToolUse (B3): cerco de escritura. Bloquea Edit/Write/MultiEdit/NotebookEdit/Bash/PowerShell fuera del worktree o de los archivos permitidos."""
from __future__ import annotations

import sys

import cerco
import comun


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    herramienta = entrada.get("tool_name", "")
    datos = entrada.get("tool_input") or {}
    cwd = entrada.get("cwd") or cfg["carpeta_ruta"]
    try:
        comun.salud(cfg)
    except comun.RegistroCaido as e:
        previo = comun.leer_estado(entrada.get("session_id") or "") or {}
        comun.guardar_pendientes(comun.ops_bloqueo(previo.get("actor") or comun.actor_de(cfg, None), "registro",
                                                   comun.plan_de(previo, cfg), f"{herramienta} bloqueada: registro caído ({e})"))
        comun.bloquear(f"REGISTRO SYPNOSE CAÍDO: {herramienta} bloqueada (FAIL LOUD).\n{e}\nTúnel: {comun.comando_tunel(cfg)}")
    estado = comun.asegurar_estado(entrada, cfg)
    if estado.get("abortado"):
        comun.bloquear(f"CAPARAZÓN ABORTADO: {herramienta} bloqueada.\n{estado['motivo']}")
    extra = [entrada["scratchpad_dir"]] if entrada.get("scratchpad_dir") else []
    fallos = []
    for objetivo in cerco.objetivos_herramienta(herramienta, datos, cwd):
        motivo = objetivo and cerco.veredicto(objetivo, cwd, estado["worktree"], estado["permitidos"], extra)
        if motivo:
            fallos.append(motivo)
    if not fallos:
        sys.exit(0)
    resumen = f"{herramienta} bloqueada por el cerco: " + " | ".join(fallos)
    detalle = resumen + (f" · comando: {datos.get('command', '')[:300]}" if herramienta in ("Bash", "PowerShell") else "")
    try:
        r = comun.emitir(cfg, comun.ops_bloqueo(estado["actor"], "cerco", estado["plan"]["id"], detalle))
        registro = f"Registrado en SYPNOSE: evento {r['resultados'][0]['id']} bloqueo:cerco + evidencia."
    except (comun.RegistroCaido, comun.RegistroRechazo) as e:
        registro = f"El bloqueo no se pudo registrar ({e}); queda en pendientes."
    comun.bloquear(f"CERCO: {resumen}\nSolo puedes escribir dentro de {estado['worktree']} en: {', '.join(estado['permitidos'])}.\n{registro}")


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
