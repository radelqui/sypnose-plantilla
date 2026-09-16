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
    "El cierre de la tarea exige tres cosas EN ESTE ORDEN: 1) ejecutar la comprobación tal cual en el worktree con Bash/PowerShell "
    "(sin tuberías, filtros ni comandos añadidos); 2) enviar a 07-verificador por send_message un bloque con la comprobación y su salida; "
    "3) cerrar el turno con el bloque ENTREGA.\n"
    "ENTREGA\nComprobación: <comando literal del requisito>\nSalida: <líneas reales de la salida, pegadas sin retocar>\n"
    "LECCIÓN: <una línea útil para el siguiente agente de esta línea de la oferta>\n"
    "Una ENTREGA solo vale si la comprobación pasa: una salida con fallos (failed, error, Traceback, exit code distinto de 0) o un "
    "resultado que no cumple lo esperado tras '→' la invalida.\n"
    "Con varias tareas abiertas, las líneas 'Plan: <id>' y 'Tarea: <id>' en el bloque ENTREGA seleccionan qué plan y tarea entregar; "
    "sin ellas se entrega la tarea del brief.\n"
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
            return validos, candidatos, sin_trabajo
    return [], candidatos, sin_trabajo


def es_mia(tarea: dict, cfg: dict) -> bool:
    return str(tarea.get("agente") or "").startswith(f"IA:{cfg['carpeta']}:")


ENTREGA_EN_COLA = re.compile(r"^tarea (\d+) ")


def entregas_en_cola(plan_id: str) -> set[int]:
    """Tareas del plan con un tarea_entregada que sigue en una cola local de esta carpeta: el registro todavía no lo tiene."""
    ids: set[int] = set()
    for f in sorted(comun.COLA_DIR.glob("*.jsonl")) if comun.COLA_DIR.exists() else []:
        if f.name.endswith(".rechazadas.jsonl"):
            continue
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            for linea in f.read_text(encoding="utf-8").splitlines():
                for o in (json.loads(linea)["ops"] if linea.strip() else []):
                    m = ENTREGA_EN_COLA.match(str(o.get("detalle") or ""))
                    if m and o.get("accion") == "tarea_entregada" and o.get("plan_id") == plan_id:
                        ids.add(int(m.group(1)))
    return ids


def pendientes_de_juicio(cfg: dict, plan_id: str, ids: list[int], sabidas=(), espera: float = 45) -> tuple[set[int], str]:
    """B13 (lead, 15-sep): de las tareas 'trabajando' dadas, las que tienen un tarea_entregada posterior a su último tarea_trabajando (el
    inicio de su ciclo de trabajo) están entregadas y esperan el juicio de 07. Se consulta el registro, así vale entre sesiones, y se suma
    lo que siga en la cola local. Si la consulta falla, valen las que sabe la sesión y se devuelve la nota para avisar."""
    ids = sorted(set(ids))
    if not ids:
        return set(), ""
    en_cola = entregas_en_cola(plan_id) & set(ids)
    marcas = ",".join("?" * len(ids))
    sql = (f"SELECT t.id FROM tarea t WHERE t.plan_id=? AND t.id IN ({marcas}) AND t.progreso='trabajando' AND "
           "(SELECT MAX(e.id) FROM evento e WHERE e.plan_id=t.plan_id AND e.accion='tarea_entregada' AND e.detalle LIKE 'tarea ' || t.id || ' %') > "
           "COALESCE((SELECT MAX(e.id) FROM evento e WHERE e.plan_id=t.plan_id AND e.accion='tarea_trabajando' "
           "AND e.detalle LIKE 'tarea ' || t.id || ' %'), 0)")
    try:
        filas = comun.escribir(cfg, [{"op": "consulta", "sql": sql, "params": [plan_id, *ids]}], espera=espera)["resultados"][0]["filas"]
    except (comun.RegistroCaido, comun.RegistroRechazo) as e:
        return (en_cola | (set(sabidas) & set(ids)),
                f"no se pudo consultar en el registro qué tareas esperan juicio ({e}); vale lo que sabe esta sesión")
    return en_cola | {int(f[0]) for f in filas}, ""


