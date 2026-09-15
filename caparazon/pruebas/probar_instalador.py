"""B8: prueba de instalar_caparazon.py sobre carpetas temporales (no toca ninguna carpeta de chat).

    python probar_instalador.py

Comprueba el marcador INSTALADO, SYPNOSE_MODO en settings.json (real con --modo real, prueba por defecto), que reinstalar no cambia ni
contenido ni fecha de ningún fichero y que desinstalar devuelve settings.json, CLAUDE.md y .mcp.json a como estaban.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
INSTALADOR = Path(__file__).resolve().parent.parent / "instalar_caparazon.py"
tmp = Path(tempfile.mkdtemp(prefix="probar-instalador-"))


def carpeta_nueva(nombre, settings=None):
    c = tmp / nombre
    (c / "wt").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(c / "wt")], check=True)
    (c / "CLAUDE.md").write_text(f"# {nombre}\n", encoding="utf-8", newline="\n")
    if settings is not None:
        (c / ".claude").mkdir()
        (c / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8", newline="\n")
    return c


def foto(c):
    return {p.relative_to(c).as_posix(): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in sorted(c.rglob("*")) if p.is_file() and ".git" not in p.relative_to(c).parts}


def instalar(c, *extra):
    p = subprocess.run([sys.executable, str(INSTALADOR), str(c), *extra], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"$ instalar_caparazon.py {c.name} {' '.join(extra)} → exit {p.returncode}")
    for linea in p.stdout.strip().splitlines():
        print("   ", linea)
    if p.returncode:
        print(p.stderr)


ok = True
ajenos = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "ajeno.exe"}]}]}, "permissions": {"allow": ["Bash(ls *)"]}, "env": {"AJENA": "1"}}
c1 = carpeta_nueva("con-ajenos", ajenos)
originales = {n: (c1 / n).read_bytes() for n in ("CLAUDE.md", ".claude/settings.json")}
instalar(c1, "--modo", "real")
f1 = foto(c1)
marcador = json.loads((c1 / ".claude/caparazon/INSTALADO").read_text(encoding="utf-8"))
s1 = json.loads((c1 / ".claude/settings.json").read_text(encoding="utf-8"))
ajeno_vivo = any(h.get("command") == "ajeno.exe" for g in s1["hooks"]["Stop"] for h in g["hooks"])
print(f"marcador INSTALADO: {marcador}")
print(f"settings.env: {s1.get('env')} · hook ajeno conservado: {ajeno_vivo}")
ok &= marcador.get("carpeta_ruta") == str(c1.resolve()) and s1.get("env") == {"AJENA": "1", "SYPNOSE_MODO": "real"} and ajeno_vivo
instalar(c1, "--modo", "real")
f2 = foto(c1)
print(f"reinstalar no cambia nada ({len(f2)} ficheros, ni contenido ni fecha): {f1 == f2}")
ok &= f1 == f2
instalar(c1, "--desinstalar")
s2 = json.loads((c1 / ".claude/settings.json").read_text(encoding="utf-8"))
iguales = {n: (c1 / n).read_bytes() == b for n, b in originales.items()}
print(f"desinstalar: settings.json igual al original={s2 == ajenos} · bytes iguales={iguales} · .mcp.json existe={(c1 / '.mcp.json').exists()} · "
      f"módulos activos={(c1 / '.claude/caparazon').exists()} · en .claude queda={sorted(p.name for p in (c1 / '.claude').iterdir())}")
ok &= s2 == ajenos and all(iguales.values()) and not (c1 / ".mcp.json").exists() and not (c1 / ".claude/caparazon").exists()
c2 = carpeta_nueva("limpia")
instalar(c2)
s3 = json.loads((c2 / ".claude/settings.json").read_text(encoding="utf-8"))
print(f"modo por defecto: settings.env={s3.get('env')}")
ok &= s3.get("env") == {"SYPNOSE_MODO": "prueba"}
instalar(c2, "--desinstalar")
quedan = sorted(p.relative_to(c2).as_posix() for p in c2.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(c2).parts and "caparazon-desinstalado" not in p.as_posix())
limpia = quedan == ["CLAUDE.md"] and (c2 / "CLAUDE.md").read_bytes() == b"# limpia\n"
print(f"desinstalar deja la carpeta limpia como estaba: {limpia} ({quedan})")
ok &= limpia
print("RESULTADO:", "CUMPLE" if ok else "NO CUMPLE")
sys.exit(0 if ok else 1)
