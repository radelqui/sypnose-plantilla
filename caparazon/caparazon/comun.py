"""Caparazón SYPNOSE: configuración, estado de sesión, cola local de eventos y su envío al registro (SSH/sqlite) y a la KB."""
from __future__ import annotations

import base64
import contextlib
import inspect
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
CONFIG = DIR / "config.json"
ESTADO_DIR = DIR / "estado"
COLA_DIR = DIR / "cola"
CERROJO = ESTADO_DIR / ".cerrojo"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

for _flujo in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _flujo.reconfigure(encoding="utf-8")


class RegistroCaido(Exception):
    """El registro (o la KB) no responde: la cola se conserva y se avisa."""


class RegistroRechazo(Exception):
    """El registro respondió pero rechazó la escritura (raíl o error de datos)."""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def leer_stdin() -> dict:
    datos = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    return json.loads(datos) if datos.strip() else {}


def config() -> dict:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["registro_url"] = (os.environ.get("SYPNOSE_REGISTRO_URL") or cfg.get("registro_url") or "http://127.0.0.1:7101").rstrip("/")
    cfg["kb_url"] = (os.environ.get("SYPNOSE_KB_URL") or cfg.get("kb_url") or "http://127.0.0.1:18791").rstrip("/")
    cfg["escritura"] = os.environ.get("SYPNOSE_REGISTRO_ESCRITURA") or cfg.get("escritura") or "ssh"
    return cfg


def modelo_limpio(modelo: str | None) -> str | None:
    """Id de modelo sin sufijo [..]; None si no es un id real (p. ej. '<synthetic>' de los mensajes de error del CLI)."""
    if not modelo:
        return None
    limpio = re.sub(r"\[.*?\]$", "", str(modelo)).strip()
    return limpio if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]*", limpio) else None


def actor_de(cfg: dict, modelo: str | None) -> str:
    return os.environ.get("SYPNOSE_ACTOR") or f"IA:{cfg['carpeta']}:{modelo or 'desconocido'}"


def comando_tunel(cfg: dict) -> str:
    s = cfg["ssh"]
    return (f"ssh -N -i {s['clave']} -p {s['puerto']} -L 7101:127.0.0.1:7101 -L 18791:127.0.0.1:18791 "
            f"-L 18793:127.0.0.1:18793 {s['destino']}")


def plan_de(estado: dict | None, cfg: dict) -> str | None:
    return ((estado or {}).get("plan") or {}).get("id") or cfg.get("plan_id")


# ── salida de hooks ──────────────────────────────────────────────────────────

def salir_json(obj: dict, codigo: int = 0) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()
    sys.exit(codigo)


def bloquear(mensaje: str) -> None:
    sys.stderr.write(mensaje.rstrip() + "\n")
    sys.stderr.flush()
    sys.exit(2)


def ejecutar(main, al_fallar) -> None:
    """Un fallo inesperado del hook no puede pasar en silencio: se aplica al_fallar(mensaje)."""
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        al_fallar(f"CAPARAZÓN FALLÓ ({Path(sys.argv[0]).name}): {type(e).__name__}: {e}")


# ── estado por sesión ────────────────────────────────────────────────────────

def _cerrojo_fichero(ruta: Path, espera: float, caducidad: float):
    fin = time.monotonic() + espera
    while True:
        try:
            return os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            with contextlib.suppress(FileNotFoundError):
                if time.time() - ruta.stat().st_mtime > caducidad:
                    ruta.unlink(missing_ok=True)
                    continue
            if time.monotonic() >= fin:
                return None
            time.sleep(0.05)


@contextlib.contextmanager
def cerrojo(espera: float = 15.0):
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    fd = _cerrojo_fichero(CERROJO, espera, 60)
    if fd is None:
        raise TimeoutError("cerrojo del caparazón ocupado")
    try:
        yield
    finally:
        os.close(fd)
        CERROJO.unlink(missing_ok=True)


def nombre_seguro(session_id: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "sin-sesion")


def ruta_estado(session_id: str) -> Path:
    return ESTADO_DIR / (nombre_seguro(session_id) + ".json")


