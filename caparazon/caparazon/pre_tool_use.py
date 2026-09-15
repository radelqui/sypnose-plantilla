"""PreToolUse (B3): cerco de escritura. Bloquea Edit/Write/MultiEdit/NotebookEdit/Bash/PowerShell fuera del worktree o de los archivos
permitidos. No depende del registro: el bloqueo va a la cola local."""
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
    estado = comun.asegurar_estado(entrada, cfg)
    tipo = comun.tipo_aborto(estado)
    if tipo == "registro_caido":
        comun.bloquear(f"CAPARAZÓN ABORTADO: {herramienta} bloqueada.\n{estado['motivo']}")
    if tipo == "sin_tarea":
        # B10 (lead, 15-sep): sin tarea se puede leer; escribir ficheros o ejecutar lo que cambie algo se bloquea con el aviso.
        if herramienta in ("Bash", "PowerShell"):
            lectura = cerco.solo_lectura(datos.get("command", ""))
        else:
            lectura = herramienta not in ("Edit", "Write", "MultiEdit", "NotebookEdit")
        if lectura:
            sys.exit(0)
        comun.bloquear(f"{comun.aviso_sin_tarea(estado, cfg)}\n({herramienta} bloqueada. Detalle: {estado['motivo']})")
    extra = [entrada["scratchpad_dir"]] if entrada.get("scratchpad_dir") else []
    extras_wt = cfg.get("worktrees_extra") or []
    fallos = []
    for objetivo in cerco.objetivos_herramienta(herramienta, datos, cwd):
        motivo = objetivo and cerco.veredicto(objetivo, cwd, estado["worktree"], estado["permitidos"], extra, extras_wt)
        if motivo:
            fallos.append(motivo)
    if not fallos:
        sys.exit(0)
    resumen = f"{herramienta} bloqueada por el cerco: " + " | ".join(fallos)
    detalle = resumen + (f" · comando: {datos.get('command', '')[:300]}" if herramienta in ("Bash", "PowerShell") else "")
    comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "cerco", estado["plan"]["id"], detalle))
    en_extras = "".join(f"; dentro de {x['ruta']} en: {', '.join(x.get('permitidos') or [])}" for x in extras_wt if x.get("ruta"))
    comun.bloquear(f"CERCO: {resumen}\nSolo puedes escribir dentro de {estado['worktree']} en: {', '.join(estado['permitidos'])}{en_extras}.\n"
                   "bloqueo:cerco anotado en la cola del caparazón; llega al registro SYPNOSE en el siguiente envío (≤60 s o al terminar el turno).")


if __name__ == "__main__":
    comun.ejecutar(main, comun.bloquear)
