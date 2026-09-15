"""SessionStart (B1): envía la cola pendiente y arma el brief desde el registro SYPNOSE. Sin plan abierto con dueño H: la sesión queda ABORTADA."""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import cerco
import comun

FORMATO_ENTREGA = (
    "El cierre de la tarea exige tres cosas: la comprobación ejecutada tal cual en el worktree con Bash/PowerShell (sin tuberías, filtros "
    "ni comandos añadidos); un aviso a 07-verificador por "
    "send_message que incluya el bloque ENTREGA; y un mensaje final que termina con el bloque:\n"
    "ENTREGA\nComprobación: <comando literal del requisito>\nSalida: <líneas reales de la salida, pegadas sin retocar>\n"
    "LECCIÓN: <una línea útil para el siguiente agente de esta línea de la oferta>\n"
    "Una ENTREGA solo vale si la comprobación pasa: una salida con fallos (failed, error, Traceback, exit code distinto de 0) o un "
    "resultado que no cumple lo esperado tras '→' la invalida.\n"
    "Cuando la entrega no es posible, una última línea 'PREGUNTA: <qué hace falta de Carlos>' o 'BLOQUEADO: <qué impide entregar>' "
    "permite cerrar y queda registrada para Carlos como pregunta_humano. Un segundo intento de cierre sin ENTREGA válida también se "
    "permite, pero la tarea queda como bloqueo:entrega_incompleta."
)


PRIORIDAD = {"devuelta": 0, "trabajando": 1, "pendiente": 2}


def buscar_plan(cfg: dict):
    """Tareas trabajables: devuelta > trabajando > pendiente. espera_firma (la firma Carlos), hecha y bloqueada no se trabajan."""
    listado = comun.leer_registro(cfg, "/planes?limite=500")["planes"]
    fijado = cfg.get("plan_id")
    filtrados = [p for p in listado if p.get("tareas") and (p["id"] == fijado if fijado else p["id"].startswith(cfg.get("prefijo_planes", "")))]
    prefijo_agente = f"IA:{cfg['carpeta']}:"
    candidatos, sin_trabajo = [], []
    for grupo in ([p for p in filtrados if p["estado"] == "abierto"], [p for p in filtrados if p["estado"] != "abierto"]):
        for p in grupo:
            d = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(p["id"], safe=""))
            propias = [t for t in d["tareas"] if str(t.get("agente") or "").startswith(prefijo_agente)]
            mias = sorted((t for t in propias if t["progreso"] in PRIORIDAD), key=lambda t: (PRIORIDAD[t["progreso"]], t["id"]))
            if mias:
                candidatos.append((d, mias))
            elif propias:
                sin_trabajo.append((d["plan"]["id"], [(t["id"], t["progreso"]) for t in propias]))
        validos = [c for c in candidatos if c[0]["plan"]["estado"] == "abierto" and str(c[0]["plan"].get("dueno") or "").startswith("H:")]
        if validos:
            return validos[0], candidatos, sin_trabajo
    return None, candidatos, sin_trabajo


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


def devolucion(detalle: dict, tarea: dict) -> str:
    if tarea.get("progreso") != "devuelta":
        return ""
    patron = re.compile(rf"\btarea {tarea['id']}\b")
    for e in detalle.get("eventos", []):
        if ("bloqueo:verificador" in e["accion"] or "devuelta" in e["accion"]) and patron.search(e.get("detalle") or ""):
            return f"Motivo de la devolución ({e['actor']}, {e['cuando']}): {(e.get('detalle') or '')[:600]}"
    return "Motivo de la devolución: no aparece en los últimos eventos del plan."


def forma_sql(comprobacion: str, cfg: dict) -> str:
    """Una comprobación SQL solo cuenta ejecutada contra la base del registro por ssh: se enseña la forma exacta."""
    consulta = re.split(r"\s*(?:→|->)\s*", comprobacion, maxsplit=1)[0].strip()
    if not re.match(r"(?is)^(select|with)\b", consulta):
        return ""
    s = cfg["ssh"]
    return (f"Ejecución de la comprobación (única forma que cuenta): ssh -i {s['clave']} -p {s['puerto']} {s['destino']} "
            f"\"sqlite3 {s['db']} \\\"{consulta}\\\"\"")


def _gh(worktree: str, *args: str):
    p = subprocess.run(["gh", *args], cwd=worktree, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=20, creationflags=cerco.SIN_VENTANA)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:200])
    return json.loads(p.stdout or "[]")