def leer_estado(session_id: str) -> dict | None:
    p = ruta_estado(session_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _escribir_json(p: Path, datos: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def guardar_estado(estado: dict) -> None:
    _escribir_json(ruta_estado(estado["session_id"]), estado)


def actualizar_estado(session_id: str, cambio) -> dict:
    with cerrojo():
        estado = leer_estado(session_id)
        cambio(estado)
        guardar_estado(estado)
    return estado


def ultimo_estado() -> dict | None:
    if not ESTADO_DIR.exists():
        return None
    ficheros = sorted(ESTADO_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return json.loads(ficheros[0].read_text(encoding="utf-8")) if ficheros else None


def asegurar_estado(entrada: dict, cfg: dict) -> dict:
    estado = leer_estado(entrada.get("session_id") or "sin-sesion")
    if estado is None:
        import brief
        estado = brief.construir_estado(entrada, cfg)
    return estado


# ── registro SYPNOSE ─────────────────────────────────────────────────────────

_ABRIDOR = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(url: str, metodo: str = "GET", cuerpo: dict | None = None, espera: float = 6.0):
    datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    with _ABRIDOR.open(req, timeout=espera) as r:
        return json.loads(r.read().decode("utf-8"))


def salud(cfg: dict) -> dict:
    url = cfg["registro_url"] + "/salud"
    try:
        d = http_json(url, espera=4)
    except Exception as e:
        raise RegistroCaido(f"{url} no responde ({type(e).__name__}: {e})")
    if d.get("estado") != "ok":
        raise RegistroCaido(f"{url} respondió {d}")
    return d


def leer_registro(cfg: dict, ruta: str):
    try:
        return http_json(cfg["registro_url"] + ruta, espera=8)
    except Exception as e:
        raise RegistroCaido(f"lectura {ruta} falló ({type(e).__name__}: {e})")


def aplicar_ops(c, ops):
    """Idempotente: un evento con la misma (cuando, actor, accion, plan_id, detalle) no se repite; así reenviar la cola es seguro."""
    resultados, ultimo_evento = [], None

    def evento_existente(ev):
        fila = c.execute("SELECT id FROM evento WHERE cuando=? AND actor=? AND accion=? AND plan_id IS ? AND detalle IS ?",
                         (ev["cuando"], ev["actor"], ev["accion"], ev.get("plan_id"), ev.get("detalle"))).fetchone()
        return fila[0] if fila else None

    def insertar_evento(ev):
        existente = evento_existente(ev)
        if existente:
            return existente, False
        cur = c.execute("INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                        (ev["cuando"], ev["actor"], ev["accion"], ev.get("nodo_id"), ev.get("plan_id"), ev.get("detalle")))
        return cur.lastrowid, True

    for o in ops:
        tipo = o["op"]
        if tipo == "actor":
            c.execute("INSERT OR IGNORE INTO actor (id, clase, rol, modelo) VALUES (?, 'ia', ?, ?)", (o["id"], o["rol"], o["modelo"]))
            resultados.append({"op": tipo, "id": o["id"]})
        elif tipo == "evento":
            ultimo_evento, nuevo = insertar_evento(o)
            resultados.append({"op": tipo, "id": ultimo_evento, "accion": o["accion"], "nuevo": nuevo})
        elif tipo == "evidencia":
            dice = o["dice"].replace("{evento}", str(ultimo_evento))
            cur = c.execute("INSERT OR IGNORE INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?,?,?,?)",
                            (o["plan_id"], o.get("nodo_id"), o["fuente"], dice))
            resultados.append({"op": tipo, "fuente": o["fuente"], "insertada": cur.rowcount})
        elif tipo == "tarea_progreso":
            filas = 0
            if not evento_existente(o["evento"]):
                marcas = ",".join("?" * len(o["desde"]))
                filas = c.execute(f"UPDATE tarea SET progreso=? WHERE id=? AND progreso IN ({marcas})",
                                  (o["progreso"], o["tarea_id"], *o["desde"])).rowcount
                if filas:
                    ultimo_evento, _ = insertar_evento(o["evento"])
            resultados.append({"op": tipo, "filas": filas})
        elif tipo == "consulta":
            if not o["sql"].strip().lower().startswith("select"):
                raise ValueError("consulta solo admite SELECT")
            resultados.append({"op": tipo, "filas": [list(f) for f in c.execute(o["sql"], o.get("params", [])).fetchall()]})
        else:
            raise ValueError(f"op desconocida: {tipo}")
    return resultados


def ejecutar_lote(db_path, ops):
    import sqlite3
    c = sqlite3.connect(db_path, timeout=20, isolation_level=None)
    try:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=20000")
        c.execute("BEGIN" if all(o["op"] == "consulta" for o in ops) else "BEGIN IMMEDIATE")
        try:
            resultados = aplicar_ops(c, ops)
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        return {"ok": True, "resultados": resultados}
    finally:
        c.close()


def comando_ssh(cfg: dict) -> list[str]:
    s = cfg["ssh"]
    return [s["bin"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-i", os.path.expanduser(s["clave"]),
            "-p", str(s["puerto"]), s["destino"]]


def escribir(cfg: dict, ops: list[dict]) -> dict:
    modo = cfg["escritura"]
    if modo.startswith("sqlite:"):
        try:
            return ejecutar_lote(modo[len("sqlite:"):], ops)
        except sqlite3.OperationalError as e:
            raise RegistroCaido(f"sqlite local no disponible: {e}")
        except Exception as e:
            raise RegistroRechazo(f"{type(e).__name__}: {e}")
    payload = base64.b64encode(json.dumps(ops, ensure_ascii=False).encode("utf-8")).decode("ascii")
    programa = ("import base64, json, sys\n" + inspect.getsource(aplicar_ops) + "\n" + inspect.getsource(ejecutar_lote) + "\n"
                f"ops = json.loads(base64.b64decode('{payload}').decode('utf-8'))\n"
                "try:\n"
                f"    print(json.dumps(ejecutar_lote({cfg['ssh']['db']!r}, ops)))\n"
                "except Exception as e:\n"
                "    print(json.dumps({'ok': False, 'error': type(e).__name__ + ': ' + str(e)}))\n"
                "    sys.exit(3)\n")
    try:
        p = subprocess.run(comando_ssh(cfg) + ["python3", "-"], input=programa.encode("utf-8"),
                           capture_output=True, timeout=45, creationflags=SIN_VENTANA)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RegistroCaido(f"SSH al registro falló: {e}")
    lineas = p.stdout.decode("utf-8", "replace").strip().splitlines()
    try:
        r = json.loads(lineas[-1])
    except (IndexError, json.JSONDecodeError):
        raise RegistroCaido(f"SSH al registro sin respuesta (rc={p.returncode}): {p.stderr.decode('utf-8', 'replace')[-300:]}")
    if not r.get("ok"):
        raise RegistroRechazo(str(r.get("error")))
    return r


def op_evento(actor: str, accion: str, detalle: str, plan_id: str | None = None, cuando: str | None = None) -> dict:
    return {"op": "evento", "cuando": cuando or ahora(), "actor": actor, "accion": accion,
            "plan_id": plan_id, "nodo_id": None, "detalle": detalle[:1800]}


def ops_bloqueo(actor: str, mecanismo: str, plan_id: str | None, texto: str, cuando: str | None = None) -> list[dict]:
    cuando = cuando or ahora()
    ops = [op_evento(actor, f"bloqueo:{mecanismo}", texto, plan_id=plan_id, cuando=cuando)]
    if plan_id:
        ops.append({"op": "evidencia", "plan_id": plan_id, "nodo_id": None, "fuente": f"bloqueo:{mecanismo}",
                    "dice": f"evento {{evento}} ({cuando}) {actor}: {texto}"[:1800]})
    return ops


def op_kb(cfg: dict, clave: str, valor: str) -> dict:
    return {"op": "kb_guardar", "clave": clave, "valor": valor, "proyecto": cfg["kb_proyecto"], "categoria": "leccion"}


# ── cola local: los hooks encolan; flush.py (cada 60 s), el Stop y el SessionStart la envían ──

def ruta_cola(sid: str) -> Path:
    return COLA_DIR / (nombre_seguro(sid) + ".jsonl")


def ruta_estado_cola(sid: str) -> Path:
    return COLA_DIR / (nombre_seguro(sid) + ".estado.json")


def encolar(sid: str, ops: list[dict]) -> None:
    if not ops:
        return
    linea = json.dumps({"cuando": ahora(), "ops": ops}, ensure_ascii=False) + "\n"
    COLA_DIR.mkdir(parents=True, exist_ok=True)
    with cerrojo():
        with ruta_cola(sid).open("a", encoding="utf-8", newline="\n") as f:
            f.write(linea)


def estado_cola(sid: str) -> dict:
    try:
        return json.loads(ruta_estado_cola(sid).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _actualizar_estado_cola(sid: str, cambio) -> dict:
    with cerrojo():
        st = estado_cola(sid)
        cambio(st)
        _escribir_json(ruta_estado_cola(sid), st)
    return st


def ops_en_cola(sid: str) -> int:
    p = ruta_cola(sid)
    if not p.exists():
        return 0
    return sum(len(json.loads(l)["ops"]) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())


def kb_guardar(cfg: dict, op: dict) -> None:
    try:
        http_json(cfg["kb_url"] + "/api/save", "POST",
                  {"key": op["clave"], "value": op["valor"], "category": op["categoria"], "project": op["proyecto"]}, espera=10)
    except Exception as e:
        raise RegistroCaido(f"KB {cfg['kb_url']} no guardó {op['clave']} ({type(e).__name__}: {e})")


def _enviar_aislando_rechazos(cfg: dict, sid: str, lotes: list[list[dict]]) -> int:
    rechazados = []
    for ops in lotes:
        if not ops:
            continue
        try:
            escribir(cfg, ops)
        except RegistroRechazo as e:
            rechazados.append({"rechazado": ahora(), "error": str(e), "ops": ops})
    if rechazados:
        with (COLA_DIR / (nombre_seguro(sid) + ".rechazadas.jsonl")).open("a", encoding="utf-8") as f:
            for r in rechazados:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rechazados)


def vaciar(cfg: dict, sid: str, motivo: str, esperar: float = 0.0) -> dict:
    """Envía la cola de una sesión: primero la KB, después un lote atómico e idempotente al registro. Si falla, la cola se queda."""
    candado = COLA_DIR / (nombre_seguro(sid) + ".enviando")
    COLA_DIR.mkdir(parents=True, exist_ok=True)
    fd = _cerrojo_fichero(candado, esperar, 180)
    if fd is None:
        return {"estado": "ocupado", "sesion": sid}
    try:
        with cerrojo():
            p = ruta_cola(sid)
            datos = p.read_bytes() if p.exists() else b""
        lotes = [json.loads(l)["ops"] for l in datos.decode("utf-8").splitlines() if l.strip()]
        ops = [op for lote in lotes for op in lote]
        if not ops:
            return {"estado": "vacia", "sesion": sid}
        intento = ahora()
        st = _actualizar_estado_cola(sid, lambda s: s.update(ultimo_intento=intento))
        fallo = st.get("fallo")
        registro = [o for o in ops if o["op"] != "kb_guardar"]
        caida = []
        if fallo:
            caida = ops_bloqueo(fallo["actor"], "registro_caido", fallo.get("plan_id"),
                                f"registro SYPNOSE sin respuesta desde {fallo['desde']} (último fallo {fallo['ultimo']}, {fallo['intentos']} envíos fallidos"
                                f"{', incluido el del cierre del turno' if fallo.get('en_stop') else ''}); {len(ops)} operaciones retenidas en la cola "
                                f"local y enviadas al volver; último motivo: {fallo['motivo']}", cuando=fallo["ultimo"])
        try:
            salud(cfg)
            for o in ops:
                if o["op"] == "kb_guardar":
                    kb_guardar(cfg, o)
            try:
                escribir(cfg, registro + caida)
                rechazados = 0
            except RegistroRechazo:
                rechazados = _enviar_aislando_rechazos(cfg, sid, [[o for o in lote if o["op"] != "kb_guardar"] for lote in lotes] + [caida])
        except RegistroCaido as e:
            primer_evento = next((o for o in ops if o["op"] == "evento"), {})

            def anotar_fallo(s: dict) -> None:
                previo = s.get("fallo") or {}
                s["fallo"] = {"desde": previo.get("desde") or intento, "ultimo": intento, "intentos": previo.get("intentos", 0) + 1,
                              "motivo": str(e)[:500], "en_stop": bool(previo.get("en_stop")) or motivo == "stop",
                              "actor": primer_evento.get("actor") or actor_de(cfg, None),
                              "plan_id": next((o.get("plan_id") for o in ops if o.get("plan_id")), None)}

            _actualizar_estado_cola(sid, anotar_fallo)
            return {"estado": "fallo", "sesion": sid, "motivo": str(e), "pendientes": len(ops), "cola": str(ruta_cola(sid))}
        with cerrojo():
            completo = p.read_bytes() if p.exists() else b""
            resto = completo[len(datos):]
            if resto:
                tmp = p.with_name(p.name + ".tmp")
                tmp.write_bytes(resto)
                os.replace(tmp, p)
            else:
                p.unlink(missing_ok=True)
            st = estado_cola(sid)
            st.update(fallo=None, ultimo_ok=ahora())
            _escribir_json(ruta_estado_cola(sid), st)
        return {"estado": "rechazo" if rechazados else "ok", "sesion": sid, "enviadas": len(ops), "caido_registrado": bool(fallo),
                "rechazadas": rechazados, "fichero_rechazos": str(COLA_DIR / (nombre_seguro(sid) + ".rechazadas.jsonl"))}
    finally:
        os.close(fd)
        candado.unlink(missing_ok=True)


def vaciar_todas(cfg: dict, motivo: str) -> list[dict]:
    if not COLA_DIR.exists():
        return []
    sids = sorted({f.name[:-len(".jsonl")] for f in COLA_DIR.glob("*.jsonl") if not f.name.endswith(".rechazadas.jsonl")})
    return [vaciar(cfg, sid, motivo, esperar=10) for sid in sids]


def texto_fallo_cola(cfg: dict, r: dict) -> str:
    if r["estado"] == "rechazo":
        return f"EL REGISTRO SYPNOSE RECHAZÓ {r['rechazadas']} lote(s) de la cola (guardados en {r['fichero_rechazos']}); el resto se envió."
    if r["estado"] != "fallo":
        return ""
    return (f"REGISTRO SYPNOSE NO RESPONDE: {r.get('pendientes', '?')} operaciones siguen en la cola local ({r.get('cola')}); "
            "se reenvían cada 60 s y al terminar el turno, y el siguiente arranque las envía y registra bloqueo:registro_caido. "
            f"Motivo: {r.get('motivo')}. Túnel: {comando_tunel(cfg)}")


def aviso_cola(cfg: dict, sid: str) -> str | None:
    """Aviso visible, una vez por intento fallido, de que la cola no llega al registro."""
    mostrar = {}

    def cambio(s: dict) -> None:
        fallo = s.get("fallo")
        if fallo and s.get("avisado") != fallo["ultimo"]:
            s["avisado"] = fallo["ultimo"]
            mostrar.update(fallo)

    _actualizar_estado_cola(sid, cambio)
    if not mostrar:
        return None
    return texto_fallo_cola(cfg, {"estado": "fallo", "pendientes": ops_en_cola(sid), "cola": str(ruta_cola(sid)),
                                  "motivo": f"{mostrar['motivo']} (sin respuesta desde {mostrar['desde']})"})


# ── KB (knowledge-hub) ───────────────────────────────────────────────────────

def _filas_kb(respuesta) -> list[dict]:
    if isinstance(respuesta, list):
        return [x for x in respuesta if isinstance(x, dict)]
    if isinstance(respuesta, dict):
        for v in respuesta.values():
            if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                return v
    return []


def kb_ultima_leccion(cfg: dict, linea: str) -> dict | None:
    prefijo = f"leccion-linea-{linea}-"
    q = urllib.parse.urlencode({"project": cfg["kb_proyecto"], "category": "leccion", "limit": 500})
    filas = [f for f in _filas_kb(http_json(cfg["kb_url"] + "/api/list?" + q, espera=8)) if str(f.get("key", "")).startswith(prefijo)]
    if not filas:
        return None
    mejor = max(filas, key=lambda f: (int(f.get("id") or 0), str(f["key"])))
    if mejor.get("value"):
        return mejor
    q = urllib.parse.urlencode({"key": mejor["key"], "project": cfg["kb_proyecto"]})
    leida = http_json(cfg["kb_url"] + "/api/read?" + q, espera=8)
    for candidata in (leida, *(v for v in (leida.values() if isinstance(leida, dict) else []) if isinstance(v, dict)), *_filas_kb(leida)):
        if isinstance(candidata, dict) and candidata.get("value"):
            return {**mejor, **candidata}
    return {**mejor, "value": "(la KB no devolvió el valor)"}


# ── transcript: tokens, modelo y coste del turno ─────────────────────────────

def precios() -> dict:
    res, actual = {}, None
    for linea in (DIR / "precios.yaml").read_text(encoding="utf-8").splitlines():
        s = linea.split("#", 1)[0].rstrip()
        if not s.strip():
            continue
        sangria = len(s) - len(s.lstrip())
        clave, _, valor = s.strip().partition(":")
        if sangria == 2 and not valor.strip():
            actual = clave
            res[actual] = {}
        elif sangria == 4 and actual:
            res[actual][clave] = float(valor)
    return res


def _cola_transcript(transcript_path: str | None) -> list[str]:
    p = Path(transcript_path) if transcript_path else None
    if not p or not p.is_file():
        return []
    with p.open("rb") as f:
        tam = f.seek(0, os.SEEK_END)
        f.seek(max(0, tam - 2_000_000))
        return f.read().decode("utf-8", errors="replace").splitlines()


def uso_turno(transcript_path: str | None) -> dict:
    uso = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "modelo": None, "leido": False}
    vistos = set()
    for linea in reversed(_cola_transcript(transcript_path)):
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        if d.get("type") == "user":
            contenido = msg.get("content")
            if not (isinstance(contenido, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in contenido)):
                break
        elif d.get("type") == "assistant":
            clave = msg.get("id") or d.get("uuid")
            if clave in vistos:
                continue
            vistos.add(clave)
            u = msg.get("usage") or {}
            uso["input"] += int(u.get("input_tokens") or 0)
            uso["output"] += int(u.get("output_tokens") or 0)
            uso["cache_creation"] += int(u.get("cache_creation_input_tokens") or 0)
            uso["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
            uso["modelo"] = uso["modelo"] or modelo_limpio(msg.get("model"))
            uso["leido"] = True
    return uso


def modelo_en_transcript(transcript_path: str | None) -> str | None:
    """Último modelo real del transcript: adjunto 'model' (se escribe tras SessionStart) o message.model de una respuesta."""
    for linea in reversed(_cola_transcript(transcript_path)):
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue
        adjunto = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
        candidato = None
        if adjunto.get("type") == "model" and isinstance(adjunto.get("identity"), dict):
            candidato = modelo_limpio(adjunto["identity"].get("modelId"))
        elif d.get("type") == "assistant" and isinstance(d.get("message"), dict):
            candidato = modelo_limpio(d["message"].get("model"))
        if candidato:
            return candidato
    return None


def coste_usd(uso: dict, modelo: str | None) -> float | None:
    p = precios().get(modelo or "")
    if not p:
        return None
    return (uso["input"] * p["input"] + uso["cache_creation"] * p["input"] * 1.25
            + uso["cache_read"] * p["input"] * 0.1 + uso["output"] * p["output"]) / 1_000_000
