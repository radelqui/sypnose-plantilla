"""Stop (B6): no se cierra con escrituras sin un bloque ENTREGA validado contra la salida real. Al entregar: lección para la KB,
tarea_entregada + evidencia y aviso a 07 comprobado. Cada Stop envía la cola; si el registro no responde, avisa y la conserva."""
from __future__ import annotations

import hashlib
import json
import operator
import os
import re
import shlex
import sys
from datetime import datetime

import brief
import cerco
import comun
from brief import FORMATO_ENTREGA

MARCA_ENTREGA = re.compile(r"(?m)^[ \t>#*_-]*ENTREGA\b")
MARCA_PREGUNTA = re.compile(r"(?m)^[ \t>#*_-]*(PREGUNTA|BLOQUEADO)\s*:\s*(.+)$")
MARCA_LECCION = re.compile(r"(?mi)^[ \t>#*_-]*LECCI[ÓO]N\s*:\s*(.+)$")
MARCA_TAREA = re.compile(r"(?mi)^[ \t>#*_-]*Tarea\s*:\s*(\d+)\s*$")
MARCA_PLAN = re.compile(r"(?mi)^[ \t>#*_-]*Plan\s*:\s*([\w-]+)\s*$")


def compacto(texto: str) -> str:
    return " ".join(texto.split())


def huella(texto: str) -> str:
    return hashlib.sha256(compacto(texto).encode("utf-8")).hexdigest()[:16]


FLECHA = re.compile(r"\s*(→|->)\s*")


def ejecutable(comprobacion: str) -> str:
    """'SELECT … → ≥1' se ejecuta como 'SELECT …': lo que va tras la flecha es el resultado esperado."""
    return FLECHA.split(comprobacion, maxsplit=1)[0].strip() or comprobacion


def suelto(texto: str) -> str:
    """Sin espacios, comillas ni barras: la shell puede llevar el texto de la comprobación con otro entrecomillado."""
    return re.sub(r"[\s'\"`\\]", "", texto)


FALLO = re.compile(r"(?im)\b[1-9]\d*\s+(?:failed|errors?|failures?)\b|^\s*(?:FAILED|FAIL|ERROR)\b|^\s*error\s*:"
                   r"|\b(?:parse|runtime|syntax|fatal)\s+error\b|Traceback \(most recent call last\)|\bexit code\s+[1-9]\d*|\bno tests ran\b")
COMPARADOR = re.compile(r"^(≥|>=|≤|<=|==|=|>|<)?\s*(-?\d+(?:[.,]\d+)?)$")
OPERACIONES = {"≥": operator.ge, ">=": operator.ge, "≤": operator.le, "<=": operator.le, ">": operator.gt, "<": operator.lt,
               "=": operator.eq, "==": operator.eq, None: operator.eq}
RESUMEN = re.compile(r"(?i)\b\d+\s+(?:passed|failed|errors?|skipped|xfailed|xpassed|deselected)\b|\bno tests ran\b|^\s*Ran \d+ tests? in\b|^\s*(?:OK|FAILED)\b")
MAX_SALIDA_EVIDENCIA = 3000
REGISTRADO = ("ok", "vacia", "kb_pendiente")


def resumen_de(salida: str) -> str | None:
    """Última línea de resumen de la salida (pytest 'N passed in …', unittest 'Ran N tests' u 'OK'), si la trae."""
    return next((l.strip() for l in reversed(salida.splitlines()) if RESUMEN.search(l)), None)


def esperado_de(comprobacion: str) -> str | None:
    partes = FLECHA.split(comprobacion, maxsplit=1)
    return partes[2].strip() if len(partes) == 3 and partes[2].strip() else None


def cumple_esperado(esperado: str, salida: str) -> str | None:
    """None si la salida real cumple lo esperado tras la flecha; si no, el motivo."""
    m = COMPARADOR.match(esperado)
    if not m:
        return None if compacto(esperado).lower() in compacto(salida).lower() else f"la salida no muestra lo esperado «{esperado}»"
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]
    numeros = [l for l in lineas if re.fullmatch(r"-?\d+(?:[.,]\d+)?", l)]
    if len(numeros) != 1 or len(lineas) - len(numeros) > 1:
        return (f"la salida completa no es un único valor que comparar con lo esperado {esperado} "
                f"({len(numeros)} valores numéricos en {len(lineas)} líneas)")
    observado = float(numeros[0].replace(",", "."))
    if OPERACIONES[m.group(1)](observado, float(m.group(2).replace(",", "."))):
        return None
    return f"el resultado observado {numeros[0]} no cumple lo esperado {esperado}"


