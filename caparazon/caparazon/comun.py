"""Caparazón SYPNOSE: configuración, estado de sesión, registro (lectura HTTP, escritura SSH/sqlite), KB y salida de hooks."""
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
CERROJO = ESTADO_DIR / ".cerrojo"
PENDIENTES = DIR / "pendientes.jsonl"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

for _flujo in (sys.stdout, sys.stderr):
    with contextlib.suppress(Exception):
        _flujo.reconfigure(encoding="utf-8")


class RegistroCaido(Exception):
    """El registro no responde: se bloquea y las escrituras quedan en pendientes.jsonl."""


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
    """Un fallo inesperado del hook no puede dejar la puerta abierta: se aplica al_fallar(mensaje)."""
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        al_fallar(f"CAPARAZÓN FALLÓ ({Path(sys.argv[0]).name}): {type(e).__name__}: {e}")


# ── estado por sesión ────────────────────────────────────────────────────────

@contextlib.contextmanager
def cerrojo(espera: float = 15.0):
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    fin = time.monotonic() + espera
    while True:
        try:
            fd = os.open(CERROJO, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            with contextlib.suppress(FileNotFoundError):
                if time.time() - CERROJO.stat().st_mtime > 60:
                    CERROJO.unlink(missing_ok=True)
                    continue
            if time.monotonic() > fin:
                raise TimeoutError("cerrojo del caparazón ocupado")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        CERROJO.unlink(missing_ok=True)


def ruta_estado(session_id: str) -> Path:
    return ESTADO_DIR / (re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "sin-sesion") + ".json")


def leer_estado(session_id: str) -> dict | None:
    p = ruta_estado(session_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def guardar_estado(estado: dict) -> None:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    p = ruta_estado(estado["session_id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


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
    resultados, ultimo_evento = [], None
    for o in ops:
        tipo = o["op"]
        if tipo == "actor":
            c.execute("INSERT OR IGNORE INTO actor (id, clase, rol, modelo) VALUES (?, 'ia', ?, ?)", (o["id"], o["rol"], o["modelo"]))
            resultados.append({"op": tipo, "id": o["id"]})
        elif tipo == "evento":
            cur = c.execute("INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                            (o["cuando"], o["actor"], o["accion"], o.get("nodo_id"), o.get("plan_id"), o.get("detalle")))
            ultimo_evento = cur.lastrowid
            resultados.append({"op": tipo, "id": ultimo_evento, "accion": o["accion"]})
        elif tipo == "evidencia":
            dice = o["dice"].replace("{evento}", str(ultimo_evento))
            cur = c.execute("INSERT OR IGNORE INTO evidencia (plan_id, nodo_id, fuente, dice) VALUES (?,?,?,?)",
                            (o["plan_id"], o.get("nodo_id"), o["fuente"], dice))
            resultados.append({"op": tipo, "fuente": o["fuente"], "insertada": cur.rowcount})
        elif tipo == "tarea_progreso":
            marcas = ",".join("?" * len(o["desde"]))
            cur = c.execute(f"UPDATE tarea SET progreso=? WHERE id=? AND progreso IN ({marcas})", (o["progreso"], o["tarea_id"], *o["desde"]))
            if cur.rowcount and o.get("evento"):
                ev = o["evento"]
                cur2 = c.execute("INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) VALUES (?,?,?,?,?,?)",
                                 (ev["cuando"], ev["actor"], ev["accion"], None, ev.get("plan_id"), ev.get("detalle")))
                ultimo_evento = cur2.lastrowid
            resultados.append({"op": tipo, "filas": cur.rowcount})
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


def guardar_pendientes(ops: list[dict]) -> None:
    with cerrojo():
        with PENDIENTES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"guardado": ahora(), "ops": ops}, ensure_ascii=False) + "\n")


def vaciar_pendientes(cfg: dict) -> int:
    if not PENDIENTES.exists():
        return 0
    with cerrojo():
        lotes = [json.loads(l) for l in PENDIENTES.read_text(encoding="utf-8").splitlines() if l.strip()]
        ops = [op for lote in lotes for op in lote["ops"]]
        if ops:
            try:
                escribir(cfg, ops)
            except RegistroRechazo:
                PENDIENTES.rename(DIR / f"pendientes-rechazados-{datetime.now():%Y%m%d-%H%M%S}.jsonl")
                return 0
        PENDIENTES.unlink(missing_ok=True)
    return len(ops)


def emitir(cfg: dict, ops: list[dict]) -> dict:
    """Escribe en el registro. Si cae, las ops quedan en pendientes.jsonl y se relanza (FAIL LOUD)."""
    try:
        vaciar_pendientes(cfg)
        return escribir(cfg, ops)
    except RegistroCaido:
        guardar_pendientes(ops)
        raise


def op_evento(actor: str, accion: str, detalle: str, plan_id: str | None = None, cuando: str | None = None) -> dict:
    return {"op": "evento", "cuando": cuando or ahora(), "actor": actor, "accion": accion,
            "plan_id": plan_id, "nodo_id": None, "detalle": detalle[:1800]}


def ops_bloqueo(actor: str, mecanismo: str, plan_id: str | None, texto: str) -> list[dict]:
    cuando = ahora()
    ops = [op_evento(actor, f"bloqueo:{mecanismo}", texto, plan_id=plan_id, cuando=cuando)]
    if plan_id:
        ops.append({"op": "evidencia", "plan_id": plan_id, "nodo_id": None, "fuente": f"bloqueo:{mecanismo}",
                    "dice": f"evento {{evento}} ({cuando}) {actor}: {texto}"[:1800]})
    return ops


# ── KB (knowledge-hub) ───────────────────────────────────────────────────────

def kb_guardar(cfg: dict, clave: str, valor: str) -> dict:
    return http_json(cfg["kb_url"] + "/api/save", "POST",
                     {"key": clave, "value": valor, "category": "leccion", "project": cfg["kb_proyecto"]}, espera=10)


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


# ── transcript: tokens y coste del turno ─────────────────────────────────────

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


def uso_turno(transcript_path: str | None) -> dict:
    uso = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "modelo": None, "leido": False}
    p = Path(transcript_path) if transcript_path else None
    if not p or not p.is_file():
        return uso
    with p.open("rb") as f:
        tam = f.seek(0, os.SEEK_END)
        f.seek(max(0, tam - 2_000_000))
        lineas = f.read().decode("utf-8", errors="replace").splitlines()
    vistos = set()
    for linea in reversed(lineas):
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
    """Último modelo visto en el transcript: adjunto 'model' (se escribe tras SessionStart) o message.model de una respuesta."""
    p = Path(transcript_path) if transcript_path else None
    if not p or not p.is_file():
        return None
    with p.open("rb") as f:
        tam = f.seek(0, os.SEEK_END)
        f.seek(max(0, tam - 2_000_000))
        lineas = f.read().decode("utf-8", errors="replace").splitlines()
    for linea in reversed(lineas):
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
