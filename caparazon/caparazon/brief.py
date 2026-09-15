"""SessionStart (B1): envía la cola pendiente y arma el brief desde el registro SYPNOSE. Sin plan abierto con dueño H: la sesión queda ABORTADA."""
from __future__ import annotations

import contextlib
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import cerco
import comun

FORMATO_ENTREGA = (
    "Para cerrar la tarea: (1) ejecuta la comprobación en el worktree con Bash/PowerShell; (2) avisa a 07-verificador con "
    "send_message incluyendo el bloque ENTREGA; (3) termina tu mensaje con el bloque:\n"
    "ENTREGA\nComprobación: <comando literal del requisito>\nSalida: <líneas reales de la salida, pegadas sin retocar>\n"
    "LECCIÓN: <una línea útil para el siguiente agente de esta línea de la oferta>\n"
    "Si antes de terminar necesitas a Carlos, acaba el mensaje con una línea 'PREGUNTA: ...'."
)


def buscar_plan(cfg: dict):
    listado = comun.leer_registro(cfg, "/planes?limite=500")["planes"]
    fijado = cfg.get("plan_id")
    filtrados = [p for p in listado if p.get("tareas") and (p["id"] == fijado if fijado else p["id"].startswith(cfg.get("prefijo_planes", "")))]
    prefijo_agente = f"IA:{cfg['carpeta']}:"
    candidatos = []
    for grupo in ([p for p in filtrados if p["estado"] == "abierto"], [p for p in filtrados if p["estado"] != "abierto"]):
        for p in grupo:
            d = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(p["id"], safe=""))
            mias = [t for t in d["tareas"] if str(t.get("agente") or "").startswith(prefijo_agente) and t["progreso"] != "hecha"]
            if mias:
                candidatos.append((d, mias))
        validos = [c for c in candidatos if c[0]["plan"]["estado"] == "abierto" and str(c[0]["plan"].get("dueno") or "").startswith("H:")]
        if validos:
            return validos[0], candidatos
    return None, candidatos


def resolver_permitidos(plan: dict, cfg: dict) -> tuple[list[str], str]:
    afecta = (plan.get("afecta") or "").strip()
    trozos = [t.strip().strip("`") for t in re.split(r"[,;\n]", afecta) if t.strip()]
    if trozos and all("/" in t or "." in t for t in trozos):
        return trozos, "registro: plan.afecta"
    return (cerco.ficheros_propios_claude_md(Path(cfg["carpeta_ruta"])),
            f"{cfg['carpeta']}/CLAUDE.md §Ficheros propios (plan.afecta = '{afecta}')")