PUNTUACION = re.compile(r"[;&|<>]+")
CD = re.compile(r"""(?is)^\s*(?:cd|set-location|pushd)\s+("[^"]*"|'[^']*'|\S+)\s*&&\s*(.+)$""")


def _tokens(texto: str) -> list[str] | None:
    try:
        lx = shlex.shlex(texto, posix=True, punctuation_chars=";&|<>")
        lx.whitespace_split = True
        return list(lx)
    except ValueError:
        return None


SQLITE_OPCIONES = {"-readonly", "-header", "-noheader", "-csv", "-list", "-line", "-batch", "-bail", "-json", "-box", "-column",
                   "-table", "-markdown", "-quote", "-safe"}
SSH_OPCION_O = re.compile(r"(?i)(BatchMode=yes|ConnectTimeout=\d+|ServerAliveInterval=\d+|ServerAliveCountMax=\d+)")


def _consulta_sqlite(toks: list[str] | None, consulta: str, bd_del_registro) -> str | None:
    """None si toks es `sqlite3 [opciones de formato] <bd del registro> "<consulta>"`; si no, por qué no cuenta."""
    if not toks or len(toks) < 3 or os.path.basename(toks[0]).lower() not in ("sqlite3", "sqlite3.exe"):
        return "no es `sqlite3 <bd del registro> \"<consulta>\"`"
    if any(PUNTUACION.fullmatch(t) for t in toks) or any(t not in SQLITE_OPCIONES for t in toks[1:-2]):
        return "sqlite3 lleva opciones o comandos que no están permitidos"
    if suelto(toks[-1]) != suelto(consulta):
        return "no es la consulta tal cual"
    if not bd_del_registro(toks[-2]):
        return f"la base de datos {toks[-2]} no es la del registro configurado"
    return None


def _ssh_al_registro(toks: list[str], cfg: dict) -> str | None:
    """None si toks es `ssh [-i clave] [-p puerto del registro] [-o BatchMode/ConnectTimeout/ServerAlive…] [-q] [-T] <destino> "<remoto>"`.
    Otras opciones (-o HostName, -J, -F…) podrían llevar la conexión a otro servidor sin cambiar el destino escrito."""
    s = cfg.get("ssh") or {}
    i, fin = 1, len(toks) - 2
    while i < fin:
        opcion, valor = toks[i], toks[i + 1] if i + 1 < fin else None
        if opcion in ("-q", "-T"):
            i += 1
        elif opcion == "-i" and valor is not None:
            i += 2
        elif opcion == "-p" and valor == str(s.get("puerto")):
            i += 2
        elif opcion == "-o" and valor is not None and SSH_OPCION_O.fullmatch(valor):
            i += 2
        else:
            return f"ssh lleva la opción {opcion} {valor or ''}, que no está permitida".replace("  ", " ")
    if len(toks) < 3 or toks[-2] != s.get("destino"):
        return f"ssh no va al servidor del registro ({s.get('destino')})"
    return None


def _bd_remota_del_registro(bd: str, cfg: dict) -> bool:
    """Compara con '~' expandido al home del destino en los dos lados: `~/sypnose-f1/registry.db` y `/home/sypnose/…` son la misma BD."""
    s = cfg.get("ssh") or {}
    destino, esperada = str(s.get("destino") or ""), str(s.get("db") or "")
    return bool(esperada) and comun.ruta_remota(bd, destino) == comun.ruta_remota(esperada, destino)


def forma_pura(comando: str, comprobacion: str, cwd: str | None, worktree: str, cfg: dict) -> str | None:
    """None si el comando es exactamente la comprobación (solo se admite `cd <worktree> &&` delante; una consulta SQL va como
    `sqlite3 <bd> "<consulta>"`, directa o por ssh); si no, por qué no cuenta. Un filtro, un `; echo`, una sustitución o un echo del texto
    de la comprobación falsearían la salida que se valida."""
    orden = ejecutable(comprobacion)
    base, resto = cwd or worktree, comando.strip()
    m = CD.match(resto)
    if m:
        base, resto = cerco.norm(m.group(1).strip("\"'"), base), m.group(2)
    toks = _tokens(resto)
    if toks is None:
        return "el comando no se puede leer"
    if any(PUNTUACION.fullmatch(t) for t in toks):
        return "lleva tuberías, ';', '&&'/'||' o redirecciones"
    if any("$(" in t or "`" in t or "${" in t for t in toks):
        return "lleva sustituciones ($(…), `…` o ${…})"
    if re.match(r"(?is)^\s*(select|with)\b", orden):
        if toks and os.path.basename(toks[0]).lower() in ("ssh", "ssh.exe"):
            return _ssh_al_registro(toks, cfg) or _consulta_sqlite(_tokens(toks[-1]), orden, lambda bd: _bd_remota_del_registro(bd, cfg))
        escritura = str(cfg.get("escritura") or "")
        if escritura.startswith("sqlite:"):
            local = cerco.norm(escritura[len("sqlite:"):], base)
            return _consulta_sqlite(toks, orden, lambda bd: cerco.norm(bd, base) == local)
        s = cfg.get("ssh") or {}
        return f"la consulta va contra el registro por ssh: ssh {s.get('destino')} \"sqlite3 {s.get('db')} \\\"<consulta>\\\"\""
    esperados = _tokens(orden) or []
    if [suelto(t) for t in toks] != [suelto(t) for t in esperados]:
        return "no es exactamente la comprobación"
    if not cerco.dentro(cerco.norm(base, base), cerco.norm(worktree, worktree)):
        return f"se ejecutó fuera del worktree ({base})"
    return None


