# T09 — Experience with Git and version control best practices

## Oferta (línea 9, literal de `oferta-coforge.txt`)

> Experience with Git and version control best practices

## Solución

La plantilla SYPNOSE implementa trazabilidad Git por diseño:

- **Rama por chat**: cada chat trabaja en `chat/<carpeta>`. La rama `main` se
  actualiza solo por merge desde ramas chat, nunca por commit directo.
- **Worktrees aislados**: cada chat tiene su worktree. Nunca dos chats tocan
  el mismo worktree.
- **Trailers obligatorios**: todo commit lleva al pie `Chat:`, `Model:` y
  `Plan:` como trailers Git.
- **Caparazón B5+**: `commit_msg.py` inyecta y valida los trailers; B24
  exime a los merges auto-generados por git.

## R1 — Trailers post-cierre en los tres repositorios

**EARS:**

Desde el commit de cierre en cada repositorio, el 100 % de los commits en
TODAS las ramas DEBE llevar los trailers `Chat:`, `Model:` y `Plan:` con
valores reales (no plantillas como `<...>` ni vacíos), medido como igualdad
(0 violaciones). Los commits anteriores al cierre se clasifican en tres
periodos con su recuento y causa. Los merges auto-generados por git (>1
parent, mensaje "Merge branch..." o "Merge remote-tracking branch...") están
exentos: git auto-genera su mensaje y B24 del commit-msg los acepta sin
trailers.

### Periodos

1. **Pre-hook** (deuda histórica): commits anteriores al hook `commit-msg`
   en el caparazón (`eae906f`, 2026-09-15 12:16:08 en sypnose-plantilla).
   No se reescribe la historia.
2. **Hook-a-cierre** (deuda de transición): commits posteriores al hook pero
   anteriores al cierre. Causas documentadas por repo.
3. **Post-cierre** (regla de igualdad): 0 violaciones exigido.

### Estado del cierre

El cierre es un job de CI (`check-trailers`) que rechaza PRs si algún commit
nuevo carece de `Chat:`, `Model:` o `Plan:` leídos con
`%(trailers:key=...,valueonly)`. Server-side, no depende de hooks locales.

**Hoy el cierre NO existe en ninguno de los tres repos.** La regla del 100 %
no es verificable aún: todos los commits post-hook caen en el periodo 2.
La comprobación sale roja — un rojo honesto.

### Análisis: sypnose-plantilla

Hook creado: `eae906fd62b9a9d783c7c51400004af5c4001704` (2026-09-15 12:16:08).
344 commits post-hook en todas las ramas. 48 no-merge sin trailers.

| Causa | Commits | Periodo | Detalle |
|---|---|---|---|
| Hook bootstrap | 17 | Sep 15 12:16–12:56 | Los commits B1–B9 que crearon el hook; chicken-and-egg |
| Worktree rollout | 26 | Sep 15 12:53–14:07 | Worktrees donde instalar_caparazon.py no se había ejecutado aún |
| Remote sin hook | 5 | Sep 17 23:16–23:49 | Commits m6/stack en github/main desde worktree sin hook instalado |

Merges auto-generados en main sin trailers: 19 (exentos por B24).
Deuda pre-hook: 63 commits (Sep 14–15 antes de eae906f).

### Análisis: rag-banking-agent

No hay SHA de hook ni de cierre en este repo. El hook se instaló
externamente vía `instalar_caparazon.py` (en plantilla repo, no aquí).
15 commits sin trailers (todos del Sep 14, antes de que el hook existiera),
distribuidos en 6 ramas:

| Rama | Commits sin trailers |
|---|---|
| chat/01-git-cicd | 5 |
| chat/03-datos-rag | 4 |
| backup/02-backend-api | 2 |
| fix/02-trivy-version | 2 |
| fix/01-trivy-tag | 1 |
| fix/04-trivy-cve-real | 1 |

Main: 0 violaciones (todos los commits en main tienen trailers).

### Análisis: como-estoy-hecho

Repo creado 2026-09-16, después del hook. 0 violaciones en todas las ramas.
9 commits no-merge, todos con trailers completos.

### Comprobación

```bash
python plantilla/comprobar_trailers.py
```

Repos locales explícitos:

```bash
python plantilla/comprobar_trailers.py --repo rag-banking-agent:../wt --repo sypnose-plantilla:. --repo como-estoy-hecho:../../como-estoy-hecho
```