def listado_tareas(tareas: list[dict], plan_id: str | None = None) -> str:
    """B13.1 + B14: con más de una tarea trabajable, todas con su plan (si hay varios), requisito, progreso y si ya están entregadas."""
    if len(tareas) < 2:
        return ""
    planes = sorted(set(t.get("plan_id") or plan_id or "" for t in tareas))
    def _linea(t: dict) -> str:
        return f"tarea {t['id']} · {t['req_ref']} · {t['progreso']} · entregada: {'sí' if t.get('entregada') else 'no'}"
    if len(planes) > 1:
        partes = []
        for pid in planes:
            ptareas = [t for t in tareas if (t.get("plan_id") or plan_id) == pid]
            partes.append(f"{pid}: " + " | ".join(_linea(t) for t in ptareas))
        return ("Tus tareas trabajables: " + " · ".join(partes)
                + ". Para entregar una de otro plan, añade «Plan: <id>» y «Tarea: <id>» al bloque ENTREGA.")
    return (f"Tus tareas trabajables en {planes[0]}: " + " | ".join(_linea(t) for t in tareas)
            + ". Para entregar una que no es la de este brief, añade la línea «Tarea: <id>» al bloque ENTREGA.")


def tarea_de_entrega(estado: dict, tarea_id: int, cfg: dict, plan_id_objetivo: str | None = None) -> tuple[dict | None, str | None]:
    """B13.2 + B14 + B19: la tarea que nombra 'Tarea: <id>' (y opcionalmente 'Plan: <id>') en el bloque ENTREGA vale si es del agente en
    ese plan, se puede trabajar y no está ya entregada pendiente de juicio. Devuelve (el estado con esa tarea/plan y su requisito, None) o
    (None, motivo). Lanza RegistroCaido."""
    plan_id = plan_id_objetivo or estado["plan"]["id"]
    detalle = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(plan_id, safe=""))
    if plan_id_objetivo:
        ids_planes = [p["id"] for p in estado.get("planes_trabajables") or []] or [estado["plan"]["id"]]
        if plan_id_objetivo not in ids_planes:
            pl = detalle.get("plan") or {}
            if pl.get("estado") != "abierto" or not str(pl.get("dueno") or "").startswith("H:"):
                return None, f"el plan {plan_id_objetivo} no es un plan abierto con dueño H: ({pl.get('estado')}, {pl.get('dueno')})"
            prefijo = f"IA:{cfg['carpeta']}:"
            if not any(str(t.get("agente") or "").startswith(prefijo) and t.get("progreso") in PRIORIDAD
                       for t in detalle.get("tareas") or []):
                return None, f"el plan {plan_id_objetivo} no tiene tareas trabajables de {prefijo}*"
    t = next((x for x in detalle.get("tareas") or [] if x.get("id") == tarea_id), None)
    if not t or not es_mia(t, cfg):
        return None, f"la tarea {tarea_id} no es una tarea de IA:{cfg['carpeta']}:* en {plan_id}"
    if t.get("progreso") not in PRIORIDAD:
        return None, f"la tarea {tarea_id} no está abierta ({t.get('progreso')})"
    if t["progreso"] == "trabajando" and tarea_id in pendientes_de_juicio(cfg, plan_id, [tarea_id], estado.get("entregadas_pendientes") or [],
                                                                         espera=15)[0]:
        return None, f"la tarea {tarea_id} ya está entregada y pendiente de juicio de {cfg['verificador']}"
    req = next((r for r in detalle.get("requisitos") or [] if r.get("ref") == t.get("req_ref")), None)
    if not req:
        return None, f"la tarea {tarea_id} apunta al requisito {t.get('req_ref')}, que no existe en {plan_id}"
    nuevo = {**estado, "tarea": {k: t.get(k) for k in ("id", "req_ref", "titulo", "progreso", "agente")}, "requisito": req}
    if plan_id != estado["plan"]["id"]:
        p = detalle["plan"]
        nuevo["plan"] = {k: p.get(k) for k in ("id", "que", "para", "estado", "dueno", "worktree", "cuesta", "abierto_en")}
    return nuevo, None


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


