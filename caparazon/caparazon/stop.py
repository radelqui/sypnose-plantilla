"""Stop (B6): no se cierra con escrituras sin un bloque ENTREGA validado contra la salida real. Al entregar: lección en la KB,
evento tarea_entregada + evidencia en el registro y aviso a 07-verificador comprobado."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime

import comun
from brief import FORMATO_ENTREGA

MARCA_ENTREGA = re.compile(r"(?m)^[ \t>#*_-]*ENTREGA\b")
MARCA_PREGUNTA = re.compile(r"(?m)^[ \t>#*_-]*(PREGUNTA|BLOQUEADO)\s*:\s*(.+)$")
MARCA_LECCION = re.compile(r"(?mi)^[ \t>#*_-]*LECCI[ÓO]N\s*:\s*(.+)$")


def compacto(texto: str) -> str:
    return " ".join(texto.split())


def validar(bloque: str, estado: dict):
    fallos = []
    comprobacion = estado["requisito"]["comprobacion"]
    if compacto(comprobacion) not in compacto(bloque):
        fallos.append(f"el bloque ENTREGA no cita la comprobación literal `{comprobacion}`")
    ejecuciones = [c for c in estado.get("comandos", []) if compacto(comprobacion) in compacto(c["comando"])]
    linea_salida = None
    if not ejecuciones:
        fallos.append(f"la comprobación `{comprobacion}` no se ha ejecutado en esta sesión con Bash/PowerShell")
    else:
        ultima = ejecuciones[-1]
        if ultima.get("interrumpido"):
            fallos.append("la última ejecución de la comprobación se interrumpió")
        lineas = [l.strip() for l in ultima["salida"].splitlines() if len(l.strip()) >= 10][-15:]
        linea_salida = next((l for l in reversed(lineas) if l in bloque), None)
        if not linea_salida:
            fallos.append("la salida pegada no es la salida real: ninguna de las últimas líneas de la última ejecución aparece literal en el bloque")
    leccion = MARCA_LECCION.search(bloque)
    if not leccion:
        fallos.append("falta la línea 'LECCIÓN: ...' (se guarda en la KB con clave leccion-linea-<T>-<fecha>)")
    if not estado.get("aviso_07"):
        fallos.append("falta el aviso a 07-verificador: send_message a su sesión con el bloque ENTREGA (list_sessions para encontrarla)")
    return fallos, (leccion.group(1).strip() if leccion else None), linea_salida


def rechazar(cfg: dict, estado: dict, motivo: str, primero: bool) -> None:
    nota = ""
    if primero:
        try:
            r = comun.emitir(cfg, comun.ops_bloqueo(estado["actor"], "entrega", estado["plan"]["id"], motivo))
            nota = f" Registrado en SYPNOSE: evento {r['resultados'][0]['id']} bloqueo:entrega + evidencia."
        except (comun.RegistroCaido, comun.RegistroRechazo) as e:
            nota = f" (No registrado: {e}.)"
    comun.bloquear(f"CIERRE IMPEDIDO: {motivo}.{nota}\n{FORMATO_ENTREGA}")


def entregar(cfg: dict, estado: dict, bloque: str, huella: str, primero: bool) -> None:
    fallos, leccion, linea_salida = validar(bloque, estado)
    if fallos:
        rechazar(cfg, estado, "ENTREGA rechazada: " + "; ".join(fallos), primero)
    plan_id, actor, tarea = estado["plan"]["id"], estado["actor"], estado["tarea"]
    comprobacion = estado["requisito"]["comprobacion"]
    clave = f"leccion-linea-{estado.get('linea') or 'SIN-LINEA'}-{datetime.now():%d%m%y-%H%M}"
    cuando = comun.ahora()
    valor = (f"{leccion}\n\nPlan {plan_id} · tarea {tarea['id']} ({tarea['req_ref']}) · {actor} · {cuando}\n"
             f"Comprobación: {comprobacion}\nSalida real: {linea_salida}")
    try:
        comun.kb_guardar(cfg, clave, valor)
    except Exception as e:
        nota_registro = ""
        try:
            comun.emitir(cfg, comun.ops_bloqueo(actor, "kb", plan_id, f"entrega de la tarea {tarea['id']} sin lección: KB no responde ({e})"))
        except (comun.RegistroCaido, comun.RegistroRechazo) as e2:
            nota_registro = f" y el registro tampoco ({e2})"
        comun.salir_json({"systemMessage": f"ENTREGA NO REGISTRADA: la KB no responde ({e}){nota_registro}. La tarea sigue sin entregar."})
    ops = [
        comun.op_evento(actor, "tarea_entregada", f"tarea {tarea['id']} {tarea['req_ref']}: `{comprobacion}` → {linea_salida} · lección {clave}", plan_id, cuando),
        {"op": "evidencia", "plan_id": plan_id, "nodo_id": None, "fuente": f"entrega:{cfg['carpeta']}",
         "dice": f"evento {{evento}} ({cuando}) {actor}: `{comprobacion}` → {linea_salida}"},
        comun.op_evento(actor, "leccion_guardada", f"KB {cfg['kb_proyecto']}/{clave}", plan_id, cuando),
        comun.op_evento(actor, "aviso_verificador", f"send_message a {cfg['verificador']} ({estado['aviso_07']['cuando']})", plan_id, cuando),
    ]
    try:
        nota = f"evento {comun.emitir(cfg, ops)['resultados'][0]['id']}"
    except comun.RegistroCaido:
        nota = "en pendientes: el registro cayó al entregar"
    except comun.RegistroRechazo as e:
        nota = f"RECHAZADA por el registro: {e}"

    def anotar(e: dict) -> None:
        e.setdefault("entregas", []).append({"cuando": cuando, "huella": huella, "kb_clave": clave})

    comun.actualizar_estado(estado["session_id"], anotar)
    comun.salir_json({"systemMessage": f"ENTREGA registrada ({nota}) · lección {clave}"})


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    estado = comun.leer_estado(entrada.get("session_id") or "sin-sesion")
    if estado is None or estado.get("abortado"):
        return
    texto = entrada.get("last_assistant_message") or ""
    primero = not entrada.get("stop_hook_active")
    try:
        comun.salud(cfg)
    except comun.RegistroCaido as e:
        comun.guardar_pendientes(comun.ops_bloqueo(estado["actor"], "registro", estado["plan"]["id"],
                                                   f"cierre de la sesión {estado['session_id'][:8]} con el registro caído ({e})"))
        comun.salir_json({"systemMessage": f"REGISTRO SYPNOSE CAÍDO al cerrar: nada de este turno queda registrado como entrega. {e}"})
    marca = MARCA_ENTREGA.search(texto)
    if marca:
        bloque = texto[marca.start():]
        huella = hashlib.sha256(compacto(bloque).encode("utf-8")).hexdigest()[:16]
        if not any(x.get("huella") == huella for x in estado.get("entregas", [])):
            entregar(cfg, estado, bloque, huella, primero)
        return
    ultima_entrega = max((x["cuando"] for x in estado.get("entregas", [])), default="")
    pendientes = [x for x in estado.get("escrituras", []) if x["cuando"] > ultima_entrega]
    if not pendientes:
        return
    pregunta = MARCA_PREGUNTA.search(texto)
    if pregunta:
        try:
            comun.emitir(cfg, [comun.op_evento(estado["actor"], "pregunta_humano", pregunta.group(2)[:500], estado["plan"]["id"])])
        except (comun.RegistroCaido, comun.RegistroRechazo):
            pass
        return
    rechazar(cfg, estado, f"hay {len(pendientes)} escrituras de la tarea sin bloque ENTREGA (última: {pendientes[-1]['ruta']})", primero)


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m}))