def validar(bloque: str, estado: dict, cfg: dict):
    fallos = []
    comprobacion = estado["requisito"]["comprobacion"]
    orden = suelto(ejecutable(comprobacion))
    if orden not in suelto(bloque):
        fallos.append(f"el bloque ENTREGA no cita la comprobación literal `{comprobacion}`")
    intentos = [c for c in estado.get("comandos", []) if orden in suelto(c["comando"])]
    ejecuciones = [c for c in intentos if forma_pura(c["comando"], comprobacion, c.get("cwd"), estado["worktree"], cfg) is None]
    if intentos and (not ejecuciones or intentos[-1] is not ejecuciones[-1]):
        motivo = forma_pura(intentos[-1]["comando"], comprobacion, intentos[-1].get("cwd"), estado["worktree"], cfg)
        fallos.append(f"la última ejecución de la comprobación («{intentos[-1]['comando'][:160]}») no cuenta: {motivo}. Tiene que ir tal cual "
                      "(solo se admite delante 'cd <worktree> &&'), sin tuberías, ';', '&&'/'||' añadidos, echo, redirecciones ni sustituciones")
    linea_salida = None
    if not ejecuciones:
        fallos.append(f"la comprobación `{ejecutable(comprobacion)}` no se ha ejecutado tal cual en esta sesión con Bash/PowerShell")
    else:
        ultima = ejecuciones[-1]
        if ultima.get("interrumpido"):
            fallos.append("la última ejecución de la comprobación se interrumpió")
        if ultima.get("exit_code") not in (0, None):
            fallos.append(f"la última ejecución de la comprobación terminó con exit code {ultima['exit_code']}")
        marca = FALLO.search(ultima["salida"])
        if marca:
            fallos.append(f"la salida real de la comprobación indica fallo («{marca.group(0).strip()}»)")
        esperado = esperado_de(comprobacion)
        motivo = cumple_esperado(esperado, ultima["salida"]) if esperado else None
        if motivo:
            fallos.append(motivo)
        lineas_bloque = {re.sub(r"^(salida|output)\s*:\s*", "", x.strip(), flags=re.I) for x in bloque.splitlines()}
        candidatas = [l.strip() for l in ultima["salida"].splitlines() if l.strip()][-15:]
        linea_salida = next((l for l in reversed(candidatas) if (l in bloque if len(l) >= 10 else l in lineas_bloque)), None)
        if not linea_salida:
            fallos.append("la salida pegada no es la salida real: ninguna de las últimas líneas de la última ejecución aparece literal en el bloque")
    leccion = MARCA_LECCION.search(bloque)
    if not leccion:
        fallos.append("falta la línea 'LECCIÓN: ...' (se guarda en la KB con clave leccion-linea-<T>-<fecha>)")
    if not estado.get("aviso_07"):
        fallos.append("falta el aviso a 07-verificador: primero send_message a 07 con la comprobación y su salida, "
                      "después cierra el turno con ENTREGA (list_sessions para encontrar la sesión de 07)")
    return fallos, (leccion.group(1).strip() if leccion else None), linea_salida, (ejecuciones[-1] if ejecuciones else None)


def enviar(cfg: dict, sid: str) -> tuple[str, str]:
    """Envía la cola al registro y a la KB. Devuelve el estado del envío y el aviso visible ('' si llegó todo)."""
    r = comun.vaciar(cfg, sid, "stop", esperar=30)
    return r["estado"], ("" if r["estado"] in ("ok", "vacia") else comun.texto_fallo_cola(cfg, r))


def terminar(mensaje: str = "") -> None:
    if mensaje:
        comun.salir_json({"systemMessage": mensaje})
    sys.exit(0)