def github(worktree: str) -> str:
    """GitHub por gh (CLI autenticado en el PC): CI y PR de la rama del worktree y último CI de main."""
    try:
        rama = _git(worktree, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        campos = "status,conclusion,workflowName,createdAt,url"
        run_rama = _gh(worktree, "run", "list", "--branch", rama, "--limit", "1", "--json", campos)
        run_main = _gh(worktree, "run", "list", "--branch", "main", "--limit", "1", "--json", campos)
        prs = _gh(worktree, "pr", "list", "--head", rama, "--state", "all", "--limit", "1", "--json", "number,state,url")
    except (OSError, subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as e:
        return f"gh no disponible ({type(e).__name__}: {e})"

    def resumen_run(runs: list) -> str:
        return f"{runs[0]['workflowName']} {runs[0]['conclusion'] or runs[0]['status']} {runs[0]['createdAt']} {runs[0]['url']}" if runs else "sin runs"

    pr = f"PR #{prs[0]['number']} {prs[0]['state']} {prs[0]['url']}" if prs else "sin PR"
    return f"rama {rama}: CI {resumen_run(run_rama)} · {pr} · main: CI {resumen_run(run_main)}"


def unir_nota(nota: str, texto: str) -> str:
    """Añade un aviso de la cola a la nota del brief sin repetir la explicación del modo prueba."""
    if texto.startswith("MODO PRUEBA") and "MODO PRUEBA" in nota:
        return nota
    return " · ".join(x for x in (nota, texto) if x)


def envio_inicial(cfg: dict) -> str:
    resultados = comun.vaciar_todas(cfg, "arranque")
    partes = []
    enviadas = sum(r.get("enviadas", 0) for r in resultados if r["estado"] in ("ok", "rechazo", "kb_pendiente"))
    if enviadas:
        partes.append(f"{enviadas} operaciones pendientes enviadas al registro")
    caidas = sum(1 for r in resultados if r.get("caido_registrado"))
    if caidas:
        partes.append(f"bloqueo:registro_caido registrado ({caidas} cola(s) retenida(s) por registro caído)")
    kb_caidas = sum(1 for r in resultados if r.get("kb_caida_registrada"))
    if kb_caidas:
        partes.append(f"bloqueo:kb_caida registrado ({kb_caidas} cola(s) con lecciones retenidas por la KB caída)")
    pruebas = [r for r in resultados if r["estado"] == "prueba"]
    if pruebas:
        partes.append(comun.texto_fallo_cola(cfg, {**pruebas[0], "pendientes": sum(r["pendientes"] for r in pruebas),
                                                   "cola": pruebas[0]["cola"] if len(pruebas) == 1 else f"{len(pruebas)} colas en {comun.COLA_DIR}"}))
    partes += [comun.texto_fallo_cola(cfg, r) for r in resultados if r["estado"] in ("fallo", "rechazo", "kb_pendiente")]
    return " · ".join(p for p in partes if p)


def abortar(estado: dict, cfg: dict, motivo: str, plan_id: str | None, nota_cola: str = "") -> dict:
    estado.update(abortado=True, motivo=motivo, plan={"id": plan_id} if plan_id else None, tarea=None, requisito=None)
    sid = estado["session_id"]
    if not estado.get("bloqueo_brief_emitido"):
        comun.encolar(sid, comun.ops_bloqueo(estado["actor"], "brief", plan_id, f"sesión {sid[:8]} sin trabajo permitido: {motivo}"))
        estado["bloqueo_brief_emitido"] = True
        r = comun.vaciar(cfg, sid, "arranque")
        nota_cola = unir_nota(nota_cola, comun.texto_fallo_cola(cfg, r))
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
        encontrado, candidatos, sin_trabajo = buscar_plan(cfg)
    except comun.RegistroCaido as e:
        return abortar(estado, cfg, f"REGISTRO SYPNOSE CAÍDO: no se puede verificar el plan ({e})",
                       comun.plan_de(previo or comun.ultimo_estado(), cfg), nota_cola)
    if not encontrado:
        if candidatos:
            p = candidatos[0][0]["plan"]
            motivo = (f"{p['id']} está '{p['estado']}' con dueño {p.get('dueno') or 'ninguno'}: solo se trabaja un plan abierto por un humano (H:). "
                      f"Carlos debe abrirlo como dueño en la consola SYPNOSE ({cfg['registro_url']}).")
            return abortar(estado, cfg, motivo, p["id"], nota_cola)
        if sin_trabajo:
            plan_id, tareas = sin_trabajo[0]
            estados = ", ".join(f"tarea {i} {pr}" for i, pr in tareas)
            return abortar(estado, cfg, f"{plan_id} no tiene trabajo abierto para IA:{cfg['carpeta']}:* ({estados}): espera_firma la firma Carlos "
                                        "y bloqueada espera a otra tarea.", plan_id, nota_cola)
        return abortar(estado, cfg, f"ningún plan {cfg.get('prefijo_planes', '')}* tiene tareas para IA:{cfg['carpeta']}:*.", cfg.get("plan_id"), nota_cola)

    detalle, mias = encontrado
    p, tarea = detalle["plan"], mias[0]
    motivo_devolucion = devolucion(detalle, tarea)
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
        sucios_inicio_extra=previo.get("sucios_inicio_extra") or {x["ruta"]: sorted(c) for x in cfg.get("worktrees_extra") or []
                                                                   if x.get("ruta") and (c := cerco.cambios_git(x["ruta"])) is not None},
        plan={k: p.get(k) for k in ("id", "que", "para", "estado", "dueno", "worktree", "cuesta", "abierto_en")},
        tarea={k: tarea.get(k) for k in ("id", "req_ref", "titulo", "progreso", "agente")},
    )
    cuando = comun.ahora()
    # Sin SessionStart (sesión abierta antes de instalar el caparazón) el estado lo crea otro hook, que no trae 'source'.
    origen = entrada.get("source") or f"sin SessionStart: estado creado por {entrada.get('hook_event_name') or 'un hook sin nombre'}"
    ops = [
        comun.op_evento(estado["actor"], "sesion_iniciada",
                        f"{origen} · modelo {modelo} ({fuente_modelo}) · tarea {tarea['id']} {req['ref']} · worktree {cfg['worktree']}",
                        p["id"], cuando),
        {"op": "tarea_progreso", "tarea_id": tarea["id"], "progreso": "trabajando", "desde": ["pendiente", "devuelta"],
         "evento": comun.op_evento(estado["actor"], "tarea_trabajando", f"tarea {tarea['id']} {tarea['progreso']} → trabajando", p["id"], cuando)},
    ]
    if modelo != "desconocido":
        ops.insert(0, {"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": modelo})
    comun.encolar(sid, ops)
    r = comun.vaciar(cfg, sid, "arranque")
    if r["estado"] in ("ok", "rechazo", "kb_pendiente"):
        with contextlib.suppress(comun.RegistroCaido, KeyError, StopIteration):
            fresco = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(p["id"], safe=""))
            estado["tarea"]["progreso"] = next(t["progreso"] for t in fresco["tareas"] if t["id"] == tarea["id"])
    nota_cola = unir_nota(nota_cola, comun.texto_fallo_cola(cfg, r))
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
        motivo_devolucion,
        f"Requisito {req['ref']} (EARS literal): {req['ears']}",
        f"Comprobación: {req['comprobacion']}",
        forma_sql(req["comprobacion"], cfg),
        f"Worktree local: {cfg['worktree']}",
        f"Archivos permitidos ({fuente_permitidos}): {', '.join(permitidos)}",
        *[f"Worktree extra {x['ruta']}: {', '.join(x.get('permitidos') or [])} (y git -C en él)" for x in cfg.get("worktrees_extra") or [] if x.get("ruta")],
        f"Presupuesto: {presupuesto}",
        f"Grafo del repo: {grafo(cfg['worktree'])}",
        f"GitHub (gh): {github(cfg['worktree'])}",
        f"Última lección de la línea: {leccion(cfg, estado['linea'])}",
        f"Cola del caparazón: {nota_cola}" if nota_cola else "",
        "Reglas de máquina: escrituras fuera del cerco se bloquean (bloqueo:cerco); cada herramienta deja evento con tokens y coste en la cola "
        "local, que llega al registro cada 60 s y al terminar el turno (si el registro no responde, se avisa y la cola se conserva); "
        f"commits con Chat: {cfg['carpeta']}, Model: <modelo real>, Plan: {p['id']} y Tarea: {tarea['id']} en el último párrafo del mensaje, "
        "junto a Co-Authored-By y sin línea en blanco entre ellas.",
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
    comun.actualizar_estado(estado["session_id"], lambda e: e.update(brief_entregado=comun.ahora(), brief_via="SessionStart"))
    comun.salir_json({"systemMessage": aviso, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": estado["brief"]}})


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m, "hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": f"BRIEF CAPARAZÓN ABORTADO: {m}"}}))
