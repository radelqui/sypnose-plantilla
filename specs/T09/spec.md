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
- **Caparazón B5+**: `commit_msg.py` inyecta y valida los trailers
  automáticamente; `cerco.py` bloquea operaciones git de escritura por SSH
  en el servidor. B24 exime a los merges de origin.
- **Bare repo centralizado**: `~/git/plantilla.git` en el servidor 67 es el
  único origen. Los PCs hacen push vía SSH; el servidor hace pull al working
  clone.

## R1 — Trailers 100 % post-corte en los tres repositorios

**EARS:**

Desde el commit de corte en que se instaló el hook `commit-msg` en cada
repositorio (identificado abajo por su sha y su fecha), el 100 % de los
commits no-merge en la rama `main` DEBE llevar los trailers `Chat:`,
`Model:` y `Plan:`, medido como igualdad (0 violaciones) y no como umbral.
Los commits anteriores al corte (inclusive) se listan como deuda histórica
con su recuento y no se reescribe la historia. Los merges están exentos
(B24: el hook `commit-msg` acepta merges de origin sin trailers).

### Commits de corte

| Repositorio | Cutoff SHA | Fecha | Deuda (no-merge sin trailers en main) |
|---|---|---|---|
| rag-banking-agent | — (sin deuda) | — | 0 |
| sypnose-plantilla | `d310a12f9e133869a0494ff17ac7623f558443b2` | 2026-09-17 23:49:38 +0200 | 63 |
| como-estoy-hecho | — (sin deuda) | — | 0 |

Para `rag-banking-agent` y `como-estoy-hecho` todos los commits no-merge en
`main` ya llevan los tres trailers desde el primer commit, por lo que no hay
commit de corte ni deuda. Para `sypnose-plantilla`, los 63 commits de deuda
corresponden al periodo 2026-09-14 a 2026-09-17 en que el repo se creó, el
caparazón se implementó (B1–B9) y se cargaron los scripts de enlace y del
stack de opciones (M6).

**Comprobación (determinista, sobre GitHub vía `gh api`):**

```bash
python plantilla/comprobar_trailers.py
```