def cerrar_incompleta(cfg: dict, estado: dict, motivo: str) -> None:
    """Con stop_hook_active=true Claude Code ya continuó por un bloqueo: volver a bloquear solo encadena turnos (la doc de hooks lo desaconseja)."""
    tarea = estado["tarea"]["id"]
    comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "entrega_incompleta", estado["plan"]["id"],
                                                         f"tarea {tarea} cerrada tras un bloqueo previo sin ENTREGA válida: {motivo}"))
    envio, aviso = enviar(cfg, estado["session_id"])
    donde = "registrado en SYPNOSE" if envio in REGISTRADO else "en la cola local"
    terminar(f"CIERRE SIN ENTREGA VÁLIDA: la tarea {tarea} queda incompleta (bloqueo:entrega_incompleta {donde}). {motivo}"
             + (f"\n{aviso}" if aviso else ""))


def rechazar(cfg: dict, estado: dict, motivo: str, primero: bool, reintentable: bool = False) -> None:
    # B17 (lead, 16-sep): si lo único que falta es el aviso a 07, no cerrar como entrega_incompleta; dejar trabajando para reintentar.
    if not primero and not reintentable:
        cerrar_incompleta(cfg, estado, motivo)
    comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "entrega", estado["plan"]["id"], motivo))
    envio, aviso = enviar(cfg, estado["session_id"])
    if aviso:
        sys.stdout.write(json.dumps({"systemMessage": aviso}, ensure_ascii=False))
    nota = " bloqueo:entrega registrado en SYPNOSE." if envio in REGISTRADO else ""
    comun.bloquear(f"CIERRE IMPEDIDO: {motivo}.{nota}\n{FORMATO_ENTREGA}")


