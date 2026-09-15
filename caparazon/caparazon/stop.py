"""Stop (B6): no se cierra con escrituras sin un bloque ENTREGA validado contra la salida real. Al entregar: lección para la KB,
tarea_entregada + evidencia y aviso a 07 comprobado. Cada Stop envía la cola; si el registro no responde, avisa y la conserva."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime

import comun
from brief import FORMATO_ENTREGA

MARCA_ENTREGA = re.compile(r"(?m)^[ \t>#*_-]*ENTREGA\b")
MARCA_PREGUNTA = re.compile(r"(?m)^[ \t>#*_-]*(PREGUNTA|BLOQUEADO)\s*:\s*(.+)$")
MARCA_LECCION = re.compile(r"(?mi)^[ \t>#*_-]*LECCI[ÓO]N\s*:\s*(.+)$")


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


def validar(bloque: str, estado: dict):
    fallos = []
    comprobacion = estado["requisito"]["comprobacion"]
    orden = suelto(ejecutable(comprobacion))
    if orden not in suelto(bloque):
        fallos.append(f"el bloque ENTREGA no cita la comprobación literal `{comprobacion}`")
    ejecuciones = [c for c in estado.get("comandos", []) if orden in suelto(c["comando"])]
    linea_salida = None
    if not ejecuciones:
        fallos.append(f"la comprobación `{ejecutable(comprobacion)}` no se ha ejecutado en esta sesión con Bash/PowerShell")
    else:
        ultima = ejecuciones[-1]
        if ultima.get("interrumpido"):
            fallos.append("la última ejecución de la comprobación se interrumpió")
        lineas_bloque = {re.sub(r"^(salida|output)\s*:\s*", "", x.strip(), flags=re.I) for x in bloque.splitlines()}
        candidatas = [l.strip() for l in ultima["salida"].splitlines() if l.strip()][-15:]
        linea_salida = next((l for l in reversed(candidatas) if (l in bloque if len(l) >= 10 else l in lineas_bloque)), None)
        if not linea_salida:
            fallos.append("la salida pegada no es la salida real: ninguna de las últimas líneas de la última ejecución aparece literal en el bloque")
    leccion = MARCA_LECCION.search(bloque)
    if not leccion:
        fallos.append("falta la línea 'LECCIÓN: ...' (se guarda en la KB con clave leccion-linea-<T>-<fecha>)")
    if not estado.get("aviso_07"):
        fallos.append("falta el aviso a 07-verificador: send_message a su sesión con el bloque ENTREGA (list_sessions para encontrarla)")
    return fallos, (leccion.group(1).strip() if leccion else None), linea_salida


def enviar(cfg: dict, sid: str) -> str:
    """Envía la cola al registro y a la KB. Devuelve '' si llegó todo, o el aviso visible si no."""
    r = comun.vaciar(cfg, sid, "stop", esperar=30)
    return "" if r["estado"] in ("ok", "vacia") else comun.texto_fallo_cola(cfg, r)


def terminar(mensaje: str = "") -> None:
    if mensaje:
        comun.salir_json({"systemMessage": mensaje})
    sys.exit(0)


def cerrar_incompleta(cfg: dict, estado: dict, motivo: str) -> None:
    """Con stop_hook_active=true Claude Code ya continuó por un bloqueo: volver a bloquear solo encadena turnos (la doc de hooks lo desaconseja)."""
    tarea = estado["tarea"]["id"]
    comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "entrega_incompleta", estado["plan"]["id"],
                                                         f"tarea {tarea} cerrada tras un bloqueo previo sin ENTREGA válida: {motivo}"))
    aviso = enviar(cfg, estado["session_id"])
    donde = "registrado en SYPNOSE" if not aviso else "en la cola local"
    terminar(f"CIERRE SIN ENTREGA VÁLIDA: la tarea {tarea} queda incompleta (bloqueo:entrega_incompleta {donde}). {motivo}"
             + (f"\n{aviso}" if aviso else ""))


def rechazar(cfg: dict, estado: dict, motivo: str, primero: bool) -> None:
    if not primero:
        cerrar_incompleta(cfg, estado, motivo)
    comun.encolar(estado["session_id"], comun.ops_bloqueo(estado["actor"], "entrega", estado["plan"]["id"], motivo))
    aviso = enviar(cfg, estado["session_id"])
    if aviso:
        sys.stdout.write(json.dumps({"systemMessage": aviso}, ensure_ascii=False))
    nota = " bloqueo:entrega registrado en SYPNOSE." if not aviso else ""
    comun.bloquear(f"CIERRE IMPEDIDO: {motivo}.{nota}\n{FORMATO_ENTREGA}")


def entregar(cfg: dict, estado: dict, bloque: str, primero: bool) -> None:
    fallos, leccion, linea_salida = validar(bloque, estado)
    if fallos:
        rechazar(cfg, estado, "ENTREGA rechazada: " + "; ".join(fallos), primero)
    sid, plan_id, actor, tarea = estado["session_id"], estado["plan"]["id"], estado["actor"], estado["tarea"]
    comprobacion = estado["requisito"]["comprobacion"]
    clave = f"leccion-linea-{estado.get('linea') or 'SIN-LINEA'}-{datetime.now():%d%m%y-%H%M}"
    cuando = comun.ahora()
    valor = (f"{leccion}\n\nPlan {plan_id} · tarea {tarea['id']} ({tarea['req_ref']}) · {actor} · {cuando}\n"
             f"Comprobación: {comprobacion}\nSalida real: {linea_salida}")
    comun.encolar(sid, [
        comun.op_kb(cfg, clave, valor),
        comun.op_evento(actor, "tarea_entregada", f"tarea {tarea['id']} {tarea['req_ref']}: `{comprobacion}` → {linea_salida} · lección {clave}", plan_id, cuando),
        {"op": "evidencia", "plan_id": plan_id, "nodo_id": None, "fuente": f"entrega:{cfg['carpeta']}",
         "dice": f"evento {{evento}} ({cuando}) {actor}: `{comprobacion}` → {linea_salida}"},
        comun.op_evento(actor, "leccion_guardada", f"KB {cfg['kb_proyecto']}/{clave}", plan_id, cuando),
        comun.op_evento(actor, "aviso_verificador", f"send_message a {cfg['verificador']} ({estado['aviso_07']['cuando']})", plan_id, cuando),
    ])
    comun.actualizar_estado(sid, lambda e: e.setdefault("entregas", []).append({"cuando": cuando, "huella": huella(bloque), "kb_clave": clave}))
    aviso = enviar(cfg, sid)
    terminar(f"ENTREGA registrada en SYPNOSE · lección {clave}" if not aviso else f"ENTREGA en la cola local · lección {clave}\n{aviso}")


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    sid = entrada.get("session_id") or "sin-sesion"
    estado = comun.leer_estado(sid)
    texto = entrada.get("last_assistant_message") or ""
    primero = not entrada.get("stop_hook_active")
    if estado is None or estado.get("abortado"):
        terminar(enviar(cfg, sid))
    marca = MARCA_ENTREGA.search(texto)
    if marca:
        bloque = texto[marca.start():]
        if not any(x.get("huella") == huella(bloque) for x in estado.get("entregas", [])):
            entregar(cfg, estado, bloque, primero)
        terminar(enviar(cfg, sid))
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
        aviso = enviar(cfg, sid)
        terminar(f"Cierre sin ENTREGA ({pregunta.group(1)}) registrado para Carlos como pregunta_humano." + (f"\n{aviso}" if aviso else ""))
    terminar(enviar(cfg, sid))


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m}))