def abortar(estado: dict, cfg: dict, motivo: str, plan_id: str | None, nota_cola: str = "", tipo: str = "sin_tarea") -> dict:
    """Sesión sin trabajo. 'registro_caido': no se pudo verificar el plan y se bloquean prompts y escrituras. 'sin_tarea' (B10, lead
    15-sep): el humano puede hablar con su chat y el chat puede leer; solo se bloquea escribir y ejecutar lo que cambie algo."""
    estado.update(abortado=True, abortado_tipo=tipo, motivo=motivo, plan={"id": plan_id} if plan_id else None, tarea=None, requisito=None)
    sid = estado["session_id"]
    if not estado.get("bloqueo_brief_emitido"):
        mecanismo = "registro_caido" if tipo == "registro_caido" else "brief"
        comun.encolar(sid, comun.ops_bloqueo(estado["actor"], mecanismo, plan_id, f"sesión {sid[:8]} sin trabajo permitido: {motivo}"))
        estado["bloqueo_brief_emitido"] = True
        r = comun.vaciar(cfg, sid, "arranque")
        nota_cola = unir_nota(nota_cola, comun.texto_fallo_cola(cfg, r))
    estado["nota_cola"] = nota_cola
    if tipo == "registro_caido":
        titulo, regla = "ABORTADO", (f"Túnel 7101 caído — remedio: `{comun.comando_tunel(cfg)}`\n"
                                     "Mientras no responda, el caparazón bloquea prompts y escrituras. Cada prompt nuevo reintenta.")
    else:
        titulo, regla = "SIN TAREA", f"{comun.aviso_sin_tarea(estado, cfg)} Cada prompt nuevo vuelve a consultar el registro."
    estado["brief"] = (f"═══ BRIEF CAPARAZÓN · {cfg['carpeta']} · {titulo} ═══\nActor: {estado['actor']}\nMotivo: {motivo}\n"
                       + (f"Cola del caparazón: {nota_cola}\n" if nota_cola else "")
                       + f"{regla}\nTúnel del registro: {comun.comando_tunel(cfg)}")
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
        validos, candidatos, sin_trabajo = buscar_plan(cfg)
    except comun.RegistroCaido as e:
        return abortar(estado, cfg, f"REGISTRO SYPNOSE CAÍDO: no se puede verificar el plan ({e})",
                       comun.plan_de(previo or comun.ultimo_estado(), cfg), nota_cola, tipo="registro_caido")
    if not validos:
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

    # B14 (lead, 15-sep): todos los planes válidos, no solo el primero. Los permitidos del cerco son la unión.
    todas_tareas, planes_info, notas_juicio = [], [], []
    todos_permitidos: list[str] = []
    fuentes_permitidos: list[str] = []
    for det, mias in validos:
        pid = det["plan"]["id"]
        trabajando = [t["id"] for t in mias if t["progreso"] == "trabajando"] if len(mias) > 1 else []
        ya, nota = pendientes_de_juicio(cfg, pid, trabajando, previo.get("entregadas_pendientes") or [])
        if nota:
            notas_juicio.append(nota)
        for t in mias:
            t["entregada"] = t["progreso"] == "trabajando" and t["id"] in ya
            t["plan_id"] = pid
        todas_tareas.extend(mias)
        planes_info.append(det)
        perms, fuente = resolver_permitidos(det["plan"], cfg)
        for px in perms:
            if px not in todos_permitidos:
                todos_permitidos.append(px)
        fuentes_permitidos.append(fuente)
    todas_tareas.sort(key=lambda t: (t["entregada"], t.get("plan_id", ""), PRIORIDAD[t["progreso"]], t["id"]))
    nota_juicio = " · ".join(notas_juicio)
    tarea = todas_tareas[0]
    detalle = next(d for d in planes_info if d["plan"]["id"] == tarea["plan_id"])
    p = detalle["plan"]
    motivo_devolucion = devolucion(detalle, tarea)
    req = next((r for r in detalle["requisitos"] if r["ref"] == tarea["req_ref"]), None)
    if not req:
        return abortar(estado, cfg, f"la tarea {tarea['id']} apunta al requisito {tarea['req_ref']}, que no existe en {p['id']}.", p["id"], nota_cola)
    fuente_permitidos = " + ".join(fuentes_permitidos) if len(fuentes_permitidos) > 1 else (fuentes_permitidos[0] if fuentes_permitidos else "")
    if not todos_permitidos:
        return abortar(estado, cfg, f"sin archivos permitidos ({fuente_permitidos}): el cerco no se puede definir.", p["id"], nota_cola)
    m = re.search(r"(T\d{2})$", p["id"])
    estado.update(
        abortado=False, motivo=None, linea=m.group(1) if m else None, requisito=req, permitidos=todos_permitidos,
        permitidos_fuente=fuente_permitidos, sucios_inicio=previo.get("sucios_inicio") or sorted(cerco.cambios_git(cfg["worktree"]) or []),
        sucios_inicio_extra=previo.get("sucios_inicio_extra") or {x["ruta"]: sorted(c) for x in cfg.get("worktrees_extra") or []
                                                                   if x.get("ruta") and (c := cerco.cambios_git(x["ruta"])) is not None},
        plan={k: p.get(k) for k in ("id", "que", "para", "estado", "dueno", "worktree", "cuesta", "abierto_en")},
        tarea={k: tarea.get(k) for k in ("id", "req_ref", "titulo", "progreso", "agente")},
        tareas_trabajables=[{"id": t["id"], "plan_id": t["plan_id"], "req_ref": t["req_ref"], "progreso": t["progreso"], "entregada": t["entregada"]}
                            for t in todas_tareas],
        entregadas_pendientes=sorted(t["id"] for t in todas_tareas if t["entregada"]),
        planes_trabajables=[{k: d["plan"].get(k) for k in ("id", "que", "estado", "dueno")} for d in planes_info],
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
            for t in estado["tareas_trabajables"]:
                if t["id"] == tarea["id"]:
                    t["progreso"] = estado["tarea"]["progreso"]
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
        listado_tareas(estado["tareas_trabajables"]),
        f"Aviso del caparazón: {nota_juicio}" if nota_juicio else "",
        motivo_devolucion,
        f"Requisito {req['ref']} (EARS literal): {req['ears']}",
        f"Comprobación: {req['comprobacion']}",
        forma_sql(req["comprobacion"], cfg),
        f"Worktree local: {cfg['worktree']}",
        f"Archivos permitidos ({fuente_permitidos}): {', '.join(todos_permitidos)}",
        *[f"Worktree extra {x['ruta']}: {', '.join(x.get('permitidos') or [])} (y git -C en él)" for x in cfg.get("worktrees_extra") or [] if x.get("ruta")],
        f"Presupuesto: {presupuesto}",
        f"Grafo del repo: {grafo(cfg['worktree'])}",
        f"GitHub (gh): {github(cfg['worktree'])}",
        f"Última lección de la línea: {leccion(cfg, estado['linea'])}",
        f"Cola del caparazón: {nota_cola}" if nota_cola else "",
        "Reglas de máquina: escrituras fuera del cerco se bloquean (bloqueo:cerco); cada herramienta deja evento con tokens y coste en la cola "
        "local, que llega al registro cada 60 s y al terminar el turno (si el registro no responde, se avisa y la cola se conserva); "
        f"commits con Chat: {cfg['carpeta']}, Model: <modelo real>, Plan: <plan de tu tarea> y Tarea: <id> en el último párrafo del mensaje, "
        "junto a Co-Authored-By y sin línea en blanco entre ellas."
        + (f" Con un solo plan, Plan: {p['id']}." if len(estado.get('planes_trabajables') or []) < 2 else ""),
        FORMATO_ENTREGA,
    ] if x)
    with comun.cerrojo():
        comun.guardar_estado(estado)
    return estado