def entregar(cfg: dict, estado: dict, bloque: str, primero: bool, entrada: dict) -> None:
    marca_tarea = MARCA_TAREA.search(bloque)
    marca_plan = MARCA_PLAN.search(bloque)
    objetivo = int(marca_tarea.group(1)) if marca_tarea else estado["tarea"]["id"]
    plan_objetivo = marca_plan.group(1) if marca_plan else None
    # B12 (lead, 15-sep): una entrega es un punto de juicio y se valida contra el requisito vigente del registro, nunca contra la foto.
    try:
        vigente, cambios = brief.refrescar_trabajo(estado, entrada, cfg)
        if (marca_tarea or marca_plan) and not vigente.get("abortado"):
            # B13.2 + B14 (lead, 15-sep): 'Plan: <id>' y 'Tarea: <id>' seleccionan qué plan y tarea entregar.
            vista, motivo = brief.tarea_de_entrega(vigente, objetivo, cfg, plan_id_objetivo=plan_objetivo)
            if motivo:
                rechazar(cfg, estado, f"ENTREGA rechazada: {motivo}", primero)
            vigente = vista
    except comun.RegistroCaido as e:
        comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "registro_caido", estado["plan"]["id"],
                                                             f"ENTREGA de la tarea {objetivo} sin confirmar la comprobación vigente: {e}"))
        rechazar(cfg, estado, "no se pudo confirmar la comprobación vigente: registro caído; reintenta la ENTREGA cuando vuelva", primero)
    if vigente.get("abortado") or (vigente.get("tarea") or {}).get("id") != objetivo:
        rechazar(cfg, estado, "ENTREGA rechazada: " + "; ".join(cambios or [f"la tarea {objetivo} ya no está abierta en el registro"]), primero)
    estado = vigente
    fallos, leccion, linea_salida, ultima = validar(bloque, estado, cfg)
    if fallos:
        # B17: si el único fallo es la falta de aviso a 07, la tarea se queda trabajando para reintentar en el siguiente turno.
        solo_aviso = len(fallos) == 1 and "falta el aviso a 07-verificador" in fallos[0]
        rechazar(cfg, estado, "ENTREGA rechazada: " + "; ".join(cambios + fallos), primero, reintentable=solo_aviso)
    sid, plan_id, actor, tarea = estado["session_id"], estado["plan"]["id"], estado["actor"], estado["tarea"]
    comprobacion = estado["requisito"]["comprobacion"]
    clave = f"leccion-linea-{estado.get('linea') or 'SIN-LINEA'}-{datetime.now():%d%m%y-%H%M}"
    cuando = comun.ahora()
    # La evidencia lleva la línea de resumen si la salida la trae (la pegada puede ser la de puntos) y la salida completa.
    salida = (ultima or {}).get("salida") or ""
    resumen = resumen_de(salida)
    visible = (resumen or linea_salida) + ("" if resumen else " (la salida no trae línea de resumen)")
    completa = (salida if len(salida) <= MAX_SALIDA_EVIDENCIA
                else f"(últimos {MAX_SALIDA_EVIDENCIA} de {len(salida)} caracteres)\n{salida[-MAX_SALIDA_EVIDENCIA:]}")
    valor = (f"{leccion}\n\nPlan {plan_id} · tarea {tarea['id']} ({tarea['req_ref']}) · {actor} · {cuando}\n"
             f"Comprobación: {comprobacion}\nSalida real: {visible}")
    inicio = []
    if tarea.get("progreso") in ("pendiente", "devuelta"):
        # B13.2: la tarea entregada con 'Tarea: <id>' abre su ciclo de trabajo antes de la entrega, para que la detección del juicio pendiente lo vea.
        inicio = [{"op": "tarea_progreso", "tarea_id": tarea["id"], "progreso": "trabajando", "desde": ["pendiente", "devuelta"],
                   "evento": comun.op_evento(actor, "tarea_trabajando", f"tarea {tarea['id']} {tarea['progreso']} → trabajando", plan_id, cuando)}]
    comun.encolar(sid, inicio + [
        comun.op_kb(cfg, clave, valor),
        comun.op_evento(actor, "tarea_entregada", f"tarea {tarea['id']} {tarea['req_ref']}: `{comprobacion}` → {visible} · lección {clave}", plan_id, cuando),
        {"op": "evidencia", "plan_id": plan_id, "nodo_id": None, "fuente": f"entrega:{cfg['carpeta']}",
         "dice": f"evento {{evento}} ({cuando}) {actor}: `{comprobacion}` → {visible} · exit {(ultima or {}).get('exit_code', 0)}\n"
                 f"Salida completa:\n{completa}"},
        {**comun.op_evento(actor, "leccion_guardada", f"KB {cfg['kb_proyecto']}/{clave}", plan_id, cuando), "tras_kb": clave},
        comun.op_evento(actor, "aviso_verificador", f"send_message a {cfg['verificador']} ({estado['aviso_07']['cuando']})", plan_id, cuando),
    ])
    def anotar(e: dict) -> None:
        e.setdefault("entregas", []).append({"cuando": cuando, "huella": huella(bloque), "kb_clave": clave, "tarea_id": tarea["id"]})
        e["entregadas_pendientes"] = sorted(set(e.get("entregadas_pendientes") or []) | {tarea["id"]})

    comun.actualizar_estado(sid, anotar)
    envio, aviso = enviar(cfg, sid)
    terminar((f"ENTREGA registrada en SYPNOSE · lección {clave}" if envio in REGISTRADO else f"ENTREGA en la cola local · lección {clave}")
             + (f"\n{aviso}" if aviso else ""))


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    sid = entrada.get("session_id") or "sin-sesion"
    estado = comun.leer_estado(sid)
    texto = entrada.get("last_assistant_message") or ""
    primero = not entrada.get("stop_hook_active")
    if estado is None or estado.get("abortado"):
        terminar(enviar(cfg, sid)[1])
    marca = MARCA_ENTREGA.search(texto)
    if marca:
        bloque = texto[marca.start():]
        if not any(x.get("huella") == huella(bloque) for x in estado.get("entregas", [])):
            entregar(cfg, estado, bloque, primero, entrada)
        terminar(enviar(cfg, sid)[1])
    ultima_entrega = max((x["cuando"] for x in estado.get("entregas", [])), default="")
    pendientes = [x for x in estado.get("escrituras", []) if x["cuando"] > ultima_entrega]
    if pendientes:
        pregunta = MARCA_PREGUNTA.search(texto)
        if not pregunta:
            rechazar(cfg, estado, f"hay {len(pendientes)} escrituras de la tarea sin bloque ENTREGA (última: {pendientes[-1]['ruta']})", primero)
        huella_pregunta = huella(pregunta.group(2))
        if huella_pregunta not in estado.get("preguntas", []):
            comun.actualizar_estado(sid, lambda e: e.setdefault("preguntas", []).append(huella_pregunta))
            comun.encolar(sid, [comun.op_evento(estado["actor"], "pregunta_humano", f"{pregunta.group(1)}: {pregunta.group(2)}"[:500],
                                                estado["plan"]["id"])])
        _, aviso = enviar(cfg, sid)
        terminar(f"Cierre sin ENTREGA ({pregunta.group(1)}) registrado para Carlos como pregunta_humano." + (f"\n{aviso}" if aviso else ""))
    terminar(enviar(cfg, sid)[1])


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m}))