def _git(worktree: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", worktree, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=15, creationflags=cerco.SIN_VENTANA)


def grafo(worktree: str) -> str:
    """GRAPH_REPORT.md lo generan el CI y el 67 y se commitea: se lee del worktree o, si no está, de main."""
    f = Path(worktree) / "graphify-out" / "GRAPH_REPORT.md"
    if f.exists():
        fecha = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%MZ")
        return f"(worktree, {fecha})\n" + f.read_text(encoding="utf-8", errors="replace")[:2500]
    for ref in ("origin/main", "main"):
        commit = _git(worktree, "log", "-1", "--format=%h %cs", ref, "--", "graphify-out/GRAPH_REPORT.md")
        if commit.returncode == 0 and commit.stdout.strip():
            contenido = _git(worktree, "show", f"{ref}:graphify-out/GRAPH_REPORT.md")
            if contenido.returncode == 0:
                return f"({ref} @ {commit.stdout.strip()})\n" + contenido.stdout[:2500]
    return "no hay graphify-out/GRAPH_REPORT.md en el worktree ni en main (lo generan el CI y el 67 y se commitea en el repo)."


def leccion(cfg: dict, linea: str | None) -> str:
    if not linea:
        return "sin línea de la oferta asociada al plan."
    try:
        lec = comun.kb_ultima_leccion(cfg, linea)
    except Exception as e:
        return f"KB NO RESPONDE ({cfg['kb_url']}): {type(e).__name__}: {e}"
    return f"{lec['key']}: {str(lec.get('value'))[:1500]}" if lec else f"ninguna todavía (clave leccion-linea-{linea}-*)."


def envio_inicial(cfg: dict) -> str:
    resultados = comun.vaciar_todas(cfg, "arranque")
    partes = []
    enviadas = sum(r.get("enviadas", 0) for r in resultados if r["estado"] in ("ok", "rechazo"))
    if enviadas:
        partes.append(f"{enviadas} operaciones pendientes enviadas al registro")
    caidas = sum(1 for r in resultados if r.get("caido_registrado"))
    if caidas:
        partes.append(f"bloqueo:registro_caido registrado ({caidas} cola(s) retenida(s) por registro caído)")
    partes += [comun.texto_fallo_cola(cfg, r) for r in resultados if r["estado"] in ("fallo", "rechazo")]
    return " · ".join(p for p in partes if p)


def abortar(estado: dict, cfg: dict, motivo: str, plan_id: str | None, nota_cola: str = "") -> dict:
    estado.update(abortado=True, motivo=motivo, plan={"id": plan_id} if plan_id else None, tarea=None, requisito=None)
    sid = estado["session_id"]
    if not estado.get("bloqueo_brief_emitido"):
        comun.encolar(sid, comun.ops_bloqueo(estado["actor"], "brief", plan_id, f"sesión {sid[:8]} sin trabajo permitido: {motivo}"))
        estado["bloqueo_brief_emitido"] = True
        r = comun.vaciar(cfg, sid, "arranque")
        nota_cola = " · ".join(x for x in (nota_cola, comun.texto_fallo_cola(cfg, r)) if x)
    estado["nota_cola"] = nota_cola
    estado["brief"] = (f"═══ BRIEF CAPARAZÓN · {cfg['carpeta']} · ABORTADO ═══\nActor: {estado['actor']}\nMotivo: {motivo}\n"
                       + (f"Cola del caparazón: {nota_cola}\n" if nota_cola else "")
                       + "Mientras siga abortado, el caparazón bloquea tus prompts y todas las escrituras (Edit/Write/Bash/PowerShell). "
                       f"Cada prompt nuevo vuelve a consultar el registro.\nTúnel del registro: {comun.comando_tunel(cfg)}")
    with comun.cerrojo():
        comun.guardar_estado(estado)
    return estado


def construir_estado(entrada: dict, cfg: dict) -> dict:
    sid = entrada.get("session_id") or "sin-sesion"
    previo = comun.leer_estado(sid) or {}
    modelo, fuente_modelo = comun.modelo_limpio(entrada.get("model")), "SessionStart.model"
    if not modelo and previo.get("modelo") not in (None, "desconocido"):
        modelo, fuente_modelo = previo["modelo"], "estado previo de la sesión"
    if not modelo:
        modelo, fuente_modelo = comun.modelo_en_transcript(entrada.get("transcript_path")) or "desconocido", "transcript"
    estado = {
        "session_id": sid, "carpeta": cfg["carpeta"], "creado": previo.get("creado") or comun.ahora(),
        "modelo": modelo, "modelo_fuente": fuente_modelo, "actor": comun.actor_de(cfg, modelo),
        "worktree": cfg["worktree"], "comandos": previo.get("comandos", []), "escrituras": previo.get("escrituras", []),
        "aviso_07": previo.get("aviso_07"), "entregas": previo.get("entregas", []), "preguntas": previo.get("preguntas", []),
        "fuera_avisados": previo.get("fuera_avisados", []), "cambios_vistos": previo.get("cambios_vistos", []),
        "coste_turnos": previo.get("coste_turnos", {}), "bloqueo_brief_emitido": previo.get("bloqueo_brief_emitido", False),
    }
    nota_cola = envio_inicial(cfg)
    try:
        comun.salud(cfg)
        encontrado, candidatos = buscar_plan(cfg)
    except comun.RegistroCaido as e:
        return abortar(estado, cfg, f"REGISTRO SYPNOSE CAÍDO: no se puede verificar el plan ({e})",
                       comun.plan_de(previo or comun.ultimo_estado(), cfg), nota_cola)
    if not encontrado:
        if candidatos:
            p = candidatos[0][0]["plan"]
            motivo = (f"{p['id']} está '{p['estado']}' con dueño {p.get('dueno') or 'ninguno'}: solo se trabaja un plan abierto por un humano (H:). "
                      f"Carlos debe abrirlo como dueño en la consola SYPNOSE ({cfg['registro_url']}).")
            return abortar(estado, cfg, motivo, p["id"], nota_cola)
        return abortar(estado, cfg, f"ningún plan {cfg.get('prefijo_planes', '')}* tiene tareas para IA:{cfg['carpeta']}:*.", cfg.get("plan_id"), nota_cola)

    detalle, mias = encontrado
    p, tarea = detalle["plan"], mias[0]
    req = next((r for r in detalle["requisitos"] if r["ref"] == tarea["req_ref"]), None)
    if not req:
        return abortar(estado, cfg, f"la tarea {tarea['id']} apunta al requisito {tarea['req_ref']}, que no existe en {p['id']}.", p["id"], nota_cola)
    permitidos, fuente_permitidos = resolver_permitidos(p, cfg)
    if not permitidos:
        return abortar(estado, cfg, f"sin archivos permitidos para {p['id']} ({fuente_permitidos}): el cerco no se puede definir.", p["id"], nota_cola)
    m = re.search(r"(T\d{2})$", p["id"])
    estado.update(
        abortado=False, motivo=None, linea=m.group(1) if m else None, requisito=req, permitidos=permitidos,
        permitidos_fuente=fuente_permitidos, sucios_inicio=previo.get("sucios_inicio") or sorted(cerco.cambios_git(cfg["worktree"]) or []),
        plan={k: p.get(k) for k in ("id", "que", "para", "estado", "dueno", "worktree", "cuesta", "abierto_en")},
        tarea={k: tarea.get(k) for k in ("id", "req_ref", "titulo", "progreso", "agente")},
    )
    cuando = comun.ahora()
    ops = [
        comun.op_evento(estado["actor"], "sesion_iniciada",
                        f"{entrada.get('source', '?')} · modelo {modelo} ({fuente_modelo}) · tarea {tarea['id']} {req['ref']} · worktree {cfg['worktree']}",
                        p["id"], cuando),
        {"op": "tarea_progreso", "tarea_id": tarea["id"], "progreso": "trabajando", "desde": ["pendiente", "devuelta"],
         "evento": comun.op_evento(estado["actor"], "tarea_trabajando", f"tarea {tarea['id']} {tarea['progreso']} → trabajando", p["id"], cuando)},
    ]
    if modelo != "desconocido":
        ops.insert(0, {"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": modelo})
    comun.encolar(sid, ops)
    r = comun.vaciar(cfg, sid, "arranque")
    if r["estado"] in ("ok", "rechazo"):
        with contextlib.suppress(comun.RegistroCaido, KeyError, StopIteration):
            fresco = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(p["id"], safe=""))
            estado["tarea"]["progreso"] = next(t["progreso"] for t in fresco["tareas"] if t["id"] == tarea["id"])
    nota_cola = " · ".join(x for x in (nota_cola, comun.texto_fallo_cola(cfg, r)) if x)
    estado["nota_cola"] = nota_cola
    agente_nota = "" if tarea.get("agente") == estado["actor"] else f" (la tarea está asignada a {tarea.get('agente')})"
    presupuesto = f"{p['cuesta']} USD (plan.cuesta)" if p.get("cuesta") is not None else "sin definir (plan.cuesta vacío)"
    estado["brief"] = "\n".join(x for x in [
        f"═══ BRIEF CAPARAZÓN · {cfg['carpeta']} · {cuando} ═══",
        f"Actor: {estado['actor']} — modelo leído de {fuente_modelo}{agente_nota}",
        f"Plan: {p['id']} · {p['estado']} · dueño {p['dueno']} · abierto_en {p.get('abierto_en')} · worktree en registro {p.get('worktree')}",
        f"Línea de la oferta (literal): \"{p['para']}\"",
        f"Qué: {p['que']}",
        f"Tarea {tarea['id']} · requisito {req['ref']} · progreso {estado['tarea']['progreso']}",
        f"Requisito {req['ref']} (EARS literal): {req['ears']}",
        f"Comprobación: {req['comprobacion']}",
        f"Worktree local: {cfg['worktree']}",
        f"Archivos permitidos ({fuente_permitidos}): {', '.join(permitidos)}",
        f"Presupuesto: {presupuesto}",
        f"Grafo del repo: {grafo(cfg['worktree'])}",
        f"Última lección de la línea: {leccion(cfg, estado['linea'])}",
        f"Cola del caparazón: {nota_cola}" if nota_cola else "",
        "Reglas de máquina: escrituras fuera del cerco se bloquean (bloqueo:cerco); cada herramienta deja evento con tokens y coste en la cola "
        "local, que llega al registro cada 60 s y al terminar el turno (si el registro no responde, se avisa y la cola se conserva); "
        f"commits con pie Chat: {cfg['carpeta']} / Model: / Plan: {p['id']} / Tarea: {tarea['id']}.",
        FORMATO_ENTREGA,
    ] if x)
    with comun.cerrojo():
        comun.guardar_estado(estado)
    return estado


def main() -> None:
    entrada = comun.leer_stdin()
    estado = construir_estado(entrada, comun.config())
    if estado["abortado"]:
        aviso = f"Caparazón ABORTADO: {estado['motivo']}"
    else:
        aviso = f"Caparazón: {estado['plan']['id']} · tarea {estado['tarea']['id']} · cerco {', '.join(estado['permitidos'])}"
    if estado.get("nota_cola"):
        aviso += f"\n{estado['nota_cola']}"
    comun.salir_json({"systemMessage": aviso, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": estado["brief"]}})


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m, "hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": f"BRIEF CAPARAZÓN ABORTADO: {m}"}}))
