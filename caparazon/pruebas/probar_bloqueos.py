"""B9: pruebas de bloqueo del caparazón invocando cada hook con su ENTRADA EXACTA (JSON por stdin; fichero de mensaje en commit-msg).

    python probar_bloqueos.py --carpeta "C:\\MICD\\Coforge Santander\\02-backend-api" --modo local
        registro sqlite temporal (registro_minimo.sql, PLAN-CS-T01 abierto) + API y KB simuladas; no toca SYPNOSE.
    python probar_bloqueos.py --carpeta "C:\\MICD\\Coforge Santander\\02-backend-api" --modo real --actor IA:07-verificador:claude-opus-5
        caparazón instalado en la carpeta + registro SYPNOSE real por túnel (7101 y 18791). Escribe eventos reales con --actor.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

for _flujo in (sys.stdout, sys.stderr):
    _flujo.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
FUENTE = AQUI.parent / "caparazon"
RESULTADOS: list[tuple[str, str]] = []
SQL_PLANES = """SELECT p.id, p.clase, p.que, p.estado, p.autor, p.dueno, p.worktree, p.cuesta, p.coste_real, p.abierto_en, p.cerrado_en,
  (SELECT COUNT(*) FROM requisito r WHERE r.plan_id=p.id) requisitos, (SELECT COUNT(*) FROM tarea t WHERE t.plan_id=p.id) tareas,
  (SELECT COUNT(*) FROM tarea t WHERE t.plan_id=p.id AND t.progreso='hecha') hechas FROM plan p"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def simulador(db: Path) -> str:
    kb: dict[str, dict] = {}

    class Api(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def responder(self, codigo: int, cuerpo) -> None:
            datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(datos)

        def do_POST(self):
            cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if urlparse(self.path).path == "/api/save":
                kb[cuerpo["key"]] = {**cuerpo, "id": len(kb) + 1, "tier": "HOT", "access_count": 0}
                return self.responder(200, {"ok": True, "key": cuerpo["key"]})
            self.responder(404, {"error": "no existe"})

        def do_GET(self):
            u, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
            if u.path == "/api/list":
                filas = [{k: v for k, v in e.items() if k != "value"} for e in kb.values() if e.get("project") == q.get("project", [None])[0]]
                return self.responder(200, {"entries": filas, "total": len(filas), "limit": 500, "offset": 0})
            if u.path == "/api/read":
                entrada = kb.get(q.get("key", [""])[0])
                return self.responder(200, {"found": bool(entrada), "entry": entrada})
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            try:
                if u.path == "/salud":
                    return self.responder(200, {"estado": "ok", "eventos": c.execute("SELECT COUNT(*) FROM evento").fetchone()[0]})
                if u.path == "/planes":
                    return self.responder(200, {"planes": [dict(r) for r in c.execute(SQL_PLANES)]})
                m = re.match(r"^/plan/([^/]+)$", u.path)
                if m and (plan := c.execute("SELECT * FROM plan WHERE id=?", (m.group(1),)).fetchone()):
                    return self.responder(200, {
                        "plan": dict(plan),
                        "requisitos": [dict(r) for r in c.execute("SELECT ref, ears, comprobacion FROM requisito WHERE plan_id=? ORDER BY ref", (plan["id"],))],
                        "tareas": [dict(r) for r in c.execute("SELECT id, req_ref, titulo, progreso, agente, coste, bloqueada_por, verificada_por FROM tarea WHERE plan_id=? ORDER BY id", (plan["id"],))],
                        "objetivos": [], "eventos": []})
                return self.responder(404, {"error": "no existe"})
            finally:
                c.close()

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Api)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{servidor.server_address[1]}"


def caso(nombre: str, dir_capa: Path, script: str, entrada: dict | None, env: dict, esperado, args: tuple = ()) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, str(dir_capa / script), *args], input=json.dumps(entrada or {}, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env={**os.environ, **env}, timeout=240)
    rc, out, err = p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    veredicto = "CUMPLE" if esperado(rc, out, err) else "NO CUMPLE"
    print(f"\n── {nombre} ──\nhook: {script} {' '.join(args)}")
    if entrada is not None:
        visible = {k: v for k, v in entrada.items() if k not in ("transcript_path", "permission_mode")}
        print(f"entrada: {json.dumps(visible, ensure_ascii=False)[:500]}")
    print(f"exit={rc}")
    if out.strip():
        print(f"stdout: {out.strip()[:900]}")
    if err.strip():
        print(f"stderr: {err.strip()[:900]}")
    print(f"→ {veredicto}")
    RESULTADOS.append((nombre, veredicto))
    return rc, out, err


