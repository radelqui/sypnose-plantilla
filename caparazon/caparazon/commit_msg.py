"""git commit-msg (B5): Chat:, Model:, Plan: y Tarea: van en el último párrafo del mensaje, junto a Co-Authored-By, para que git los lea
como trailers (`git log --format=%(trailers)`). Si llegan en párrafos finales separados (el harness añade Co-Authored-By aparte), se unen
en un solo bloque reescribiendo el mensaje. Si faltan o están en otro sitio, se rechaza el commit y se anota bloqueo:commit-msg en la cola."""
from __future__ import annotations

import os
import re
import subprocess
import sys

import comun

CAMPOS = ("Chat", "Model", "Plan", "Tarea")
TRAILER = re.compile(r"^(?:Chat|Model|Plan|Tarea|(?i:co-authored-by|signed-off-by)):[ \t]*\S")


def parrafos(lineas: list[str]) -> list[list[str]]:
    res, actual = [], []
    for linea in lineas:
        if linea.strip():
            actual.append(linea)
        elif actual:
            res.append(actual)
            actual = []
    if actual:
        res.append(actual)
    return res


def normalizar(texto: str) -> tuple[str, list[str], list[str]]:
    """(mensaje con los párrafos finales de trailers unidos en uno, líneas de ese bloque final, líneas del resto del mensaje)."""
    lineas = texto.splitlines()
    fin = len(lineas)
    while fin and (not lineas[fin - 1].strip() or lineas[fin - 1].startswith("#")):
        fin -= 1
    cola = lineas[fin:]
    bloques = parrafos(lineas[:fin])
    trailers: list[str] = []
    while len(bloques) > 1 and all(TRAILER.match(linea) for linea in bloques[-1]):
        trailers = bloques.pop() + trailers
    partes = ["\n".join(b) for b in bloques] + (["\n".join(trailers)] if trailers else [])
    mensaje = "\n\n".join(partes) + "\n" + ("\n".join(cola) + "\n" if cola else "")
    return mensaje, trailers, [linea for b in bloques for linea in b]


def trailers_git(mensaje: str) -> set[str] | None:
    try:
        p = subprocess.run(["git", "interpret-trailers", "--parse"], input=mensaje, capture_output=True, text=True, encoding="utf-8",
                           timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    return {linea.split(":", 1)[0].strip() for linea in p.stdout.splitlines() if ":" in linea}


def main() -> None:
    cfg = comun.config()
    ruta = sys.argv[1]
    with open(ruta, encoding="utf-8", errors="replace") as f:
        original = f.read()
    mensaje, bloque, resto = normalizar(original)
    campos = {}
    for linea in bloque:
        m = re.match(r"^(Chat|Model|Plan|Tarea):[ \t]*(.*?)\s*$", linea)
        if m:
            campos[m.group(1)] = m.group(2)
    fuera_de_sitio = {m.group(1) for linea in resto[1:] if (m := re.match(r"^(Chat|Model|Plan|Tarea):", linea))}
    estado = comun.ultimo_estado() or {}
    plan_vigente = None if estado.get("abortado") else (estado.get("plan") or {}).get("id")
    tarea = estado.get("tarea") if plan_vigente else None
    fallos = []
    for k in CAMPOS:
        if not campos.get(k):
            fallos.append(f"'{k}:' tiene que ir en el último párrafo, junto a Co-Authored-By y sin línea en blanco" if k in fuera_de_sitio
                          else f"falta '{k}:' al pie")
    for k in CAMPOS:
        veces = sum(1 for linea in resto[1:] + bloque if re.match(rf"^{k}:", linea))
        if veces > 1:
            fallos.append(f"'{k}:' aparece {veces} veces; tiene que aparecer una sola vez")
    if campos.get("Chat") and campos["Chat"] != cfg["carpeta"]:
        fallos.append(f"Chat: debe ser {cfg['carpeta']} (llegó '{campos['Chat']}')")
    if campos.get("Model") and not re.fullmatch(r"claude-[a-z0-9.-]+", campos["Model"]):
        fallos.append(f"Model: debe ser el id del modelo, p. ej. claude-sonnet-5 (llegó '{campos['Model']}')")
    planes_ok = [p["id"] for p in estado.get("planes_trabajables") or []] if not estado.get("abortado") else []
    if not planes_ok and plan_vigente:
        planes_ok = [plan_vigente]
    if planes_ok and campos.get("Plan") and campos["Plan"] not in planes_ok:
        fallos.append(f"Plan: debe ser uno de {', '.join(planes_ok)} (llegó '{campos['Plan']}')")
    tareas_ok = {str(t["id"]) for t in estado.get("tareas_trabajables") or []} if not estado.get("abortado") else set()
    if tarea:
        tareas_ok |= {str(tarea["id"]), f"{plan_vigente}/{tarea['req_ref']}"}
    if tareas_ok and campos.get("Tarea") and campos["Tarea"] not in tareas_ok:
        fallos.append(f"Tarea: debe ser una de las trabajables {', '.join(sorted(tareas_ok))} (llegó '{campos['Tarea']}')")
    if not fallos:
        reconocidos = trailers_git(mensaje)
        if reconocidos is not None and not set(CAMPOS) <= reconocidos:
            fallos.append(f"git no lee {sorted(set(CAMPOS) - reconocidos)} como trailers del último párrafo")
    if not fallos:
        if mensaje != original:
            with open(ruta, "w", encoding="utf-8", newline="\n") as f:
                f.write(mensaje)
        sys.exit(0)
    asunto = (resto[0] if resto else "")[:120]
    actor = estado.get("actor") or comun.actor_de(cfg, None)
    comun.encolar(estado.get("session_id") or "sin-sesion",
                  comun.ops_bloqueo(actor, "commit-msg", comun.plan_de(estado, cfg),
                                    f"commit rechazado en {os.getcwd()} ('{asunto}'): " + "; ".join(fallos)))
    sys.stderr.write("COMMIT RECHAZADO por el caparazón:\n - " + "\n - ".join(fallos)
                     + "\nPie obligatorio en el último párrafo del mensaje, sin línea en blanco entre sus líneas:\n"
                     + f"  Chat: {cfg['carpeta']}\n  Model: <modelo real>\n  Plan: {plan_vigente or '<plan abierto>'}\n"
                     + f"  Tarea: {tarea['id'] if tarea else '<id de tarea>'}\n  Co-Authored-By: … (si se añade, en el mismo párrafo)\n"
                     + "bloqueo:commit-msg anotado en la cola del caparazón; llega al registro SYPNOSE en el siguiente envío.\n")
    sys.exit(1)


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: (sys.stderr.write(f"COMMIT RECHAZADO: {m}\n"), sys.exit(1)))
