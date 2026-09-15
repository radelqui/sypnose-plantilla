"""headersHelper del MCP github: la cabecera Authorization sale de `gh auth token` en cada conexión; el token no se guarda en ningún fichero."""
import json
import subprocess
import sys

p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
token = p.stdout.strip()
if p.returncode != 0 or not token:
    sys.stderr.write("gh auth token falló: ejecuta `gh auth login`\n")
    sys.exit(1)
print(json.dumps({"Authorization": f"Bearer {token}"}))