def no_aplica(nombre: str, motivo: str) -> None:
    print(f"\n── {nombre} ──\n→ NO APLICA: {motivo}")
    RESULTADOS.append((nombre, "NO APLICA"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", required=True)
    ap.add_argument("--modo", choices=("local", "real"), default="local")
    ap.add_argument("--actor", default="IA:08-caparazon:claude-opus-5")
    args = ap.parse_args()
    carpeta = Path(args.carpeta).resolve()
    inicio = ahora()
    tmp = Path(tempfile.mkdtemp(prefix="caparazon-b9-"))
    env = {"SYPNOSE_ACTOR": args.actor}
    if args.modo == "local":
        db = tmp / "registro.db"
        with sqlite3.connect(db) as c:
            c.executescript((AQUI / "registro_minimo.sql").read_text(encoding="utf-8"))
        url = simulador(db)
        dir_capa = tmp / "caparazon"
        shutil.copytree(FUENTE, dir_capa, ignore=shutil.ignore_patterns("__pycache__", "estado", "pendientes*.jsonl", "config.json"))
        wt = carpeta / "wt"
        (dir_capa / "config.json").write_text(json.dumps({
            "carpeta": carpeta.name, "carpeta_ruta": str(carpeta), "worktree": str(wt), "coleccion": "coforge-santander",
            "kb_proyecto": "coforge-santander", "prefijo_planes": "PLAN-CS-", "plan_id": None, "verificador": "07-verificador",
            "ssh": {"bin": "ssh", "destino": "sin-uso", "puerto": 0, "clave": "sin-uso", "db": "sin-uso"}}, ensure_ascii=False), encoding="utf-8")
        env.update(SYPNOSE_REGISTRO_URL=url, SYPNOSE_KB_URL=url, SYPNOSE_REGISTRO_ESCRITURA=f"sqlite:{db}")
        print(f"[modo local] registro sqlite {db} · API/KB simuladas en {url}")
    else:
        dir_capa = carpeta / ".claude" / "caparazon"
        if not (dir_capa / "config.json").exists():
            sys.exit(f"{carpeta} no tiene el caparazón instalado")
        print(f"[modo real] caparazón {dir_capa} · registro {os.environ.get('SYPNOSE_REGISTRO_URL', 'http://127.0.0.1:7101')} · actor {args.actor}")
    cfg = json.loads((dir_capa / "config.json").read_text(encoding="utf-8"))
    wt = cfg["worktree"]
    transcript = tmp / "transcript.jsonl"
    transcript.write_text("\n".join(json.dumps(x) for x in [
        {"type": "user", "message": {"role": "user", "content": "continúa con la tarea"}},
        {"type": "assistant", "message": {"id": "msg_prueba", "model": "claude-sonnet-5", "role": "assistant", "content": [],
                                          "usage": {"input_tokens": 1200, "output_tokens": 340, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 5000}}},
    ]) + "\n", encoding="utf-8")
    sid = f"prueba-b9-{args.modo}-{datetime.now():%H%M%S}"
    base = {"session_id": sid, "transcript_path": str(transcript), "cwd": wt, "permission_mode": "default"}
    centinela = str(Path(wt).parent / "_centinela_fuera.txt")
    permitido = str(Path(wt) / "app" / "main.py")

    _, out, _ = caso("B1 SessionStart: brief desde el registro", dir_capa, "brief.py",
                     {**base, "hook_event_name": "SessionStart", "source": "startup", "model": "claude-sonnet-5"}, env,
                     lambda rc, o, e: rc == 0 and "BRIEF CAPARAZÓN" in o)
    abierto = "ABORTADO" not in out
    caso("B2 UserPromptSubmit: reinyecta la EARS literal" if abierto else "B2 UserPromptSubmit: prompt bloqueado por brief ABORTADO",
         dir_capa, "prompt_submit.py", {**base, "hook_event_name": "UserPromptSubmit", "prompt": "sigue con la tarea"}, env,
         (lambda rc, o, e: rc == 0 and "texto literal del registro SYPNOSE" in o) if abierto else (lambda rc, o, e: rc == 2 and "ABORTADO" in e))
    pre = {**base, "hook_event_name": "PreToolUse", "tool_use_id": "toolu_prueba"}
    bloquea = lambda rc, o, e: rc == 2 and ("CERCO" in e or not abierto)
    caso("B3.1 PreToolUse: Write a la centinela fuera del worktree", dir_capa, "pre_tool_use.py",
         {**pre, "tool_name": "Write", "tool_input": {"file_path": centinela, "content": "x"}}, env, bloquea)
    caso("B3.2 PreToolUse: Bash con redirección a la centinela", dir_capa, "pre_tool_use.py",
         {**pre, "tool_name": "Bash", "tool_input": {"command": "echo x > ../_centinela_fuera.txt"}}, env, bloquea)
    caso("B3.3 PreToolUse: Write dentro del worktree pero fuera de archivos_permitidos", dir_capa, "pre_tool_use.py",
         {**pre, "tool_name": "Write", "tool_input": {"file_path": str(Path(wt) / "README.md"), "content": "x"}}, env, bloquea)
    caso("B3.4 PreToolUse (control): Edit en archivo permitido", dir_capa, "pre_tool_use.py",
         {**pre, "tool_name": "Edit", "tool_input": {"file_path": permitido, "old_string": "a", "new_string": "b"}}, env,
         (lambda rc, o, e: rc == 0) if abierto else (lambda rc, o, e: rc == 2 and "ABORTADO" in e))
    caso("B4 PostToolUse: evento en vivo con tokens del turno", dir_capa, "post_tool_use.py",
         {**base, "hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": permitido, "content": "..."},
          "tool_response": {"filePath": permitido, "type": "update"}, "tool_use_id": "toolu_prueba", "duration_ms": 12, "prompt_id": "prompt-prueba"},
         env, lambda rc, o, e: rc == 0 and '"continue": false' not in o)

    mensajes = {"sin_pie": "prueba B9: commit sin pie\n",
                "con_pie": f"prueba B9: commit con pie\n\nChat: {cfg['carpeta']}\nModel: claude-sonnet-5\nPlan: PLAN-CS-T01\nTarea: 9\n"}
    for nombre, texto in mensajes.items():
        (tmp / f"{nombre}.txt").write_text(texto, encoding="utf-8")
    caso("B5.1 commit-msg: mensaje sin pie Chat/Model/Plan/Tarea", dir_capa, "commit_msg.py", None, env,
         lambda rc, o, e: rc == 1 and "COMMIT RECHAZADO" in e, (str(tmp / "sin_pie.txt"),))
    caso("B5.2 commit-msg (control): mensaje con pie completo", dir_capa, "commit_msg.py", None, env,
         (lambda rc, o, e: rc == 0) if abierto else (lambda rc, o, e: rc in (0, 1)), (str(tmp / "con_pie.txt"),))
    if args.modo == "real":
        cabeza = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        p = subprocess.run(["git", "-C", wt, "commit", "--allow-empty", "-m", "prueba B9: commit real sin pie"],
                           capture_output=True, text=True, env={**os.environ, **env})
        despues = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        ok = p.returncode != 0 and cabeza == despues
        print(f"\n── B5.3 git commit real sin pie en el worktree ──\n$ git -C {wt} commit --allow-empty -m \"prueba B9: commit real sin pie\"\n"
              f"exit={p.returncode}\nstderr: {p.stderr.strip()[:700]}\nHEAD antes {cabeza[:10]} · después {despues[:10]}\n→ {'CUMPLE' if ok else 'NO CUMPLE'}")
        RESULTADOS.append(("B5.3 git commit real sin pie", "CUMPLE" if ok else "NO CUMPLE"))

    stop = {**base, "hook_event_name": "Stop", "stop_hook_active": False}
    if abierto:
        caso("B6.1 Stop: cierre con escrituras y sin ENTREGA", dir_capa, "stop.py",
             {**stop, "last_assistant_message": "He terminado los cambios en app/main.py."}, env, lambda rc, o, e: rc == 2 and "CIERRE IMPEDIDO" in e)
    else:
        no_aplica("B6.1 Stop: cierre con escrituras y sin ENTREGA", "el plan no está abierto; la sesión está ABORTADA y no tiene escrituras que entregar")
    if args.modo == "local":
        comprobacion = "pytest tests/test_main.py tests/test_engine_mode.py -q"
        caso("B6.2 PostToolUse: ejecución de la comprobación (salida simulada en modo local)", dir_capa, "post_tool_use.py",
             {**base, "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": f"cd wt && python -m {comprobacion}"},
              "tool_response": {"stdout": "...............\n15 passed in 1.04s", "stderr": "", "interrupted": False, "isImage": False}}, env,
             lambda rc, o, e: rc == 0)
        inventada = f"ENTREGA\nComprobación: {comprobacion}\nSalida: 20 passed in 0.50s\nLECCIÓN: prueba"
        caso("B6.3 Stop: ENTREGA con salida inventada", dir_capa, "stop.py", {**stop, "last_assistant_message": inventada}, env,
             lambda rc, o, e: rc == 2 and "no es la salida real" in e)
        caso("B6.4 PostToolUse: aviso a 07-verificador por send_message", dir_capa, "post_tool_use.py",
             {**base, "hook_event_name": "PostToolUse", "tool_name": "mcp__ccd_session_mgmt__send_message",
              "tool_input": {"session_id": "sesion-07", "message": f"ENTREGA PLAN-CS-T01 tarea 9: {comprobacion} → 15 passed in 1.04s"},
              "tool_response": {"ok": True}}, env, lambda rc, o, e: rc == 0)
        valida = f"ENTREGA\nComprobación: {comprobacion}\nSalida: 15 passed in 1.04s\nLECCIÓN: el arranque en modo real falla antes de readiness si falta una credencial"
        caso("B6.5 Stop: ENTREGA válida → lección en KB + tarea_entregada", dir_capa, "stop.py", {**stop, "last_assistant_message": valida}, env,
             lambda rc, o, e: rc == 0 and "ENTREGA registrada" in o)
        caso("B6.6 SessionStart de una segunda sesión: el brief incluye la lección", dir_capa, "brief.py",
             {**base, "session_id": sid + "-2", "hook_event_name": "SessionStart", "source": "startup", "model": "claude-sonnet-5"}, env,
             lambda rc, o, e: rc == 0 and "leccion-linea-T01-" in o)

    caido = {**env, "SYPNOSE_REGISTRO_URL": "http://127.0.0.1:9"}
    caso("B7.1 registro caído: UserPromptSubmit", dir_capa, "prompt_submit.py", {**base, "hook_event_name": "UserPromptSubmit", "prompt": "sigue"},
         caido, lambda rc, o, e: rc == 2 and "REGISTRO SYPNOSE CAÍDO" in e)
    caso("B7.2 registro caído: PreToolUse en archivo permitido", dir_capa, "pre_tool_use.py",
         {**pre, "tool_name": "Edit", "tool_input": {"file_path": permitido, "old_string": "a", "new_string": "b"}}, caido,
         lambda rc, o, e: rc == 2 and "REGISTRO SYPNOSE CAÍDO" in e)
    caso("B7.3 registro caído: PostToolUse para la sesión (continue:false)", dir_capa, "post_tool_use.py",
         {**base, "hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": permitido}, "tool_response": {}}, caido,
         lambda rc, o, e: rc == 0 and '"continue": false' in o)
    caso("B7.4 registro caído: commit-msg con pie completo", dir_capa, "commit_msg.py", None, caido,
         lambda rc, o, e: rc == 1 and "REGISTRO SYPNOSE CAÍDO" in e, (str(tmp / "con_pie.txt"),))
    caso("B7.5 registro caído: SessionStart aborta la sesión", dir_capa, "brief.py",
         {**base, "session_id": sid + "-caido", "hook_event_name": "SessionStart", "source": "startup", "model": "claude-sonnet-5"}, caido,
         lambda rc, o, e: rc == 0 and "REGISTRO SYPNOSE CAÍDO" in o)
    caso("B7.6 registro de vuelta: PostToolUse vacía pendientes en el registro", dir_capa, "post_tool_use.py",
         {**base, "hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {"file_path": permitido}, "tool_response": {}}, env,
         lambda rc, o, e: rc == 0 and not (dir_capa / "pendientes.jsonl").exists())

    print(f"\n══ Evidencia en el registro (actor {args.actor}, desde {inicio}) ══")
    sql_ev = "SELECT id, cuando, accion, plan_id, substr(detalle,1,150) FROM evento WHERE actor=? AND cuando>=? ORDER BY id"
    sql_evid = "SELECT plan_id, fuente, substr(dice,1,170) FROM evidencia WHERE dice LIKE ? ORDER BY rowid"
    if args.modo == "local":
        with sqlite3.connect(env["SYPNOSE_REGISTRO_ESCRITURA"][len("sqlite:"):]) as c:
            eventos = c.execute(sql_ev, (args.actor, inicio)).fetchall()
            evidencias = c.execute(sql_evid, (f"%{args.actor}%",)).fetchall()
            print("tarea 9:", c.execute("SELECT progreso FROM tarea WHERE id=9").fetchone())
    else:
        sys.path.insert(0, str(dir_capa))
        import comun
        r = comun.escribir(comun.config(), [{"op": "consulta", "sql": sql_ev, "params": [args.actor, inicio]},
                                            {"op": "consulta", "sql": sql_evid, "params": [f"%{args.actor}%"]}])["resultados"]
        eventos, evidencias = r[0]["filas"], r[1]["filas"]
    for fila in eventos:
        print("  evento", fila)
    for fila in evidencias:
        m = re.search(r"\((\d{4}-\d\d-\d\dT[^)]+)\)", fila[2])
        if m and m.group(1) >= inicio:
            print("  evidencia", fila)
    for f in (dir_capa / "estado").glob(f"{sid}*.json"):
        f.unlink()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n══ Resumen ══")
    for nombre, veredicto in RESULTADOS:
        print(f"  {veredicto:9s} {nombre}")
    sys.exit(0 if all(v != "NO CUMPLE" for _, v in RESULTADOS) else 1)


if __name__ == "__main__":
    main()