def refrescar_trabajo(estado: dict, entrada: dict, cfg: dict, cambiar_si_entregada: bool = False) -> tuple[dict, list[str]]:
    """B12 (lead, 15-sep): el requisito, la tarea y los permitidos vigentes salen del registro, no de la foto guardada en el estado de la
    sesión. Si la tarea ya no se puede trabajar o el plan ya no está abierto, reconstruye el estado. Devuelve el estado y los cambios
    vistos. Lanza comun.RegistroCaido si el registro no responde."""
    plan_id, tarea = (estado.get("plan") or {}).get("id"), estado.get("tarea") or {}
    if estado.get("abortado") or not plan_id or not tarea:
        return estado, []
    detalle = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(plan_id, safe=""))
    plan = detalle.get("plan") or {}
    vigente = next((t for t in detalle.get("tareas") or [] if t.get("id") == tarea.get("id")), None)
    req = next((r for r in detalle.get("requisitos") or [] if vigente and r.get("ref") == vigente.get("req_ref")), None)
    if not vigente or vigente.get("progreso") not in ("pendiente", "trabajando", "devuelta") or not req or plan.get("estado") != "abierto":
        situacion = vigente.get("progreso") if vigente else "no está en el registro"
        if plan.get("estado") != "abierto":
            situacion += f", plan {plan.get('estado')}"
        return construir_estado(entrada, cfg), [f"la tarea {tarea.get('id')} ya no se puede trabajar ({situacion}): el caparazón ha vuelto a leer el registro"]
    # B13 + B14 (lead, 15-sep): con varias tareas trabajables, cada prompt consulta en el registro cuáles están entregadas y pendientes de juicio.
    # Las tareas del plan activo salen del registro (frescas); las de otros planes se conservan del estado.
    trabajables = [t for t in detalle.get("tareas") or [] if es_mia(t, cfg) and t.get("progreso") in PRIORIDAD]
    trabajando, sabidas = [t["id"] for t in trabajables if t["progreso"] == "trabajando"], estado.get("entregadas_pendientes") or []
    if cambiar_si_entregada and len(trabajables) > 1:
        en_juicio, nota = pendientes_de_juicio(cfg, plan_id, trabajando, sabidas, espera=15)
    else:
        en_juicio, nota = (entregas_en_cola(plan_id) | set(sabidas)) & set(trabajando), ""
    lista_plan = [{"id": t["id"], "plan_id": plan_id, "req_ref": t.get("req_ref"), "progreso": t["progreso"], "entregada": t["id"] in en_juicio}
                  for t in trabajables]
    otros = [t for t in estado.get("tareas_trabajables") or [] if t.get("plan_id") != plan_id]
    lista = sorted(lista_plan + otros, key=lambda t: (t["entregada"], t.get("plan_id", ""), PRIORIDAD[t["progreso"]], t["id"]))
    # B19: descubrir planes nuevos abiertos después del SessionStart
    planes_conocidos = {(t.get("plan_id") or plan_id) for t in lista}
    planes_nuevos: list[dict] = []
    nuevos_perms: list[str] = []
    with contextlib.suppress(comun.RegistroCaido):
        prefijo = f"IA:{cfg['carpeta']}:"
        fijado = cfg.get("plan_id")
        for p_item in comun.leer_registro(cfg, "/planes?limite=500")["planes"]:
            if (p_item["id"] not in planes_conocidos and p_item.get("tareas") and p_item["estado"] == "abierto"
                    and str(p_item.get("dueno") or "").startswith("H:")
                    and (p_item["id"] == fijado if fijado else p_item["id"].startswith(cfg.get("prefijo_planes", "")))):
                with contextlib.suppress(comun.RegistroCaido):
                    det_n = comun.leer_registro(cfg, "/plan/" + urllib.parse.quote(p_item["id"], safe=""))
                    mias_n = [t for t in det_n.get("tareas") or [] if str(t.get("agente") or "").startswith(prefijo)
                              and t.get("progreso") in PRIORIDAD]
                    if mias_n:
                        for t in mias_n:
                            lista.append({"id": t["id"], "plan_id": p_item["id"], "req_ref": t.get("req_ref"),
                                          "progreso": t["progreso"], "entregada": False})
                        planes_nuevos.append({k: det_n["plan"].get(k) for k in ("id", "que", "estado", "dueno")})
                        perm_n, _ = resolver_permitidos(det_n["plan"], cfg)
                        nuevos_perms.extend(px for px in perm_n if px not in nuevos_perms)
    if planes_nuevos:
        lista.sort(key=lambda t: (t["entregada"], t.get("plan_id", ""), PRIORIDAD[t["progreso"]], t["id"]))
    if cambiar_si_entregada and tarea.get("id") in en_juicio and any(not t["entregada"] for t in lista):
        # B13.3 (lead, 15-sep): la tarea del estado ya está entregada y pendiente de juicio; el prompt pasa a la siguiente trabajable.
        nuevo = construir_estado(entrada, cfg)
        return nuevo, [x for x in (nota, f"la tarea {tarea.get('id')} está entregada y pendiente de juicio: el caparazón pasa a la tarea "
                                         f"{(nuevo.get('tarea') or {}).get('id')}") if x]
    anterior, cambios = estado.get("requisito") or {}, [nota] if nota else []
    if req.get("comprobacion") != anterior.get("comprobacion"):
        cambios.append(f"la comprobación de {req.get('ref')} cambió en el registro: ahora es `{req.get('comprobacion')}` "
                       f"(antes `{anterior.get('comprobacion')}`)")
    if req.get("ears") != anterior.get("ears"):
        cambios.append(f"el texto EARS de {req.get('ref')} cambió en el registro")
    permitidos, fuente = resolver_permitidos(plan, cfg)
    if permitidos and permitidos != estado.get("permitidos"):
        cambios.append(f"los archivos permitidos cambiaron en el registro: {', '.join(permitidos)}")
    if planes_nuevos:
        cambios.append(f"planes nuevos descubiertos: {', '.join(p['id'] for p in planes_nuevos)}")

    def aplicar(e: dict) -> None:
        e.update(requisito=req, tarea={**(e.get("tarea") or {}), "progreso": vigente.get("progreso")}, requisito_confirmado=comun.ahora(),
                 tareas_trabajables=lista, entregadas_pendientes=sorted(en_juicio))
        if planes_nuevos:
            e["planes_trabajables"] = list(e.get("planes_trabajables") or []) + planes_nuevos
        multi = len(e.get("planes_trabajables") or []) > 1
        if multi or nuevos_perms:
            union = list(e.get("permitidos") or [])
            for px in (permitidos or []):
                if px not in union:
                    union.append(px)
            for px in nuevos_perms:
                if px not in union:
                    union.append(px)
            e.update(permitidos=union, permitidos_fuente=fuente + " (unión multi-plan)")
        elif permitidos:
            e.update(permitidos=permitidos, permitidos_fuente=fuente)

    return comun.actualizar_estado(estado["session_id"], aplicar), cambios


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    estado = construir_estado(entrada, cfg)
    if estado["abortado"]:
        aviso = (f"Caparazón ABORTADO — túnel 7101 caído: `{comun.comando_tunel(cfg)}`\n{estado['motivo']}"
                 if comun.tipo_aborto(estado) == "registro_caido"
                 else f"Caparazón sin tarea: {comun.aviso_sin_tarea(estado, cfg)}")
    else:
        aviso = f"Caparazón: {estado['plan']['id']} · tarea {estado['tarea']['id']} · cerco {', '.join(estado['permitidos'])}"
    if estado.get("nota_cola"):
        aviso += f"\n{estado['nota_cola']}"
    comun.actualizar_estado(estado["session_id"], lambda e: e.update(brief_entregado=comun.ahora(), brief_via="SessionStart"))
    comun.salir_json({"systemMessage": aviso, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": estado["brief"]}})


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m, "hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": f"BRIEF CAPARAZÓN ABORTADO: {m}"}}))
