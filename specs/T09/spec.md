# T09 — Experience with Git and version control best practices

## Oferta (línea 9, literal de `oferta-coforge.txt`)

> Experience with Git and version control best practices

## Solución

La plantilla SYPNOSE implementa trazabilidad Git por diseño:

- **Rama por chat**: cada chat trabaja en `chat/<carpeta>` (p. ej.
  `chat/02-backend-api`, `chat/05-arquitecto-sypnose`). La rama `main` se
  actualiza solo por merge desde ramas chat, nunca por commit directo.
- **Worktrees aislados**: cada chat tiene su worktree (`wt-plantilla`,
  `wt-T03`, etc.) que apunta a su rama. Nunca dos chats tocan el mismo
  worktree.
- **Trailers obligatorios**: todo commit lleva al pie `Chat:`, `Model:` y
  `Plan:` como trailers Git. Sin los tres, el commit no es válido según las
  reglas del proyecto (`CLAUDE.md`).
- **Caparazón B15**: `commit_msg.py` inyecta los trailers automáticamente;
  `cerco.py` bloquea operaciones git de escritura por SSH en el servidor.
- **Bare repo centralizado**: `~/git/plantilla.git` en el servidor 67 es el
  único origen. Los PCs hacen push vía SSH; el servidor hace pull al working
  clone.

## R1 — Trazabilidad por commit en ambos repositorios

**EARS:**
> Cada commit en los repositorios `plantilla` y `rag-banking-agent` DEBE llevar
> los trailers `Chat:`, `Model:` y `Plan:` en el último párrafo del mensaje.
> Al menos 3 chats distintos DEBEN haber contribuido commits con trailers
> válidos al repositorio `plantilla`. Al menos 10 commits con los tres trailers
> DEBEN existir en `plantilla`.

**Comprobación (determinista, sobre los repos en el servidor)**

```bash
cd ~/coforge-santander/plantilla && TOTAL=$(git log --format='%(trailers:key=Chat,valueonly)' | grep -c '.') && CHATS=$(git log --format='%(trailers:key=Chat,valueonly)' | grep '.' | sort -u | wc -l) && echo "plantilla: $TOTAL commits con Chat trailer, $CHATS chats distintos" && test "$TOTAL" -ge 10 && test "$CHATS" -ge 3 && echo "CUMPLE"
```
