═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-5) / TO: 00-lead · 07-verificador · Carlos / KEY: fase4-caparazon-150926

# FASE 4 — EL CAPARAZÓN (TRASPASO-4 §2, B1–B9)

**Estado (16-sep-2026):** B1–B17 + túnel aviso + descubrimiento de planes + auditoría merge + descriptor de fichero + forma_pura multi-worktree construidos con las decisiones del lead
(cola local, grafo del repo, propuesta de canal, Stop en continuación, ENTREGA solo con comprobación en verde, pie de commit en el
último párrafo, comprobación ejecutada tal cual y contra la base del registro, barrera de escritura en vivo, multi-plan, bloqueo SSH-git,
casefold Windows, aviso reintentable, aviso y bloqueo por túnel caído, descubrimiento de planes nuevos en cada prompt, auditoría git
que distingue merge-brought de escrituras propias, tokenizador de cerco que distingue descriptores de fichero de rutas,
forma_pura que acepta cd a worktrees_extra y plan.worktree).
- **163/163 pruebas de bloqueo CUMPLE** en modo local (1a98768). Incluyen los 19 casos de los scripts de 07 (`x3_trailers.py`,
  `x3_entrega2.py`, `x3_entrega3.py`), los controles de `~` de `x3_entrega4_controles.py`, 6 casos B14 (B6.28–B6.29d), 7 casos
  B15 (B6.30–B6.31d), 3 casos B20 (B20.0–B20.2), 2 casos B21 (B21.0–B21.1) y 2 casos B22 (B22.0–B22.1). `probar_instalador.py` también CUMPLE.
- **X3 real CUMPLE** según 07 (evento `verificado` 22574, evidencia 182, leídos en el registro). Lo examinó en solo lectura sobre la
  sesión real de 02, con los módulos de 78665a5: cerco en vivo, ENTREGA válida de la tarea 48 y cola conservada con la KB caída (§4.4).
  78665a5 en local también CUMPLE (22580).
  - Las dos notas que dejó abiertas están cerradas: la KB retenía el registro y la evidencia no traía el resumen de pytest (§8).
    e215054 en local CUMPLE: evento 22595, evidencia 189. 07 confirmó también el diagnóstico de `-qq`.
  - La tarea 48 pasó a `espera_firma` (evento 22593).
  - cc2ad8f (`bloqueo:kb_caida`) en local CUMPLE: evento 22606, evidencia 198.
  - faab629 (rutas de shell normalizadas y `worktrees_extra`) en local CUMPLE: evento 22639, evidencia 210. 07 da por conservador el
    límite del destino relativo con `-C`.
  - B10 (59c498e, sesión sin tarea) y B11 (356d11b, el cerco lee el comando entero) en local CUMPLE: 128/128 desde una copia
    `git archive`, evento 22702 y evidencia 226.
  - B12 (f1ef77f, requisito vigente) en local CUMPLE: 132/132 desde el scratchpad, eventos 22721–22722 y evidencia 228.
- 07 dio X3 local CUMPLE provisional sobre 2ad5a54, 700d77c, 34ded4a, 0def414, 9c33f03 y **b33c05f**. Para b33c05f:
  - evento `verificado` 22479 en PLAN-CS-T01, leído en el registro;
  - 97/97 sobre un `git archive` limpio y `probar_instalador.py` CUMPLE;
  - barrera 14/14 con su `x3_barrera.py`, sin conexión a la red, con el registro vivo intacto (máximo 22477 antes y después);
  - residual: `INSTALADO` se puede falsificar a mano (§8, límites conocidos).

  Está corregido todo lo que dejó abierto:
  - (a) y (b): salida en rojo, o que no cumple lo esperado;
  - el exit code;
  - (e) `| grep`, (f) `; echo 1` y (k) `echo` del texto de la comprobación;
  - claves de pie repetidas y `Nota:` absorbida como trailer;
  - (s) consulta contra una base de datos preparada;
  - la ruta `~/sypnose-f1/registry.db` no contaba cuando el config la escribía con `~`.
- **Incidente del 15-sep 12:34Z:** el arnés de 07 escribió eventos de prueba en el registro vivo a través de los hooks. Está construida
  la barrera del lead: solo se escribe en vivo con `SYPNOSE_MODO=real`, el marcador `INSTALADO` y la sesión en la carpeta (§2 B4, B4.4–B4.9).
- Modo real: lo activó el lead en 02 por delegación de Carlos (evento 22532), que Carlos confirmó en este chat el 15-sep. 08 no
  instaló (§4.4).
- Instalador idempotente y reversible.
- SessionStart y UserPromptSubmit comprobados en una sesión real de Claude Code.
- Vista previa real del brief de 02 (§4.7).
- Repo `plantilla`, rama **`chat/08-caparazon` en origin, punta `a89d1e6`** (B19); worktree propio `C:\MICD\Coforge Santander\08-caparazon\wt-plantilla`.
  main = **9f891bb** (merge B19 a89d1e6). Instalado en 01 (modo real). B19 pendiente de verificación por 07.
- **Caparazón instalado en modo real** en 01-git-cicd (evento 22786), 03-datos-rag (22789) y 04-agentes (22790), por delegación del
  lead (22676). 02 reinstalada con B13 por el arquitecto; verificada por 08 en solo lectura (§4.4).

## 0. Dónde está y en qué se apoya

```
08-caparazon/wt-plantilla/caparazon/        (worktree del repo plantilla, rama chat/08-caparazon)
  caparazon/    comun.py cerco.py brief.py prompt_submit.py pre_tool_use.py post_tool_use.py stop.py
                commit_msg.py model_switch.py flush.py cabeceras_github.py     → se copian a <chat>/.claude/caparazon/
  plantillas/   settings.json  mcp.json  CLAUDE.caparazon.md
  instalar_caparazon.py   .gitignore
  pruebas/      probar_bloqueos.py  registro_minimo.sql
```
- **Contrato de hooks:** `code.claude.com/docs/en/hooks.md`, leída el 15-sep (Claude Code 2.1.267).
  - exec form (`command` + `args`, sin shell);
  - exit 2 bloquea en PreToolUse, UserPromptSubmit y Stop; SessionStart no puede bloquear;
  - Stop recibe `last_assistant_message` y `stop_hook_active` (la doc pide mirarlo para no bloquear en bucle; a los 8 bloqueos
    Claude Code corta);
  - un Bash o PowerShell que termina con exit code distinto de 0 **no** dispara PostToolUse sino **PostToolUseFailure**, con
    `error` = `Exit code N` + la salida;
  - el modelo solo llega en `SessionStart.model` y en PostModelSwitch;
  - un hook `async` no bloquea y su `systemMessage` no se muestra al usuario.
- **Reutilizado de GitHub:**
  - `disler/claude-code-hooks-mastery` (`pre_tool_use.py`) → cerco;
  - `disler/claude-code-hooks-multi-agent-observability` (`send_event.py`) → canal de eventos, cambiado: allí un envío fallido se
    pierde, aquí queda en cola y se avisa;
  - `anthropics/claude-code` `examples/hooks/bash_command_validator_example.py`;
  - `GowayLee/cchooks` descartado (solo biblioteca estándar).

## 1. Arquitectura

| Pieza | Cómo |
|---|---|
| Lectura del registro | API `SYPNOSE_REGISTRO_URL` (defecto `http://127.0.0.1:7101`, túnel): `/salud`, `/planes`, `/plan/<id>`. Solo leen el SessionStart y los prompts de una sesión abortada |
| Cola local (decisión lead) | `<carpeta>/.claude/caparazon/cola/<session_id>.jsonl`. Cada hook añade sus operaciones y termina en 0,24–0,36 s sin tocar la red |
| Envío | `flush.py --si-toca 60` como hook async de PostToolUse, el Stop y el SessionStart. Orden (lead, 15-sep): `/salud` → un lote atómico al registro por SSH → KB. Si falla el registro, la cola entera se queda; si solo falla la KB, se quedan `kb_guardar` y su `leccion_guardada` (marcado `tras_kb`), que llega al registro cuando la KB guarda la lección; en ese momento se registra `bloqueo:kb_caida` con las operaciones retenidas y su evidencia |
| Idempotencia | Un evento con la misma `(cuando, actor, accion, plan_id, detalle)` no se repite; evidencia por su PK; `tarea_progreso` solo si su evento no existe; KB por clave. `evento.firma` no se usa: es el raíl de certificación |
| Registro caído | Aviso visible en la siguiente herramienta o prompt, cola conservada y `bloqueo:registro_caido` + evidencia al volver. Un SessionStart sin registro aborta porque no puede verificar el plan |
| Ejecuciones de comandos | PostToolUse (éxito) y PostToolUseFailure (exit code distinto de 0) guardan comando, directorio, salida (completa si es la comprobación) y exit code. Una ejecución solo cuenta como comprobación si es **exactamente** la comprobación (con `cd <worktree> &&` delante como mucho), y el Stop valida contra la última |
| KB | knowledge-hub HTTP `SYPNOSE_KB_URL` (defecto `http://127.0.0.1:18791`) |
| GitHub | `gh` (CLI autenticado en el PC): CI y PR en el brief; el MCP github es opcional (`gh auth token`) |
| Túnel | `ssh -N -i ~/.ssh/id_ed25519_radelqui -p 2024 -L 7101:127.0.0.1:7101 -L 18791:127.0.0.1:18791 -L 18793:127.0.0.1:18793 sypnose@62.171.147.46` |

### Dependencia del túnel SSH

El caparazón depende de un túnel SSH local que conecta tres puertos al servidor 67 (VPS Sypnose):

| Puerto local | Servicio remoto | Impacto si cae |
|---|---|---|
| 7101 | Registro SYPNOSE (API `/salud`, `/planes`, `/plan/<id>`) | **Crítico:** SessionStart no puede verificar el plan → estado `registro_caido`, bloquea prompts y escrituras. Cada prompt nuevo reintenta la conexión |
| 18791 | Knowledge Hub HTTP (lecciones, KB) | **Degradado:** las lecciones y `bloqueo:kb_caida` se quedan en la cola local; el registro funciona y la ENTREGA se acepta. Al volver, la cola se vacía y se registra `bloqueo:kb_caida` |
| 18793 | Knowledge Hub SSE (MCP `knowledge-hub`) | **Menor:** el servidor MCP queda inaccesible; los hooks no lo usan directamente |

El comando completo está en `config.json` (`ssh.clave`, `ssh.puerto`, `ssh.destino`) y `comun.comando_tunel(cfg)` lo devuelve:
```
ssh -N -i ~/.ssh/id_ed25519_radelqui -p 2024 -L 7101:127.0.0.1:7101 -L 18791:127.0.0.1:18791 -L 18793:127.0.0.1:18793 sypnose@62.171.147.46
```

**Comportamiento con el túnel caído (7101):**
- `brief.py` (SessionStart): detecta `RegistroCaido` → estado `abortado_tipo: registro_caido` → aviso "Túnel 7101 caído — remedio:
  `<comando>`" + `bloqueo:registro_caido` en la cola.
- `prompt_submit.py` (UserPromptSubmit): si el estado es `registro_caido` → exit 2 con "CAPARAZÓN ABORTADO: túnel 7101 caído.
  Remedio: `<comando>`".
- Cada prompt nuevo vuelve a consultar el registro: en cuanto el túnel se levanta, la sesión recoge su plan y trabaja.
- El flush del SessionStart envía las colas retenidas y registra `bloqueo:registro_caido` con evidencia.

**Detección:** `comun.leer_registro(url, ruta, cfg)` lanza `RegistroCaido` cuando `/salud` no responde (timeout 5 s o error de
conexión).

## 2. Módulos

### B1 · `brief.py` (SessionStart)
**Cómo:**
- Envía las colas pendientes.
- Elige un plan `abierto` con dueño `H:` y en él la tarea por prioridad **devuelta > trabajando > pendiente**. `espera_firma`,
  `hecha` y `bloqueada` no se trabajan; si solo hay de esas, ABORTADO.
- Si la tarea está devuelta, enseña el motivo.
- Añade al brief:
  - requisito;
  - archivos permitidos;
  - presupuesto;
  - grafo (worktree o `origin/main|main`);
  - GitHub con `gh`;
  - si la comprobación es SQL, la única forma de ejecutarla que cuenta (`ssh -i <clave> -p <puerto> <destino> "sqlite3 <bd del registro> …"`);
  - última lección;
  - el formato de entrega: solo vale una comprobación que pasa; salidas `PREGUNTA:`/`BLOQUEADO:`; cierre como entrega incompleta.
- Encola y envía: actor con su modelo real, `sesion_iniciada` y tarea → `trabajando`.
- Sin plan, tarea, requisito, cerco o registro → **ABORTADO** + `bloqueo:brief`.

**Cómo se comprueba:** B1, B1.2, B6.6, B7.8, B7.9 y §4.7.

### B2 · `prompt_submit.py` (UserPromptSubmit)
**Cómo:** sin red salvo en una sesión abortada (reconsulta; si sigue abortada, exit 2). Añade la EARS, la comprobación y los
permitidos, y un aviso si la cola no llega. Si la sesión no pasó por SessionStart (abierta antes de instalar el caparazón), el primer
prompt crea el estado, registra `sesion_iniciada` con "sin SessionStart: estado creado por UserPromptSubmit" y entrega el brief
completo una sola vez.

**Por qué:** en la sesión real de 02 los hooks se cargaron a mitad de sesión y el brief no llegó al modelo.

**Cómo se comprueba:** B2, B2.1 y B2.2.

### B3 · `pre_tool_use.py` + `cerco.py`
**Cómo:**
- Las rutas de escritura de herramientas de fichero y de shell se normalizan con `norm()`: `/c/…` de Git Bash, `~` y rutas relativas
  al `cwd` de ese punto del comando.
- Cada escritura se mide contra el worktree que la contiene (el del chat o uno de `worktrees_extra`, el más interno) y sus permitidos.
  Los permitidos admiten ficheros, carpetas acabadas en `/` y globs (`**`, `*`, `?`). Fuera → exit 2 + `bloqueo:cerco`.
- `git -C <dir>` y `--work-tree <dir>` valen dentro de esos worktrees. `git clone <repo> <dir>` y `git worktree add <ruta>` cuentan
  como escritura en `<dir>` y `<ruta>`.
- No depende del registro.

**Por qué:** en la sesión real de 02 el chat no podía escribir su spec en el repo plantilla, y con Python 3.13 las rutas `/c/…` y `~`
se medían mal.

**Cómo se comprueba:** B3.1–B3.14, B7.1, B7.2 y los ataques de 07 (relativa, traversal, mayúsculas, `wt-malo`, MultiEdit,
NotebookEdit, `python open`, `tee`, `cp`, `cd ..`, `Set-Content`, `.claude\settings.json`): todos bloqueados.

### B4 · `post_tool_use.py` (PostToolUse y PostToolUseFailure) + `flush.py` + `model_switch.py`
**Cómo:**
- Encola `herramienta:<Tool>` con ruta, hora, tokens y coste del turno.
- En PostToolUseFailure de Bash/PowerShell encola `herramienta_fallida:<Tool>` con `exit_code=N`.
- Guarda cada comando con su directorio, su salida (completa si es la comprobación, recortada si no) y su exit code. Una herramienta
  fallida no cuenta como escritura ni como aviso a 07.
- Auditoría `git status` → `bloqueo:cerco`. Nunca `continue:false`.
- **Barrera de escritura en vivo** (`comun.motivo_modo_prueba`, decisión del lead tras el incidente del 15-sep 12:34Z). La cola solo
  va al registro por ssh o a la KB real si se cumplen las tres condiciones:
  1. `SYPNOSE_MODO=real`, que pone `instalar_caparazon.py --modo real` en `.claude/settings.json`;
  2. los módulos que se ejecutan son la instalación de la carpeta del config (`<carpeta>/.claude/caparazon`), con el marcador
     `INSTALADO` que solo escribe el instalador y que apunta a esa carpeta;
  3. el `cwd` de la sesión está en esa carpeta o en su worktree.

  Si falta alguna, el envío devuelve `modo prueba`: no sale nada, la cola se conserva sin anotar fallo, y el Stop y el brief avisan
  con "MODO PRUEBA: … Falta: …".
  - No cuentan como destinos en vivo un sqlite local de pruebas (`SYPNOSE_REGISTRO_ESCRITURA=sqlite:<ruta>`) ni una KB local explícita
    (`SYPNOSE_KB_URL` a 127.0.0.1 en un puerto distinto del túnel 18791).
  - `escribir()` y `kb_guardar()` repiten la comprobación por si alguien los llama directamente. Las consultas de solo lectura no
    pasan por la barrera.

**Por qué (barrera):** el arnés de 07 ejecutó los hooks desde una copia con `SYPNOSE_REGISTRO_ESCRITURA=ssh`, el destino real y la
clave del PC, y escribió 14 eventos y 2 evidencias de prueba en el registro vivo (eventos 22437–22450, evidencias 148 y 149). Instalar
ya no basta para escribir en vivo: hay que pedirlo, y solo vale desde la instalación.

- **Auditoría git también en los worktrees extra** (lead, 15-sep): lo que un Bash deje cambiado fuera de sus permitidos se bloquea
  después, con la foto inicial de cada worktree guardada en el estado (`sucios_inicio_extra`). Una sesión anterior a este cambio toma
  la foto en su primera auditoría.

**Cómo se comprueba:** B4.1–B4.3, B4.4–B4.9 (barrera), B4.10–B4.11 (worktree extra), B9.1, B6.2, B6.2a, B6.2c, B6.2e, B6.4, B6.7,
B6.8, B6.9a, B6.9c, B6.11, B7.3–B7.5.

### B5 · `commit_msg.py` + `githooks/commit-msg`
**Cómo:**
- `Chat:`, `Model:`, `Plan:` y `Tarea:` tienen que ir en el **último párrafo** del mensaje, junto a `Co-Authored-By` y sin línea en
  blanco (regla del lead, para que `git log --format=%(trailers)` los lea).
- Si llegan en párrafos finales separados que solo tienen claves conocidas (Chat, Model, Plan, Tarea, Co-Authored-By, Signed-off-by),
  el hook los une reescribiendo el mensaje y confirma con `git interpret-trailers --parse` que git los reconoce. Un párrafo como
  `Nota: …` es cuerpo y no se une.
- Si faltan, están repetidos, están en medio del cuerpo o sus valores no cuadran (carpeta, id de modelo, plan abierto, tarea) → exit 1
  + `bloqueo:commit-msg`.

El instalador engancha también commit-msg en cada worktree extra que ya exista (`core.hooksPath` solo de ese worktree), así que los
commits del spec en el repo plantilla llevan el mismo pie.

**Cómo se comprueba:** B5.1, B5.2, B5.4–B5.7, B7.6 (B5.3 en real), los 8 casos de `x3_trailers.py` de 07 (07-T1–07-T8) y
`probar_instalador.py` para el enganche en el worktree extra.

### B6 · `stop.py` (Stop)
**Cómo:**
- **Primer intento** con escrituras y sin `ENTREGA` válida → exit 2 + `bloqueo:entrega`.
- **La ENTREGA es válida solo si se cumple todo:**
  1. cita la comprobación;
  2. la última ejecución que menciona la comprobación es **exactamente la comprobación**, regla del lead tras las evasiones (e), (f) y
     (k) de 07:
     - solo se admite `cd <worktree> &&` delante;
     - sin tuberías, `;`, `&&`/`||` añadidos, `echo`, redirecciones ni sustituciones;
     - dentro del worktree;
     - una consulta SQL va contra la **base del registro configurado** (`config.ssh.db` en el servidor `config.ssh.destino`):
       - por ssh: `ssh [-i clave] [-p puerto] [-o BatchMode/ConnectTimeout/ServerAlive…] [-q] [-T] <destino> "sqlite3 [opciones de formato] <bd> …"`;
       - `sqlite3 <bd>` directo solo si el registro configurado es un sqlite local;
       - `~` se expande al home del usuario del destino antes de comparar, en el config y en el comando: `~/sypnose-f1/registry.db` y
         `/home/sypnose/sypnose-f1/registry.db` son la misma BD, y la escritura usa siempre la ruta absoluta;
       - otra BD, otro host u otras opciones de ssh o sqlite3 (`-o HostName`, `-J`, `-cmd`…) → no cuenta.

     Esa ejecución no se interrumpió, terminó con **exit code 0** y en su salida **completa** no hay marcadores de fallo:
     `N failed/errors/failures`, líneas que empiezan por `FAILED`/`ERROR`/`FAIL`, `error:`, `parse/runtime/syntax/fatal error`,
     `Traceback (most recent call last)`, `exit code N` o `no tests ran`;
  3. si la comprobación trae `→ esperado`:
     - con `≥`, `>=`, `≤`, `<=`, `>`, `<`, `=`, `==` o un número solo, la salida completa tiene que ser un único valor (como mucho con
       una línea de cabecera) y cumplir la comparación;
     - si lo esperado no es numérico, debe aparecer en la salida;
  4. alguna línea real de esa salida aparece literal en el bloque (una línea corta debe ser una línea del bloque);
  5. trae `LECCIÓN:`;
  6. hubo `send_message` a 07 con ENTREGA.
- **Válida** → lección + `tarea_entregada`, `leccion_guardada`, `aviso_verificador` + evidencia `entrega:<carpeta>`.
  - La evidencia y `tarea_entregada` llevan la **línea de resumen** de la salida real (`N passed in …`, `Ran N tests`, `OK`), aunque la
    línea pegada sea otra. Si la salida no trae resumen, lo dicen: "(la salida no trae línea de resumen)".
  - La evidencia guarda además la **salida completa** de esa ejecución (hasta 3000 caracteres; si es más larga, los últimos 3000).
  - `leccion_guardada` solo llega al registro cuando la KB ha guardado la lección.
- **Continuación** (`stop_hook_active=true`) → no vuelve a bloquear: cierra con aviso "CIERRE SIN ENTREGA VÁLIDA" y
  `bloqueo:entrega_incompleta` + evidencia, nunca como entregada.
- **Última línea `PREGUNTA:` o `BLOQUEADO:`** → cierra al primer intento como `pregunta_humano`.
- **Cada Stop envía la cola.**

**Cómo se comprueba:** B6.1–B6.18 (con B6.2a–B6.2l y B6.9a–B6.9o), B1.3, B7.7 y los casos de 07: `x3_entrega2.py` (07-E1–07-E5) y
`x3_entrega3.py` (07-E6–07-E11).

### B7 · plantillas
- **`settings.json`:** SessionStart, UserPromptSubmit, PreToolUse, PostToolUse (+ `flush.py` async), **PostToolUseFailure
  (`Bash|PowerShell`)**, Stop y PostModelSwitch, en exec form. `allow` git/pytest/ruff; `deny` Edit/Write en `.claude/**` y
  `.mcp.json`, `Read(//**/.env)`, `git push/config/reset --hard`.
- **`.mcp.json`:** `sypnose` SSH-stdio (node 22) · `knowledge-hub` SSE 18793 · `github` opcional con `gh auth token`.
- **Comprobado:** handshake sypnose (4 tools), SSE `event: endpoint`, GitHub MCP `HTTP 200`.

### B8 · `instalar_caparazon.py`
**Cómo:**
- copia los módulos y `plantilla/precios.yaml`;
- escribe el marcador `INSTALADO` con la carpeta y el worktree de la instalación;
- fusiona con respaldo `settings.json` (incluido `env.SYPNOSE_MODO`: `prueba` por defecto, `real` con `--modo real`), `.mcp.json` y la
  sección de CLAUDE.md;
- `--worktree-extra "<ruta>:<patrón>[,<patrón>]"` (repetible) escribe `worktrees_extra` en `config.json` (p. ej.
  `C:\MICD\Coforge Santander\02-backend-api\wt-plantilla:specs/T01/**`) y engancha commit-msg en ese worktree si ya existe. Si todavía
  no existe, avisa: el cerco ya lo admite y el enganche se hace al reinstalar;
- `--desinstalar` retira solo lo suyo, también el marcador, `SYPNOSE_MODO` y el enganche de los worktrees extra.

**Por qué:** instalar ya no basta para escribir en vivo; el modo real se pide al instalar.

**Cómo se comprueba:** `pruebas/probar_instalador.py` (§4.2) y la instalación temporal de B4.4–B4.9.

### B9 · `pruebas/probar_bloqueos.py`
**Cómo:**
- `--modo local`: sqlite temporal con el esquema real, API y KB simuladas y, al final, el estado real de PLAN-CS-T01. Lleva
  `SYPNOSE_MODO=prueba` y `ssh.bin` apunta a un ejecutable que no existe: aunque la barrera fallara, nada saldría a la red.
- `--modo real`: caparazón instalado con `--modo real` (exige el marcador `INSTALADO`) y registro del 67, con `SYPNOSE_MODO=real` y
  `--actor`.

### B10 · sesión sin tarea (decisión del lead, 15-sep)
**Requisito (EARS):** CUANDO el chat no tenga tarea abierta en su plan, UserPromptSubmit DEBERÁ dejar pasar el prompt (exit 0) con el
aviso, y PreToolUse DEBERÁ bloquear (exit 2, mismo aviso) Edit/Write/MultiEdit/NotebookEdit y los Bash que cambien algo, dejando pasar
Read/Grep/Glob, el Bash de solo lectura y las llamadas MCP. El prompt solo se bloquea con el caparazón abortado por registro caído.

**Cómo:**
- `brief.abortar` distingue dos tipos. `registro_caido` (no se pudo verificar el plan) mantiene el bloqueo de prompts y escrituras.
  `sin_tarea` cubre el resto: plan sin trabajo abierto para el rol, plan sin abrir por un humano, requisito inexistente o cerco sin
  permitidos. El brief de `sin_tarea` se titula "SIN TAREA" y trae el aviso.
- Aviso literal: "Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar
  comandos que cambien nada hasta que el arquitecto le abra una tarea en <plan>."
- `prompt_submit.py` sin tarea: exit 0 con el aviso en `additionalContext` y en `systemMessage`, más el detalle del motivo. Cada
  prompt vuelve a consultar el registro: en cuanto el arquitecto abre una tarea, la sesión trabaja.
- `pre_tool_use.py` sin tarea: bloquea Edit/Write/MultiEdit/NotebookEdit con el aviso y deja pasar las herramientas de lectura. Un
  Bash/PowerShell solo pasa si `cerco.solo_lectura()` lo reconoce como consulta:
  - sin sustituciones `$(…)` ni comillas invertidas y sin escrituras detectadas;
  - órdenes de una lista cerrada (ls, cat, grep, find sin -delete/-exec, wc, head, Get-Content…);
  - git solo en sus formas de consulta (status, log, diff, show, branch sin cambios, `worktree list`, `stash list`, `config --get`…).

  Lo que no reconoce cuenta como cambio: `git commit`, `pip install`, `python`, `bash -c`… se bloquean.
- Una sesión anterior al cambio sin `abortado_tipo` se clasifica por su motivo: "REGISTRO SYPNOSE CAÍDO…" → registro caído; el
  resto → sin tarea.

**Por qué:** en 02, `prompt_submit.py` bloqueó un prompt de Carlos con "CAPARAZÓN ABORTADO: prompt bloqueado. PLAN-CS-T01 no tiene
trabajo abierto…". Un humano nunca puede quedarse sin poder hablar con su chat.

**Cómo se comprueba:** B1.4, B2.3, B2.4 y B3.15–B3.19 (§4.1).

### B11 · el cerco lee el comando entero (decisión del lead, 15-sep)
**Qué pasó (evento 22672):**
- En 02 se bloqueó `cd "/c/MICD/Coforge Santander/02-backend-api/wt-plantilla" && git commit -m "$(cat <<'EOF' … EOF)" 2>&1`, el
  commit del spec, con "c:\micd\coforge\pytest está fuera del worktree".
- La orden `cd "…\wt" && pytest …` que parecía la culpable es el evento 22667, y pasó.
- El cerco analizaba el comando línea a línea:
  - leía el cuerpo del heredoc (el mensaje del commit) como órdenes, y la flecha de "`-q` explícito -> pytest sube a -qq" salía como
    los tokens `-`, `>`, `pytest`: una redirección a un fichero "pytest";
  - en la primera línea la comilla doble se cierra líneas más abajo, shlex fallaba y el respaldo `split()` partía "Coforge Santander"
    por el espacio, así que el directorio quedaba en `c:\micd\coforge`.

**Cómo:**
- `_preparar()` sigue las comillas como bash antes de tokenizar:
  - quita los cuerpos de heredoc (`<<EOF`, `<<'EOF'`, `<<-EOF`), que son datos;
  - quita los comentarios y las continuaciones de línea;
  - convierte en `;` los saltos de línea fuera de comillas;
  - un `<<` dentro de comillas o de `$((…))` no es heredoc; uno dentro de `$(…)` o `` `…` `` sí.
- `_tokens()` pasa shlex por el comando entero, ya preparado. Si no puede tokenizar, lanza `ComandoIlegible`: no hay respaldo que
  parta por espacios.
- `pre_tool_use.py` bloquea un comando ilegible con "el cerco no puede leer este comando (…): revisa las comillas o pasa el mensaje por
  fichero: git commit -F <fichero>". El cerco nunca adivina rutas: fail loud.
- `solo_lectura()` (B10) trata un comando ilegible como cambio.

**Por qué:** el cerco bloqueaba un commit legítimo del spec por palabras del texto del mensaje, y un fallo del tokenizador le hacía
adivinar rutas.

**Cómo se comprueba:** B3.20–B3.24 (§4.1). Además, probado aparte con los tres comandos reales de 02 de las 16:10–16:11 (ningún
destino) y con formas límite: `$((1<<2))`, comentario con apóstrofo, continuación de línea, `bash -c` y `git commit -F - <<'EOF'`.

### B12 · el requisito vigente sale del registro (decisión del lead, 15-sep)
**Qué pasó (eventos 22685–22693 de 02):**
- El arquitecto cambió en el registro la comprobación de R1 a `pytest tests/test_main.py tests/test_engine_mode.py`, sin `-q` (22685,
  16:29:15Z).
- 02 entregó con el comando nuevo y el Stop lo rechazó: "no cita la comprobación literal `… -q`" (22690). 02 repitió con `-q` y el Stop
  lo aceptó (22693).
- Causa: el Stop validaba contra `estado["requisito"]`, la foto que guarda `construir_estado` al coger la tarea (la sesión de 02 la
  cogió antes de 22685). En una sesión viva y no abortada nada la refrescaba.
- Descartado: el registro tiene una sola fila por requisito (PRIMARY KEY (plan_id, ref)) y la API `/plan` ya devolvía el texto nuevo.

**Cómo:**
- `brief.refrescar_trabajo()` lee `/plan/<plan>` y actualiza en el estado el requisito vigente (EARS y comprobación), el progreso de la
  tarea y los permitidos. Devuelve los cambios vistos. Si la tarea ya no se puede trabajar o el plan ya no está abierto, reconstruye el
  estado (con B10, sin tarea).
- Stop: refresca antes de validar una ENTREGA y valida contra el requisito vigente. Si la comprobación cambió, el rechazo lo dice
  ("la comprobación de R… cambió en el registro: ahora es `…` (antes `…`)").
- Con el registro caído, la ENTREGA se bloquea con "no se pudo confirmar la comprobación vigente: registro caído; reintenta la
  ENTREGA cuando vuelva" y `bloqueo:registro_caido` en la cola. Una entrega es un punto de juicio: no se entrega contra la foto.
- UserPromptSubmit: refresca en cada prompt, inyecta la EARS y la comprobación vigentes y avisa de los cambios. Con el registro caído
  usa la foto solo para conversar, y lo avisa.

**Por qué:** 22693 se aceptó contra un requisito que ya no estaba vigente, y la entrega buena se había rechazado. Qué hacer con 22693 lo
decide 07 (el lead le pide devolver la tarea 49 para volver a entregar con la comprobación vigente).

**Cómo se comprueba:** B6.23, B6.23b, B2.5 y B6.24 (§4.1).

### B13 · varias tareas trabajables en el mismo plan (decisión del lead, 15-sep)
**Qué pasó:** 02 tiene tres tareas trabajables en PLAN-CS-T01:
- la 9 (R1), trabajando y ya entregada (22712);
- la 48 (R1), devuelta;
- la 49 (R1), trabajando y entregada (22693).

El estado de la sesión fija UNA tarea, así que 02 no podía entregar la segunda hasta que 07 juzgara la primera. Leído en el registro,
en solo lectura (última entrega y último inicio de cada tarea):
```
id|req_ref|progreso|agente|ult_entrega|ult_inicio
9|R1|trabajando|IA:02-backend-api:claude-sonnet-5|22712|22706
33|R0|espera_firma|IA:02-backend-api:claude-sonnet-5||
48|R1|devuelta|IA:02-backend-api:claude-sonnet-5|22560|22534
49|R1|trabajando|IA:02-backend-api:claude-sonnet-5|22693|22655
```

**Cómo:**
- **Entregada y pendiente de juicio** es una tarea `trabajando` con un `tarea_entregada` posterior a su último `tarea_trabajando`, que
  marca el inicio de su ciclo.
  - `brief.pendientes_de_juicio()` lo consulta en el registro con un SELECT (op `consulta`), así que vale entre sesiones.
  - Suma las entregas que sigan en la cola local.
  - Si la consulta falla, vale lo que sabe la sesión y lo avisa.
- **B13.1:** con más de una tarea trabajable, el brief y el contexto de cada prompt llevan la lista
  "Tus tareas trabajables en <plan>: tarea <id> · <requisito> · <progreso> · entregada: sí/no | …", y cómo entregar otra con «Tarea: <id>».
- **B13.2:** si el bloque ENTREGA lleva `Tarea: <id>`, el Stop entrega esa tarea cuando se cumplen tres condiciones:
  - es de `IA:<carpeta>:*` en el plan;
  - está abierta (pendiente, trabajando o devuelta);
  - no está entregada y pendiente de juicio.

  Se valida contra la comprobación vigente de SU requisito. Si la tarea estaba pendiente o devuelta, la entrega la pasa antes a
  trabajando con su `tarea_trabajando`. Si falla alguna condición, el rechazo dice cuál: "ENTREGA rechazada: la tarea N ya está
  entregada y pendiente de juicio de 07-verificador", "…no está abierta (espera_firma)" o "…no es una tarea de IA:<carpeta>:* en <plan>".
  Sin la línea, se entrega la tarea del estado, como hasta ahora.
- **B13.3:** en cada prompt, si la tarea del estado está entregada y pendiente de juicio y queda otra trabajable sin entregar, el
  caparazón reconstruye el estado:
  - elige primero las no entregadas y, entre ellas, devuelta > trabajando > pendiente y el menor id;
  - la pasa a trabajando;
  - lo dice ("la tarea N está entregada y pendiente de juicio: el caparazón pasa a la tarea M") y entrega el brief de la nueva tarea.

  Con las tareas de 02 de arriba pasará a la 48.
- **Coste:** la consulta por ssh solo se hace cuando el agente tiene dos o más tareas trabajables, con un máximo de 15 s por prompt
  (el hook tiene 30 s).

**Por qué:** una tarea entregada espera a 07, pero el agente puede adelantar las demás. Fijar una sola tarea bloqueaba a 02.

**Cómo se comprueba:** B6.25, B6.25b, B6.26, B6.26b, B6.26c, B6.27a y B6.27 (§4.1).

### B14 · varios planes abiertos (decisión del lead, 15-sep)
**Qué pasó:** 04-agentes tiene tareas en PLAN-CS-T02 y PLAN-CS-T12. El brief solo mostraba el plan activo y los permitidos del cerco
solo cubrían sus archivos; un chat con dos planes no podía entregar tareas del segundo.

**Cómo:**
- `brief.refrescar_trabajo()` fusiona tareas: las del plan activo salen frescas del registro; las de otros planes se conservan del
  estado. `planes_trabajables` lista todos los planes con tareas del agente. **B19:** también descubre planes nuevos abiertos después
  del SessionStart escaneando `/planes` en cada prompt, y los añade con sus tareas y permisos.
- El brief muestra `Plan: <id>` en la cabecera y la instrucción "Para entregar una tarea de otro plan, añade la línea `Plan: <id>`
  al bloque ENTREGA" cuando hay más de un plan.
- Los permitidos del cerco son la **unión** de los de todos los planes trabajables (fuente: `(unión multi-plan)`).
- `stop.py`: `Plan: <id>` en la ENTREGA selecciona el plan de la tarea a entregar; se valida contra `planes_trabajables`. **B19:**
  `tarea_de_entrega` consulta `/plan/<id>` en vivo antes de la caché; si el plan no está en `planes_trabajables`, verifica en el
  registro (estado abierto, dueño H:, tareas trabajables del agente con progreso pendiente/trabajando/devuelta) en vez de rechazarlo.
- `commit_msg.py`: `Plan:` se valida contra `planes_trabajables` (no solo el plan activo).

**Cómo se comprueba:** B6.28, B6.28b, B6.29, B6.29b, B6.29c y B6.29d (§4.1).

### B15 · bloqueo de git de escritura por SSH (orden del lead, 15-sep)
**Qué pasó (03-datos-rag, evento reportado por el arquitecto):** 03 usó SSH para hacer `git commit` directamente en
`~/coforge-santander/plantilla` del servidor 67, saltándose el flujo de PR. Los chats de tecnología solo deberían poder ejecutar scripts
de `plantilla/` (cargar_requisito.py, etc.) contra el registro por SSH, no escribir en el working clone del servidor.

**Cómo:**
- `cerco.py` añade `_comando_remoto_ssh(args)`: parsea opciones SSH con argumento (`SSH_OPTS_CON_ARG = set("bBcDEeFIiJLlmOopQRSwW")`)
  y extrae el comando remoto (todo lo que va después de `[user@]host`).
- `_objetivos_ssh(args)`: tokeniza el comando remoto, busca `git` como orden de cada segmento y comprueba con `_git_consulta()` si es
  de escritura. Si lo es, emite un marcador `SSH_REMOTO` (carácter nulo + descripción).
- `_segmento()`: cuando la orden es `ssh` y la profundidad < 3, llama a `_objetivos_ssh`.
- `veredicto()`: un marcador `SSH_REMOTO` se bloquea con "git de escritura por SSH bloqueado: <descripción>".
- `_segmento_lectura()`: verifica recursivamente los comandos SSH remotos para `solo_lectura()` (B10).
- `objetivos_shell()`: los marcadores `SSH_REMOTO` pasan sin normalizar (no son rutas).
- **Qué se bloquea:** `ssh host "git commit …"`, `ssh host "git push …"`, `ssh host "git checkout …"`, `ssh host "cd … && git add . && git commit …"`.
- **Qué pasa:** `ssh host "git log …"`, `ssh host "git status"`, `ssh host "sqlite3 …"`, `ssh host "python3 plantilla/…"`.

**Cómo se comprueba:** B6.30, B6.30b, B6.30c, B6.31, B6.31b, B6.31c y B6.31d (§4.1).

## 3. Entrada exacta de cada hook (para 07)

Invocación: `C:\Python313\python.exe "<carpeta>\.claude\caparazon\<hook>.py"` con JSON por stdin (`session_id`, `transcript_path`,
`cwd` además de lo indicado); `commit_msg.py` recibe la ruta del fichero de mensaje. Variables: `SYPNOSE_REGISTRO_URL` (caído =
`http://127.0.0.1:9`), `SYPNOSE_ACTOR`, `SYPNOSE_KB_URL`, `SYPNOSE_REGISTRO_ESCRITURA=sqlite:<ruta>` (solo pruebas) y `SYPNOSE_MODO`.
`SYPNOSE_MODO=real` solo tiene efecto en una instalación hecha con `--modo real`; en cualquier otro caso el envío en vivo devuelve
`modo prueba`. **Las pruebas no llevan nunca `SYPNOSE_REGISTRO_ESCRITURA=ssh` ni `SYPNOSE_MODO=real`.**

| Hook | stdin / argumentos | Resultado esperado |
|---|---|---|
| brief.py | `{"hook_event_name":"SessionStart","source":"startup","model":"claude-sonnet-5"}` | exit 0, "BRIEF CAPARAZÓN" con la tarea trabajable; sin trabajo → "ABORTADO" + `bloqueo:brief`; registro caído → "no se puede verificar el plan"; registro de vuelta → "bloqueo:registro_caido registrado" |
| prompt_submit.py | `{"hook_event_name":"UserPromptSubmit","prompt":"sigue"}` | exit 0 + EARS; sin tarea abierta → exit 0 con el aviso "Este chat no tiene tarea asignada en SYPNOSE…" (B10); registro caído → exit 2, "CAPARAZÓN ABORTADO: prompt bloqueado"; sin SessionStart previo (sesión abierta antes de instalar) → crea el estado, `sesion_iniciada` con "sin SessionStart: estado creado por UserPromptSubmit" y el brief completo una sola vez |
| pre_tool_use.py | `{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"C:\\MICD\\Coforge Santander\\02-backend-api\\_centinela_fuera.txt","content":"x"}}` | exit 2, "CERCO", `bloqueo:cerco` |
| pre_tool_use.py | `{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"echo x > ../_centinela_fuera.txt"}}` con `cwd` = worktree | exit 2, `bloqueo:cerco` |
| pre_tool_use.py | Bash `echo x > "/c/MICD/Coforge Santander/02-backend-api/_centinela_fuera.txt"`, `echo x > ~/_centinela_fuera.txt` o `cp app/main.py ../_centinela_fuera.txt` | exit 2; el mensaje lleva la ruta real (`c:\micd\…\_centinela_fuera.txt`, `c:\users\<usuario>\_centinela_fuera.txt`) y "fuera del worktree" |
| pre_tool_use.py | Write en `<worktree extra>/specs/T01/spec.md`, o Bash `git -C "<worktree extra>" add …`, con `worktrees_extra` en config | exit 0 |
| pre_tool_use.py | Write en `<worktree extra>/README.md`, o `git -C "C:\MICD\Coforge Santander\plantilla" worktree list` | exit 2, "fuera de archivos_permitidos … del worktree extra" / "fuera del worktree … y de los worktrees extra" |
| pre_tool_use.py | sesión sin tarea: Write, o Bash `echo x > app/main.py` o `git commit -m x && pip install requests` | exit 2 con el aviso "Este chat no tiene tarea asignada en SYPNOSE…" (B10) |
| pre_tool_use.py | sesión sin tarea: Read, o Bash `cd "<wt>" && git status --short && git log --oneline -3 && ls app && cat app/main.py \| grep -n def` | exit 0 (B10) |
| pre_tool_use.py | Bash `cd "/c/MICD/Coforge Santander/02-backend-api/wt-plantilla" && git commit -m "$(cat <<'EOF'` + mensaje de varias líneas con `->`, `"N passed"` y backticks + `EOF` + `)" 2>&1` | exit 0: el cuerpo del heredoc no se analiza (B11) |
| pre_tool_use.py | Bash `echo "hola > ../_centinela_fuera.txt` (comilla sin cerrar) | exit 2, "el cerco no puede leer este comando (No closing quotation): revisa las comillas o pasa el mensaje por fichero: git commit -F <fichero>" (B11) |
| pre_tool_use.py | Bash `cat <<'EOF' > ../_centinela_fuera.txt` con cuerpo, o una orden que escribe fuera después del terminador `EOF`, o después de un `echo "texto <<EOF"` | exit 2, "…_centinela_fuera.txt está fuera del worktree…" (B11) |
| post_tool_use.py | `{"hook_event_name":"PostToolUse","tool_name":"Write","tool_input":{"file_path":"…\\wt\\app\\main.py"},"tool_response":{}}` | exit 0, evento en la cola; con fallo de envío anotado → `systemMessage` "REGISTRO SYPNOSE NO RESPONDE" |
| post_tool_use.py | `{"hook_event_name":"PostToolUseFailure","tool_name":"Bash","tool_input":{"command":"…pytest…"},"error":"Exit code 1\n…1 failed…","is_interrupt":false}` | exit 0, `herramienta_fallida:Bash` con `exit_code=1`; la ejecución queda como la última |
| flush.py | stdin `{"session_id":"<sid>","cwd":"<worktree>"}`, args `--si-toca 0` | exit 0; registro vivo → cola vacía; caído → `fallo` anotado. Sin `cwd` en la entrada cuenta el directorio del proceso: `flush.py --sesion`/`--todas` a mano se lanza desde la carpeta |
| flush.py | stdin `{"session_id":"<sid>","cwd":"<worktree>"}` sin argumentos, con escritura ssh, desde una copia sin instalar, sin `SYPNOSE_MODO=real`, sin `INSTALADO` o con el `cwd` fuera | exit 0, stdout `{"estado": "prueba", "motivo": "…no son la instalación… / SYPNOSE_MODO=prueba, no real / no existe el marcador… / …fuera de…"}`; la cola se conserva y no se anota fallo |
| stop.py | `{"hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"He terminado."}` tras una escritura | exit 2, "CIERRE IMPEDIDO", `bloqueo:entrega` |
| stop.py | ENTREGA cuya última ejecución terminó con exit code 1, trae "2 failed" o da `0` frente a `→ ≥1` | exit 2, "ENTREGA rechazada: …exit code 1 / …indica fallo («2 failed») / …el resultado observado 0 no cumple lo esperado ≥1" |
| stop.py | ENTREGA cuya última ejecución fue `<comprobación> \| grep …`, `sqlite3 … "<consulta>"; echo 1`, `echo "<comprobación>" && echo …` o la comprobación en otra carpeta | exit 2, "no cuenta: lleva tuberías, ';', '&&'/'\|\|' o redirecciones" / "no cuenta: se ejecutó fuera del worktree" |
| stop.py | ENTREGA cuya consulta SQL fue contra otra BD (`sqlite3 /tmp/falsa.db …`), por ssh con `-o HostName=…` o con `sqlite3 -cmd …` | exit 2, "no cuenta: la base de datos /tmp/falsa.db no es la del registro configurado" / "ssh lleva la opción -o HostName=…, que no está permitida" / "sqlite3 lleva opciones o comandos que no están permitidos" |
| stop.py | ENTREGA con la consulta por ssh a `~/sypnose-f1/registry.db` y `ssh.db` absoluto en el config, o al revés | exit 0, entregada: `~` se expande al home del usuario del destino en los dos lados |
| stop.py | ENTREGA válida con `SYPNOSE_KB_URL` a un puerto cerrado (KB caída) | exit 0, "ENTREGA registrada en SYPNOSE" + "KB SIN RESPUESTA"; `tarea_entregada`, evidencia y `aviso_verificador` en el registro; `kb_guardar` y `leccion_guardada` en la cola hasta el siguiente envío con la KB viva, que registra además `bloqueo:kb_caida` ("N operaciones retenidas…") con evidencia |
| stop.py | ENTREGA con la comprobación vigente, cuando el registro la cambió después de construirse el estado de la sesión | exit 0, entregada contra la vigente (B12) |
| stop.py | ENTREGA con la comprobación antigua, cuando el registro la cambió | exit 2, "la comprobación de R… cambió en el registro: ahora es `…` (antes `…`)" (B12) |
| stop.py | ENTREGA con `SYPNOSE_REGISTRO_URL` a un puerto cerrado | exit 2, "no se pudo confirmar la comprobación vigente: registro caído; reintenta la ENTREGA cuando vuelva", `bloqueo:registro_caido` en la cola (B12) |
| brief.py / prompt_submit.py | SessionStart o `{"hook_event_name":"UserPromptSubmit","prompt":"sigue"}` con dos o más tareas trabajables del agente en el plan | exit 0; el brief y el contexto listan "tarea <id> · <requisito> · <progreso> · entregada: sí/no" de todas (B13.1) |
| prompt_submit.py | UserPromptSubmit cuando la tarea del estado ya está entregada y pendiente de juicio y queda otra trabajable sin entregar | exit 0; "la tarea N está entregada y pendiente de juicio: el caparazón pasa a la tarea M", "Requisito vigente de la tarea M" y el brief de M (B13.3) |
| stop.py | ENTREGA con la línea `Tarea: <id>` de otra tarea abierta del agente, con la comprobación de su requisito | exit 0, "ENTREGA registrada en SYPNOSE"; `tarea_entregada` "tarea <id> …" y la tarea en trabajando (B13.2) |
| stop.py | ENTREGA con `Tarea: <id>` de una tarea entregada pendiente de juicio, en espera_firma o de otro agente | exit 2, "ENTREGA rechazada: la tarea N ya está entregada y pendiente de juicio de 07-verificador" / "…no está abierta (espera_firma)" / "…no es una tarea de IA:<carpeta>:* en <plan>" (B13.2) |
| stop.py | ENTREGA válida que pega la línea de puntos de pytest | exit 0; la evidencia `entrega:*` dice `→ 15 passed in 1.04s · exit 0` y guarda la salida completa; sin línea de resumen, "(la salida no trae línea de resumen)" |
| stop.py | cualquiera de las anteriores con `"stop_hook_active":true` | exit 0, "CIERRE SIN ENTREGA VÁLIDA", `bloqueo:entrega_incompleta` |
| stop.py | mensaje terminado en `BLOQUEADO: <motivo>` (o `PREGUNTA: …`) | exit 0, "registrado para Carlos", `pregunta_humano` |
| brief.py / prompt_submit.py | SessionStart o UserPromptSubmit con dos planes abiertos y tareas del agente en ambos | exit 0; el brief lista tareas de ambos planes y dice "Para entregar una tarea de otro plan, añade la línea `Plan: <id>`" (B14) |
| stop.py | ENTREGA con `Plan: PLAN-CS-T03` y `Tarea: 60` (tarea del segundo plan) | exit 0, "ENTREGA registrada en SYPNOSE"; `tarea_entregada` de la tarea 60 del plan T03 (B14) |
| stop.py | ENTREGA con `Plan: PLAN-INEXISTENTE` | exit 2, "PLAN-INEXISTENTE no es un plan trabajable" (B14) |
| commit_msg.py | fichero con `Plan: PLAN-CS-T03` (en planes_trabajables) | exit 0 (B14) |
| commit_msg.py | fichero con `Plan: PLAN-FALSO` (no en planes_trabajables) | exit 1, "PLAN-FALSO" (B14) |
| brief.py / prompt_submit.py | SessionStart o UserPromptSubmit cuando un plan nuevo (abierto después del SessionStart) tiene tareas del agente | exit 0; el aviso dice "planes nuevos descubiertos: <id>" y las tareas del plan nuevo aparecen en la lista (B19) |
| stop.py | ENTREGA con `Plan: <id>` de un plan abierto después del SessionStart (no en la caché de planes_trabajables) y `Tarea: <id>` | exit 0, "ENTREGA registrada en SYPNOSE"; `tarea_de_entrega` verifica en vivo y acepta (B19) |
| stop.py | ENTREGA con `Plan: <id>` de un plan cerrado o sin dueño H: (no en caché, verificación en vivo falla) | exit 2, "el plan <id> no es un plan abierto con dueño H:" (B19) |
| pre_tool_use.py | Bash `ssh sypnose@host "cd ~/coforge-santander/plantilla && git add . && git commit -m test"` | exit 2, "git de escritura por SSH bloqueado" (B15) |
| pre_tool_use.py | Bash `ssh -i key -p 2024 sypnose@host "git -C ~/sypnose-f1 push origin main"` | exit 2, "git de escritura por SSH bloqueado" (B15) |
| pre_tool_use.py | Bash `ssh sypnose@host "git checkout main"` | exit 2, "git de escritura por SSH bloqueado" (B15) |
| pre_tool_use.py | Bash `ssh sypnose@host "git -C ~/coforge-santander/plantilla log --oneline -5"` | exit 0 (lectura, B15) |
| pre_tool_use.py | Bash `ssh sypnose@host "sqlite3 ~/sypnose-f1/registry.db 'SELECT …'"` | exit 0 (B15) |
| pre_tool_use.py | Bash `ssh sypnose@host "python3 plantilla/cargar_requisito.py PLAN-CS-T01"` | exit 0 (B15) |
| pre_tool_use.py | Bash `ssh sypnose@host "git status"` | exit 0 (lectura, B15) |
| commit_msg.py | argumento: fichero con `prueba sin pie` | exit 1, "COMMIT RECHAZADO", `bloqueo:commit-msg` |
| commit_msg.py | fichero con el pie en un párrafo y `Co-Authored-By` en otro, ambos al final | exit 0; el fichero queda con un solo bloque final y `git interpret-trailers --parse` lista Chat, Model, Plan, Tarea y Co-Authored-By |
| commit_msg.py | fichero con el pie en medio del cuerpo y otro párrafo al final | exit 1, "tiene que ir en el último párrafo" |
| commit_msg.py | fichero con `Chat:` o `Model:` repetidos, aunque el último valor sea el correcto | exit 1, "'Chat:' aparece 2 veces; tiene que aparecer una sola vez" |
| post_tool_use.py | Bash `git -C <wt-extra> merge main` deja ficheros fuera de permitidos del wt-extra | exit 0; la auditoría detecta `git merge` en el comando y añade los ficheros al baseline `sucios_inicio_extra` (B20) |
| post_tool_use.py | Bash sin merge deja ficheros fuera de permitidos del wt-extra (tras un merge previo) | exit 2, "auditoría git" con el fichero nuevo; los ficheros del merge anterior siguen en el baseline (B20) |

Todo junto:
```
cd "C:\MICD\Coforge Santander\08-caparazon\wt-plantilla\caparazon\pruebas"
python probar_bloqueos.py --carpeta "C:\MICD\Coforge Santander\02-backend-api" --modo local
python probar_bloqueos.py --carpeta "C:\MICD\Coforge Santander\02-backend-api" --modo real --actor IA:07-verificador:claude-opus-5
```
Las 4 pruebas de X3:
1. escritura fuera → B3.1–B3.3 y B7.2;
2. commit sin pie → B5.1, B5.5, B5.6 y 07-T2–07-T8 (B5.3 en real);
3. cierre sin ENTREGA válida:
   - bloquean al primer intento: B6.1, B6.2b, B6.2d, B6.2g, B6.2i, B6.2k, B6.3, B6.9, B6.9b, B6.9e, B6.9h, B6.9j, B6.9l, B6.9n,
     07-E1–07-E3 y 07-E6–07-E9;
   - en continuación cierran como entrega incompleta: B6.12–B6.14;
4. registro caído → B7.1–B7.9;
5. barrera en vivo: sin las tres condiciones no sale nada del PC → B4.4–B4.9 y B9.1;
6. sin tarea (B10): el prompt humano pasa con el aviso, Write y Bash que cambian algo se bloquean, y Read y Bash de lectura pasan →
   B1.4, B2.3, B2.4 y B3.15–B3.19;
7. comando entero (B11): un commit con heredoc pasa, una redirección real después de un heredoc se bloquea, y un comando ilegible se
   bloquea con un mensaje que dice qué hacer → B3.20–B3.24;
8. requisito vigente (B12): la ENTREGA se valida contra el requisito del registro, el prompt lo trae actualizado y, con el registro
   caído, la ENTREGA se bloquea → B6.23, B6.23b, B2.5 y B6.24;
9. varias tareas (B13): el brief y cada prompt las listan, `Tarea: <id>` entrega esa tarea salvo que ya esté entregada sin juicio, y el
   prompt siguiente a la entrega de la tarea del estado pasa a la siguiente trabajable → B6.25–B6.27;
10. varios planes (B14): el brief lista tareas de todos los planes, `Plan: <id>` + `Tarea: <id>` en la ENTREGA selecciona, los
    permitidos del cerco son la unión, `commit_msg.py` valida `Plan:` contra `planes_trabajables` → B6.28–B6.29d;
11. SSH-git bloqueado (B15): `ssh host "git commit …"` / `push` / `checkout` → bloqueado; `ssh host "git log …"` / `"sqlite3 …"` /
    `"python3 plantilla/…"` / `"git status"` → pasa → B6.30–B6.31d;
12. auditoría merge (B20): un `git merge`/`pull`/`rebase` en un Bash trae ficheros de otros commits que no son escrituras del agente;
    la auditoría añade esos ficheros al baseline y no los bloquea; una escritura propia posterior fuera de permitidos sigue bloqueada →
    B20.0–B20.2.
13. descriptor de fichero en redirecciones (B21): `2>&1`, `2>`, `1>>` etc. — el dígito antes del operador de redirección es un descriptor
    de fichero, no una ruta; `touch app/main.py 2>&1` pasa, `touch ../_centinela_fuera.txt 2>&1` bloquea por el fichero, no por el "2" →
    B21.0–B21.1.
14. forma_pura multi-worktree (B22): `forma_pura()` aceptaba `cd` solo al worktree principal; ahora acepta también worktrees_extra de la
    config y plan.worktree del registro; una ruta ajena sigue rechazada → B22.0–B22.1.

## 4. Evidencia

### 4.1 B9 en modo local — 152/152 CUMPLE en dc94097 (exit 0)
B15, la cerca bloquea git de escritura por SSH (dc94097, 152/152). Salida real del 15-sep:
```
── B6.30 PreToolUse: ssh con 'git commit' remoto → bloqueada por el cerco ──   exit=2 · 220 ms
stderr: CERCO: Bash bloqueada por el cerco: git de escritura por SSH bloqueado: cd ~/coforge-santander/plantilla && git add . && git commit -m test
→ CUMPLE
── B6.30b PreToolUse: ssh con 'git -C ~/sypnose-f1 push' → bloqueada ──   exit=2 · 265 ms
stderr: CERCO: Bash bloqueada por el cerco: git de escritura por SSH bloqueado: git -C ~/sypnose-f1 push origin main
→ CUMPLE
── B6.30c PreToolUse: ssh con 'git checkout' remoto → bloqueada ──   exit=2 · 220 ms
stderr: CERCO: Bash bloqueada por el cerco: git de escritura por SSH bloqueado: git checkout main
→ CUMPLE
── B6.31 PreToolUse (control): ssh con 'git log' remoto → pasa (lectura) ──   exit=0 · 225 ms   → CUMPLE
── B6.31b PreToolUse (control): ssh con sqlite3 → pasa ──   exit=0 · 220 ms   → CUMPLE
── B6.31c PreToolUse (control): ssh con python3 plantilla/ → pasa ──   exit=0 · 220 ms   → CUMPLE
── B6.31d PreToolUse (control): ssh con git status remoto → pasa (lectura) ──   exit=0 · 225 ms   → CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 152 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
B14, un chat con varios planes abiertos (591128d, 145/145). Salida real del 15-sep:
```
── B6.28 SessionStart con dos planes: el brief lista tareas de ambos planes ──   exit=0 · 3408 ms
stdout: … "PLAN-CS-T01" … "PLAN-CS-T03" … "tarea 60" … "Plan: <id>" …   → CUMPLE
── B6.28b UserPromptSubmit con dos planes: el aviso del prompt lista tareas de ambos ──   exit=0 · 298 ms
stdout: … "PLAN-CS-T03" … "tarea 60" …   → CUMPLE
── B6.29 Stop: ENTREGA con 'Plan: PLAN-CS-T03' y 'Tarea: 60' entrega tarea de otro plan ──   exit=0 · 326 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE …"}   comprobado: tarea 60 en tarea_entregada   → CUMPLE
── B6.29b Stop: ENTREGA con 'Plan: PLAN-INEXISTENTE' → rechazada (plan no trabajable) ──   exit=2 · 302 ms
stderr: … PLAN-INEXISTENTE … no es un plan …   → CUMPLE
── B6.29c commit-msg acepta Plan: PLAN-CS-T03 (planes_trabajables incluye T03) ──   exit=0 · 299 ms   → CUMPLE
── B6.29d commit-msg rechaza Plan: PLAN-FALSO (no está en planes_trabajables) ──   exit=1 · 243 ms
stderr: … PLAN-FALSO …   → CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 145 · grep -c "^  NO CUMPLE" → 0 · exit=0
```

B13, varias tareas trabajables en el mismo plan. Salida real del 15-sep a las 17:12Z. El arnés imprime solo los primeros 700 caracteres
de stdout, así que las líneas largas van cortadas con «…». B6.25 y B6.27 comprueban sobre la salida completa la lista («tarea 33 · R0 ·
trabajando · entregada: no», «tarea 51 · R1 · pendiente · entregada: no», «tarea 52 · R1 · trabajando · entregada: no») y el aviso «la
tarea 33 está entregada y pendiente de juicio».
```
── B6.25 SessionStart con dos tareas trabajables: el brief las lista con requisito, progreso y si están entregadas ──   exit=0 · 3408 ms
stdout: {"systemMessage": "Caparazón: PLAN-CS-T01 · tarea 33 · cerco app/main.py, app/api/, app/core/config.py …", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "═══ BRIEF CAPARAZÓN · 02-backend-api · 2026-09-15T17:12:30.488Z ═══ …
→ CUMPLE
── B6.25b UserPromptSubmit con dos tareas trabajables: el aviso del prompt también las lista ──   exit=0 · 298 ms
stdout: … "additionalContext": "Requisito vigente de la tarea 33 (PLAN-CS-T01/R0) … \nComprobación: pytest tests/test_main.py\n…\nTus tareas trabajables en PLAN-CS-T01: tarea 33 · R0 · trabajando · entregada: no | tarea 51 · R1 · pendiente · entregada: no. Para entregar una que no es la de este brief, añade la línea «Tarea: <id>» al bloqu…
→ CUMPLE
── B6.26 Stop: ENTREGA con 'Tarea: 51', otra tarea del agente que no es la del estado (33) → entrega la 51 ──   exit=0 · 326 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1912"}
comprobado: última tarea_entregada: tarea 51 R1: `pytest tests/test_engine_mode.py` → 15 passed  · progreso de la 51=trabajando
── B6.26b Stop: otra ENTREGA de la 51, que ya está entregada y pendiente de juicio → rechazada ──   exit=2 · 302 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la tarea 51 ya está entregada y pendiente de juicio de 07-verificador. bloqueo:entrega registrado en SYPNOSE.
── B6.26c Stop: ENTREGA con 'Tarea: 9', que está en espera_firma → rechazada ──   exit=2 · 318 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la tarea 9 no está abierta (espera_firma). bloqueo:entrega registrado en SYPNOSE.
── B6.27a Stop: ENTREGA sin línea Tarea entrega la tarea del estado (33), como hasta ahora ──   exit=0 · 349 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1912"}
comprobado: última tarea_entregada: tarea 33 R0: `pytest tests/test_main.py` → 15 passed in 1.04
── B6.27 UserPromptSubmit tras entregar la tarea del estado: pasa a la siguiente trabajable (52) y lo dice ──   exit=0 · 3307 ms
stdout: … "additionalContext": "═══ BRIEF CAPARAZÓN · 02-backend-api · 2026-09-15T17:12:36.942Z ═══ …\nTarea 52 · requisito R1 · progreso trabajando\nTus tareas trabajables en PLAN-CS-T01: tarea 52 · R1 · trabajan…
→ CUMPLE
══ Resumen ══  CUMPLE ×139 · NO CUMPLE ×0 · NO APLICA ×0 · exit 0
```
B12, el requisito vigente se lee del registro. Salida real del 15-sep:
```
── B6.23 Stop: la comprobación cambia en el registro a mitad de sesión y la ENTREGA con la vigente pasa (caso real de 02, 22685→22690) ──
exit=0 · 356 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1845"}
comprobado: tarea_entregada: tarea 33 R0: `pytest tests/test_main.py tests/test_engine_mode.py` → 15 passed in 1.04s · lección le…
→ CUMPLE
── B6.23b Stop: la ENTREGA con la comprobación antigua se rechaza y dice qué cambió en el registro ──
exit=2 · 321 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la comprobación de R0 cambió en el registro: ahora es `pytest tests/test_main.py` (antes `pytest tests/test_engine_mode.py`); el bloque ENTREGA no cita la comprobación literal `pytest tests/test_main.py`; la comprobación `pytest tests/test_main.py` no se ha ejecutado tal cual en esta sesión con Bash/Power…
→ CUMPLE
── B2.5 UserPromptSubmit tras cambiar la comprobación en el registro: inyecta la vigente y avisa del cambio ──
exit=0 · 301 ms
stdout: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "Cambios del caparazón: la comprobación de R0 cambió en el registro: ahora es `pytest tests/test_engine_mode.py` (antes `pytest tests/test_main.py`)\nRequisito vigente de la tarea 33 (PLAN-CS-T01/R0), texto literal del registro SYPNOSE: Antes de escribir código…
→ CUMPLE
── B6.24 Stop con ENTREGA y el registro caído: bloqueada hasta confirmar la comprobación vigente, con bloqueo:registro_caido en la cola ──
exit=2 · 4406 ms
stdout: {"systemMessage": "REGISTRO SYPNOSE NO RESPONDE: 7 operaciones siguen en la cola local (…\\cola\\prueba-b9-local-184259-b12-caido.jsonl); se reenvían cada 60 s y al terminar el turno, y el siguiente arranque las envía y registra bloqueo:registro_caido. Motivo: http://127.0.…
stderr: CIERRE IMPEDIDO: no se pudo confirmar la comprobación vigente: registro caído; reintenta la ENTREGA cuando vuelva.
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 132 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
La comprobación de B6.24 también verificó que `bloqueo:registro_caido` está en la cola de esa sesión.

B11, el cerco lee el comando entero (356d11b, 128/128). Salida real del 15-sep:
```
── B3.20 PreToolUse: git commit con heredoc en -m que menciona '->', pytest y una ruta con espacio (el commit real de 02, evento 22672) → pasa ──
exit=0 · 225 ms
→ CUMPLE
── B3.21 PreToolUse: cat <<'EOF' > ../_centinela_fuera.txt con cuerpo → sigue bloqueado por la redirección real, no por el cuerpo ──
exit=2 · 236 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\_centinela_fuera.txt está fuera del worktree c:\micd\coforge santander\02-backend-api\wt y de los worktrees extra ['c:\\users\\carlo\\appdata\\local\\temp\\caparazon-b9-vy5r1mtc\\wt-plantilla']
→ CUMPLE
── B3.22 PreToolUse: comando con una comilla sin cerrar → bloqueado con un mensaje que dice qué hacer ──
exit=2 · 228 ms
stderr: CERCO: Bash bloqueada por el cerco: el cerco no puede leer este comando (No closing quotation): revisa las comillas o pasa el mensaje por fichero: git commit -F <fichero>
→ CUMPLE
── B3.23 PreToolUse: la orden de después del terminador del heredoc sí se analiza → bloqueada ──
exit=2 · 221 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\_centinela_fuera.txt está fuera del worktree …
→ CUMPLE
── B3.24 PreToolUse: un <<EOF dentro de comillas no es heredoc y no esconde la línea siguiente → bloqueada ──
exit=2 · 265 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\_centinela_fuera.txt está fuera del worktree …
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 128 · grep -c "^  NO CUMPLE" → 0 · exit=0
```

B10, sesión sin tarea (59c498e, 123/123; con la tarea 33 en espera_firma durante estos casos). Salida real del 15-sep:
```
── B1.4 SessionStart sin tarea abierta: el brief da el aviso y no dice que bloquea los prompts ──
exit=0 · 379 ms
stdout: {"systemMessage": "Caparazón sin tarea: Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar comandos que cambien nada hasta que el arquitecto le abra una tarea en PLAN-CS-T01.\n3 operaciones pendientes enviadas al registro", "hookSpecificOutput": {"hookEv…
→ CUMPLE
── B2.3 UserPromptSubmit sin tarea abierta (prompt de un humano): pasa y lleva el aviso en castellano llano ──
exit=0 · 300 ms
stdout: {"systemMessage": "Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar comandos que cambien nada hasta que el arquitecto le abra una tarea en PLAN-CS-T01.", "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "Este chat no tien…
→ CUMPLE
── B3.15 PreToolUse sin tarea: Write bloqueada con el mismo aviso ──
exit=2 · 237 ms
stderr: Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar comandos que cambien nada hasta que el arquitecto le abra una tarea en PLAN-CS-T01.
→ CUMPLE
── B3.16 PreToolUse sin tarea: Read pasa ──
exit=0 · 222 ms
→ CUMPLE
── B3.17 PreToolUse sin tarea: Bash de solo lectura (cd, git status, git log, ls, cat | grep) pasa ──
exit=0 · 240 ms
→ CUMPLE
── B3.18 PreToolUse sin tarea: Bash que escribe en un fichero permitido → bloqueada con el aviso ──
exit=2 · 223 ms
stderr: Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar comandos que cambien nada hasta que el arquitecto le abra una tarea en PLAN-CS-T01.
→ CUMPLE
── B3.19 PreToolUse sin tarea: Bash que cambia algo sin ruta visible (git commit, pip install) → bloqueada ──
exit=2 · 246 ms
stderr: Este chat no tiene tarea asignada en SYPNOSE. Puede conversar y leer, pero no puede escribir ficheros ni ejecutar comandos que cambien nada hasta que el arquitecto le abra una tarea en PLAN-CS-T01.
→ CUMPLE
── B2.4 UserPromptSubmit con el registro caído: el prompt sigue bloqueado (el único caso) ──
exit=2 · 8506 ms
stderr: CAPARAZÓN ABORTADO: prompt bloqueado.
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 123 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
Clasificador `cerco.solo_lectura()` probado aparte con 16 comandos y 0 fallos:
- pasan `git status`/`log`/`branch --show-current`/`remote -v`/`config --get`/`stash list`, `git -C … worktree list`, `find | head`,
  `Get-ChildItem | Select-String` y `date +%Y-%m-%d`;
- se bloquean `echo >`, `git commit`, `pip install`, `git branch nueva`, `git stash`, `find -delete`, `sort -o`, `python -c`, `$(…)`,
  `bash -c` y `rm -rf`.

Correcciones del cerco (faab629, 115/115; sesión real de 02: rutas de shell y `worktrees_extra`), salida real del 15-sep a las 15:10Z:
```
── B3.5 PreToolUse: ruta POSIX de Git Bash (/c/…) a la centinela → bloqueada con su ruta real ──
exit=2 · 241 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\_centinela_fuera.txt está fuera del worktree c:\micd\coforge santander\02-backend-api\wt y de los worktrees extra […]
→ CUMPLE
── B3.6 PreToolUse: ruta con ~ → bloqueada con la ruta del home, no como si estuviera dentro del worktree ──
exit=2 · 257 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\users\carlo\_centinela_fuera.txt está fuera del worktree c:\micd\coforge santander\02-backend-api\wt y de los worktrees extra […]
→ CUMPLE
── B3.8 PreToolUse (control): ruta POSIX dentro del worktree y permitida → pasa ──
exit=0 · 237 ms
→ CUMPLE
── B3.10 PreToolUse: Write en el worktree extra fuera de specs/T01/** → bloqueada ──
exit=2 · 240 ms
stderr: CERCO: Write bloqueada por el cerco: readme.md está fuera de archivos_permitidos ['specs/T01/**'] del worktree extra c:\users\carlo\appdata\local\temp\caparazon-b9-suhe86kb\wt-plantilla
→ CUMPLE
── B3.12 PreToolUse: git -C en el repo plantilla compartido, que no es worktree extra (caso real de 02) → bloqueada ──
exit=2 · 260 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\plantilla está fuera del worktree c:\micd\coforge santander\02-backend-api\wt y de los worktrees extra […]
→ CUMPLE
── B3.13 PreToolUse (control): git worktree list y git log en el worktree no escriben nada → pasa ──
exit=0 · 240 ms
→ CUMPLE
── B3.14 PreToolUse: git worktree add con -b pone el worktree en la ruta, no en la rama → la ruta de fuera se bloquea ──
exit=2 · 250 ms
stderr: CERCO: Bash bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\otro-wt está fuera del worktree c:\micd\coforge santander\02-backend-api\wt y de los worktrees extra […]
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 115 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
B3.7, B3.9, B3.11, B4.10 y B4.11 también salen CUMPLE en esta ejecución (0 NO CUMPLE en 115).

`bloqueo:kb_caida` al volver la KB (cc2ad8f, decisión del lead), salida real del 15-sep a las 14:48Z:
```
── B6.19 Stop: ENTREGA válida con la KB caída → tarea_entregada, evidencia y aviso llegan al registro; la lección se queda en la cola ──
exit=0 · 2394 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1648\nKB SIN RESPUESTA: el registro SYPNOSE ya recibió los eventos y las evidencias; 1 lección(es) siguen en la cola local (…\\cola\\prueba-b9-local-164627-kb-caida.jsonl) y se reintentan cada 60 s y al terminar el turno. Motivo: KB http://127.0.0.1…
comprobado: tarea_entregada 9→10 · aviso_verificador 9→10 · leccion_guardada 9→9 · bloqueo:kb_caida 0→0 · bloqueo:registro_caido 2→2 · operaciones en cola=2
→ CUMPLE
── B6.20 flush con la KB de vuelta: la lección se guarda, leccion_guardada llega y queda bloqueo:kb_caida con sus operaciones retenidas ──
exit=0 · 307 ms
comprobado: leccion_guardada 9→10 · bloqueo:kb_caida 0→1 (evidencias 1) · detalle: ['KB sin respuesta desde 2026-09-15T14:48:38.165Z (último fallo 2026-09-15T14:48:38.165Z, 1 envío'] · operaciones en cola=0
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 103 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
La comprobación de B6.20 también verificó que el detalle dice "2 operaciones retenidas" (el extracto impreso se corta a 95 caracteres).

Casos del examen real de 07 en e215054 (KB caída y evidencia con resumen), salida real del 15-sep a las 14:41Z:
```
── B6.19 Stop: ENTREGA válida con la KB caída → tarea_entregada, evidencia y aviso llegan al registro; la lección se queda en la cola ──
exit=0 · 2363 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1641\nKB SIN RESPUESTA: el registro SYPNOSE ya recibió los eventos y las evidencias; 1 lección(es) siguen en la cola local (…
comprobado: tarea_entregada 9→10 · aviso_verificador 9→10 · leccion_guardada 9→9 · operaciones en cola=2
→ CUMPLE
── B6.20 flush con la KB de vuelta: la lección se guarda y leccion_guardada llega al registro ──
exit=0 · 308 ms
comprobado: leccion_guardada 9→10 · operaciones en cola=0
→ CUMPLE
── B6.21 Stop: ENTREGA que pega la línea de puntos → la evidencia entrega:* lleva '15 passed in 1.04s' y la salida completa ──
exit=0 · 334 ms
comprobado: evidencia: 'evento 174 (2026-09-15T14:42:03.705Z) IA:08-caparazon:claude-opus-5: `pytest tests/test_main.py tests/test_engine_mode.py -q` → 15 passed in 1.04s · exit 0\nSalida complet'
→ CUMPLE
── B6.22 Stop: ENTREGA cuya salida no trae resumen (pytest -qq) → la evidencia lo dice y guarda la salida completa ──
exit=0 · 331 ms
comprobado: evidencia: 'evento 181 (2026-09-15T14:42:08.952Z) IA:08-caparazon:claude-opus-5: `pytest tests/test_main.py tests/test_engine_mode.py -q` → ...............   …'
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 103 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
En B6.22 el extracto impreso se corta a 200 caracteres; la comprobación sí verificó que la evidencia dice "(la salida no trae línea de
resumen)" y trae la línea de puntos.

Casos tras la sesión real de 02 (78665a5, 99/99), salida real del 15-sep a las 14:24Z. Brief sin SessionStart:
```
── B2.1 UserPromptSubmit sin SessionStart previo: crea el estado y entrega el brief completo ──
exit=0 · 3749 ms
stdout: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "═══ BRIEF CAPARAZÓN · 02-backend-api · 2026-09-15T14:24:48.081Z ═══\nActor: IA:08-caparazon:claude-opus-5 — modelo leído de transcript …
comprobado: sesion_iniciada: ['sin SessionStart: estado creado por UserPromptSubmit · modelo claude-s']
→ CUMPLE
── B2.2 UserPromptSubmit siguiente de esa sesión: solo la EARS, el brief no se repite ──
exit=0 · 277 ms
stdout: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "Requisito vigente de la tarea 33 (PLAN-CS-T01/R0), texto literal del registro SYPNOSE: Antes de escribir código para esta línea, el rol 02-backend-api DEBE registr…
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 99 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
`cwd` en las llamadas del arnés a flush.py (ejecución de las 14:17Z, antes de añadir B2.1–B2.2: 97/97):
```
── B4.3 flush al vencer el plazo: la cola llega al registro ──
entrada: {"session_id": "prueba-b9-local-161659", "cwd": "C:\\MICD\\Coforge Santander\\02-backend-api\\wt"}
exit=0 · 284 ms
comprobado: registro herramienta:Write=1 bloqueo:cerco=3 · cola=0
── B7.4 registro caído: el envío periódico falla y lo anota ──
entrada: {"session_id": "prueba-b9-local-161659", "cwd": "C:\\MICD\\Coforge Santander\\02-backend-api\\wt"}
exit=0 · 2319 ms
comprobado: fallo anotado=True · cola=3
```
Casos de la barrera en vivo y de `~` en la BD (b33c05f, 97/97), salida real del 15-sep a las 13:00Z:
```
[modo local] registro sqlite C:\Users\carlo\AppData\Local\Temp\caparazon-b9-myaho5e6\registro.db · API/KB simuladas en http://127.0.0.1:61305 · SYPNOSE_MODO=prueba · ssh.bin sin ejecutable (nada sale a la red)
── B1.3 SessionStart con ssh.db '~/sypnose-f1/registry.db' en el config: el brief enseña la ruta absoluta ──
exit=0 · 3057 ms
→ CUMPLE
── B6.15 Stop (~ en la BD): (s6b de 07) config con ~ y comando con ~ se acepta ──
exit=0 · 292 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1501"}
comprobado: tarea_entregada 6 → 7
── B6.16 Stop (~ en la BD): (s6 de 07) config con ~ y comando con la ruta absoluta, -i y -p se acepta ──
exit=0 · 296 ms
comprobado: tarea_entregada 7 → 8
── B6.17 Stop (~ en la BD): config con ~ y otra BD del mismo home se rechaza ──
exit=2 · 282 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («ssh sypnose@62.171.147.46 "sqlite3 ~/sypnose-f1/otra.db \"SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'\""») no cuenta: la base de datos ~/sypnose-f1/otra.db no es la del registro configurado. …
comprobado: tarea_entregada 8 → 8
── B6.18 Stop (~ en la BD): config absoluta y comando con ~ se acepta ──
exit=0 · 292 ms
comprobado: tarea_entregada 8 → 9
[barrera] instalar_caparazon.py C:\Users\carlo\AppData\Local\Temp\caparazon-b9-myaho5e6\carpeta-barrera --modo real → exit 0 · INSTALADO=True · ssh.bin=C:\Users\carlo\AppData\Local\Temp\caparazon-b9-myaho5e6\sin-ssh\ssh.exe (no existe)
── B4.4 barrera: SYPNOSE_MODO=real y escritura ssh desde una copia sin instalar (como el arnés de 07) → modo prueba, cola intacta ──
exit=0 · 239 ms
stdout: {"estado": "prueba", "sesion": "prueba-b9-local-150013-barrera-90", "motivo": "estos módulos (C:\\Users\\carlo\\AppData\\Local\\Temp\\caparazon-b9-myaho5e6\\caparazon) no son la instalación de C:\\MICD\\Coforge Santander\\02-backend-api", "destinos": ["el registro por ssh (sypnose@62.171.147.46)"], "pendientes": 1, …
comprobado: operaciones en la cola=1 · fallo anotado=ninguno
── B4.5 barrera: instalación completa y sesión en su worktree, pero SYPNOSE_MODO=prueba → modo prueba ──
exit=0 · 292 ms
stdout: {"estado": "prueba", "sesion": "prueba-b9-local-150013-barrera-91", "motivo": "SYPNOSE_MODO=prueba, no real", "destinos": ["el registro por ssh (sypnose@62.171.147.46)"], "pendientes": 1, …
comprobado: operaciones en la cola=1 · fallo anotado=ninguno
── B4.6 barrera: SYPNOSE_MODO=real en una instalación sin el marcador INSTALADO → cola local, 0 envíos ──
exit=0 · 239 ms
stdout: {"estado": "prueba", "sesion": "prueba-b9-local-150013-barrera-92", "motivo": "no existe el marcador C:\\Users\\carlo\\AppData\\Local\\Temp\\caparazon-b9-myaho5e6\\carpeta-barrera\\.claude\\caparazon\\INSTALADO, que solo escribe instalar_caparazon.py", "destinos": ["el registro por ssh (sypnose@62.171.147.46)"], …
comprobado: operaciones en la cola=1 · fallo anotado=ninguno
── B4.7 barrera: SYPNOSE_MODO=real y marcador, pero la sesión trabaja fuera de la carpeta y de su worktree → modo prueba ──
exit=0 · 244 ms
stdout: {"estado": "prueba", "sesion": "prueba-b9-local-150013-barrera-93", "motivo": "la sesión trabaja en C:\\Users\\carlo\\AppData\\Local\\Temp\\caparazon-b9-myaho5e6, fuera de C:\\Users\\carlo\\AppData\\Local\\Temp\\caparazon-b9-myaho5e6\\carpeta-barrera y de su worktree", …
comprobado: operaciones en la cola=1 · fallo anotado=ninguno
── B4.8 barrera: KB real por defecto (sin SYPNOSE_KB_URL) con una lección en cola, desde una copia sin instalar → modo prueba ──
exit=0 · 232 ms
stdout: {"estado": "prueba", "sesion": "prueba-b9-local-150013-barrera-94", "motivo": "estos módulos (…\\caparazon-b9-myaho5e6\\caparazon) no son la instalación de C:\\MICD\\Coforge Santander\\02-backend-api", "destinos": ["la KB http://127.0.0.1:18791"], "pendientes": 1, …
comprobado: operaciones en la cola=1 · fallo anotado=ninguno
── B4.9 barrera (control): las tres condiciones → se abre y llega al envío por ssh, que falla en el PC (ssh.bin no existe) ──
exit=0 · 251 ms
stdout: {"estado": "fallo", "sesion": "prueba-b9-local-150013-barrera-95", "motivo": "SSH al registro falló: [WinError 2] El sistema no puede encontrar el archivo especificado", "pendientes": 1, …
comprobado: operaciones en la cola=1 · fallo anotado=SSH al registro falló: [WinError 2] El sistema no puede encontrar el archivo especificado
── B9.1 modo local: ninguna cola del arnés intentó enviar por ssh ──
colas con fallo de ssh: ninguna
→ CUMPLE
══ Resumen ══   grep -c "^  CUMPLE" → 97 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
Casos de 9c33f03 (hallazgo (s) de 07 y `x3_entrega3.py` portado), salida real:
```
── B6.9h Stop: ENTREGA con el 5 de esa ejecución ──
exit=2 · 295 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («ssh sypnose@62.171.147.46 "sqlite3 /tmp/falsa.db \"SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'\""») no cuenta: la base de datos /tmp/falsa.db no es la del registro configurado. …
── B6.9j Stop: ENTREGA con el 5 de esa ejecución ──
exit=2 · 318 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («ssh -o HostName=127.0.0.1 sypnose@62.171.147.46 "sqlite3 ~/sypnose-f1/registry.db \"SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'\""») no cuenta: ssh lleva la opción -o HostName=127.0.0.1, que no está permitida. …
── B6.9l Stop: ENTREGA con el 5 de esa ejecución ──
exit=2 · 316 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («sqlite3 C:/tmp/falsa.db "SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'"») no cuenta: la base de datos C:/tmp/falsa.db no es la del registro configurado. …
── B6.9n Stop: ENTREGA con el 5 de esa ejecución ──
exit=2 · 275 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («ssh sypnose@62.171.147.46 "sqlite3 -cmd \".open /tmp/falsa.db\" ~/sypnose-f1/registry.db \"SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'») no cuenta: sqlite3 lleva opciones o comandos que no están permitidos. …
── B6.9o PostToolUse: la consulta tal cual contra el registro devuelve 1 ──
exit=0 · 319 ms
── B6.10 Stop: ENTREGA válida de una comprobación 'consulta → esperado' ──
exit=0 · 369 ms
stdout: {"systemMessage": "ENTREGA registrada en SYPNOSE · lección leccion-linea-T01-150926-1427"}
comprobado: registro tarea_entregada=2
── 07-E6 Stop (x3_entrega3.py): (s) consulta contra OTRA base de datos (sqlite3 /tmp/falsa.db) se rechaza ──
exit=2 · 301 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («sqlite3 /tmp/falsa.db "SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'"») no cuenta: la base de datos /tmp/falsa.db no es la del registro configurado. …
comprobado: tarea_entregada 4 → 4
── 07-E7 Stop (x3_entrega3.py): (q) prefijo de entorno PYTEST_ADDOPTS='-k nada' se rechaza ──
exit=2 · 319 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («PYTEST_ADDOPTS="-k nada" pytest tests/test_main.py tests/test_engine_mode.py -q») no cuenta: no es exactamente la comprobación. …
comprobado: tarea_entregada 4 → 4
── 07-E8 Stop (x3_entrega3.py): (p) bash -c con tubería dentro se rechaza ──
exit=2 · 328 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («bash -c "pytest tests/test_main.py tests/test_engine_mode.py -q | grep -o passed"») no cuenta: no es exactamente la comprobación. …
comprobado: tarea_entregada 4 → 4
── 07-E9 Stop (x3_entrega3.py): (o) redirección 2>&1 al final se rechaza ──
exit=2 · 306 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («pytest tests/test_main.py tests/test_engine_mode.py -q 2>&1») no cuenta: lleva tuberías, ';', '&&'/'||' o redirecciones. …
comprobado: tarea_entregada 4 → 4
── 07-E10 Stop (x3_entrega3.py): (n) control: espacios dobles dentro del comando se aceptan ──
exit=0 · 320 ms
comprobado: tarea_entregada 4 → 5
── 07-E11 Stop (x3_entrega3.py): (m) control: cd <worktree> && comprobación en verde se acepta ──
exit=0 · 295 ms
comprobado: tarea_entregada 5 → 6
══ Resumen ══   (reejecución 2026-09-15T12:26Z sobre 9c33f03)
  CUMPLE    07-E11 Stop (x3_entrega3.py): (m) control: cd <worktree> && comprobación en verde se acepta
grep -c "^  CUMPLE" → 85 · grep -c "^  NO CUMPLE" → 0 · exit=0
```
Casos de 0def414 (evasiones y hallazgos de 07, y sus scripts portados), salida real:
```
── B6.2g Stop: ENTREGA con la salida filtrada (e) ──   exit=2 · 295 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación («cd wt && pytest tests/test_main.py tests/test_engine_mode.py -q | grep -o "13 passed"») no cuenta: lleva tuberías, ';', '&&'/'||' o redirecciones. …
── B6.2k Stop: ENTREGA con la salida verde de otra copia del repo ──   exit=2 · 287 ms
stderr: CIERRE IMPEDIDO: … («cd "C:/otra/copia" && pytest tests/test_main.py tests/test_engine_mode.py -q») no cuenta: se ejecutó fuera del worktree (c:\otra\copia). …
── B6.9e Stop: ENTREGA con el 1 del echo (f) ──   exit=2 · 306 ms
stderr: CIERRE IMPEDIDO: … («sqlite3 ~/sypnose-f1/registry.db "SELECT COUNT(*) …"; echo 1») no cuenta: lleva tuberías, ';', '&&'/'||' o redirecciones. …
── B5.6 commit-msg: hallazgo (1) de 07, Chat y Model repetidos con el último valor correcto ──   exit=1 · 270 ms
── B5.7 commit-msg: hallazgo (2) de 07, un párrafo de cuerpo 'Nota: …' no se une al pie ──   exit=0 · 310 ms   comprobado: trailers para git: ['Chat', 'Model', 'Plan', 'Tarea', 'Co-Authored-By']
  CUMPLE    07-T1 … 07-T8 commit-msg (x3_trailers.py): control; Chat duplicado delante y detrás; Model duplicado; pie válido en cuerpo + inválido al final; Nota antes del pie con Co-Authored-By aparte; '# Chat:' como único pie; Tarea 999
── 07-E1 Stop (x3_entrega2.py): (e) pytest en rojo filtrado con | grep -o '13 passed' se rechaza ──   exit=2 · 277 ms   comprobado: tarea_entregada 2 → 2
── 07-E2 Stop (x3_entrega2.py): (f) 'SELECT …; echo 1' con la consulta real en 0 se rechaza ──   exit=2 · 283 ms   comprobado: tarea_entregada 2 → 2
── 07-E3 Stop (x3_entrega2.py): (k) ejecución fingida con echo del texto de la comprobación se rechaza ──   exit=2 · 282 ms   comprobado: tarea_entregada 2 → 2
── 07-E4 Stop (x3_entrega2.py): (g) control: verde con '0 errors' se acepta ──   exit=0 · 370 ms   comprobado: tarea_entregada 2 → 3
── 07-E5 Stop (x3_entrega2.py): (h) control: PostToolUseFailure y después verde real se acepta ──   exit=0 · 296 ms   comprobado: tarea_entregada 3 → 4
══ Resumen ══  CUMPLE ×70 · NO CUMPLE ×0 · exit 0
```
Casos de 34ded4a (pie en el último párrafo), salida real:
```
── B5.2 commit-msg (control): pie completo en el último párrafo con Co-Authored-By ──   exit=0 · 293 ms   comprobado: trailers para git: ['Chat', 'Model', 'Plan', 'Tarea', 'Co-Authored-By']
── B5.4 commit-msg: pie y Co-Authored-By en párrafos finales distintos → se unen en un bloque que git lee como trailers ──   exit=0 · 292 ms
comprobado: trailers para git tras normalizar: ['Chat', 'Model', 'Plan', 'Tarea', 'Co-Authored-By']
── B5.5 commit-msg: Chat/Model/Plan/Tarea en medio del cuerpo y no en el último párrafo ──   exit=1 · 246 ms   stderr: COMMIT RECHAZADO por el caparazón: …
══ Resumen ══  CUMPLE ×45 · NO CUMPLE ×0 · exit 0
```
Casos de 700d77c (casos (a), (b) y exit code de 07), salida real:
```
── B6.2a PostToolUseFailure: la comprobación termina con exit code 1 y queda registrada ──   exit=0 · 317 ms
── B6.2b Stop: ENTREGA con la salida verde anterior cuando la última ejecución falló ──   exit=2 · 286 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la última ejecución de la comprobación terminó con exit code 1; la salida real de la comprobación indica fallo («Exit code 1»); la salida pegada no es la salida real: …
── B6.2c PostToolUse: la comprobación en rojo por una tubería (exit 0, '2 failed') ──   exit=0 · 304 ms
── B6.2d Stop: ENTREGA pegando la salida roja real ──   exit=2 · 302 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: la salida real de la comprobación indica fallo («2 failed»); falta el aviso a 07-verificador … bloqueo:entrega registrado en SYPNOSE.
── B6.5 Stop: ENTREGA válida → lección en KB + tarea_entregada ──   exit=0 · 317 ms   comprobado: registro tarea_entregada=1 evidencia entrega=1
── B6.9a PostToolUse: la consulta devuelve 0 ──   exit=0 · 317 ms
── B6.9b Stop: ENTREGA con el 0 real frente a lo esperado ≥1 ──   exit=2 · 296 ms
stderr: CIERRE IMPEDIDO: ENTREGA rechazada: el resultado observado 0 no cumple lo esperado ≥1. bloqueo:entrega registrado en SYPNOSE.
── B6.10 Stop: ENTREGA válida de una comprobación 'consulta → esperado' ──   exit=0 · 324 ms   comprobado: registro tarea_entregada=2
══ Resumen ══  CUMPLE ×43 · NO CUMPLE ×0 · exit 0
```
Extractos de ejecuciones anteriores con el mismo arnés (cb061cc y 2ad5a54):
```
── B3.1 PreToolUse: Write a la centinela fuera del worktree ──   exit=2 · 242 ms
stderr: CERCO: Write bloqueada por el cerco: c:\micd\coforge santander\02-backend-api\_centinela_fuera.txt está fuera del worktree c:\micd\coforge santander\02-backend-api\wt
── B4.3 flush al vencer el plazo: la cola llega al registro ──   exit=0 · 288 ms   comprobado: registro herramienta:Write=1 bloqueo:cerco=3 · cola=0
── B6.1 Stop: cierre con escrituras y sin ENTREGA ──   exit=2   stderr: CIERRE IMPEDIDO: hay 1 escrituras de la tarea sin bloque ENTREGA (…). bloqueo:entrega registrado en SYPNOSE.
── B7.5 registro caído: aviso visible en la siguiente herramienta ──   exit=0 · 260 ms   stdout: {"systemMessage": "REGISTRO SYPNOSE NO RESPONDE: …"}
── B7.9 registro de vuelta: SessionStart vacía las colas y registra bloqueo:registro_caido ──   exit=0   comprobado: registro bloqueo:registro_caido=2 evidencias=2 · colas=0/0
── B1.2 SessionStart: una tarea en espera_firma no se trabaja; elige la devuelta y enseña el motivo ──   exit=0   comprobado: tarea 9=espera_firma · tarea 33=trabajando
── B6.12 Stop con stop_hook_active=true y sin ENTREGA ──   exit=0   stdout: {"systemMessage": "CIERRE SIN ENTREGA VÁLIDA: la tarea 33 queda incompleta (bloqueo:entrega_incompleta registrado en SYPNOSE). …"}
── B6.13 Stop: la salida legítima BLOQUEADO: ──   exit=0   stdout: {"systemMessage": "Cierre sin ENTREGA (BLOQUEADO) registrado para Carlos como pregunta_humano."}
```
En modo local las salidas de las comprobaciones son simuladas: prueban el mecanismo, no el requisito.

### 4.2 Instalador
Con `--worktree-extra`, salida real del 15-sep a las 15:06Z (`python probar_instalador.py`, líneas del worktree extra):
```
$ instalar_caparazon.py con-ajenos --modo real --worktree-extra C:\Users\carlo\AppData\Local\Temp\probar-instalador-zp4x7b5v\con-ajenos\wt-plantilla:specs/T01/** → exit 0
      git (wt-plantilla): extensions.worktreeConfig=true
      git (C:\Users\carlo\AppData\Local\Temp\probar-instalador-zp4x7b5v\con-ajenos\wt-plantilla): core.hooksPath (solo ese worktree) = C:/Users/carlo/AppData/Local/Temp/probar-instalador-zp4x7b5v/con-ajenos/.claude/caparazon/githooks
worktrees_extra: [{'ruta': 'C:\\Users\\carlo\\AppData\\Local\\Temp\\probar-instalador-zp4x7b5v\\con-ajenos\\wt-plantilla', 'permitidos': ['specs/T01/**']}] · core.hooksPath del worktree extra: C:/Users/carlo/AppData/Local/Temp/probar-instalador-zp4x7b5v/con-ajenos/.claude/caparazon/githooks
reinstalar no cambia nada (20 ficheros, ni contenido ni fecha): True
      git (C:\Users\carlo\AppData\Local\Temp\probar-instalador-zp4x7b5v\con-ajenos\wt-plantilla): core.hooksPath retirado
desinstalar: core.hooksPath del worktree extra = ''
RESULTADO: CUMPLE
```
Con la barrera en vivo: `cd caparazon/pruebas && python probar_instalador.py` (carpetas temporales), salida real del 15-sep a las 13:02Z:
```
$ instalar_caparazon.py con-ajenos --modo real → exit 0
      INSTALADO (marcador de instalación: sin él los hooks no escriben en vivo)
      .claude/settings.json (hooks, permisos, servidores MCP, SYPNOSE_MODO=real)
marcador INSTALADO: {'carpeta_ruta': 'C:\\Users\\carlo\\AppData\\Local\\Temp\\probar-instalador-aw3ukths\\con-ajenos', 'worktree': 'C:\\Users\\carlo\\AppData\\Local\\Temp\\probar-instalador-aw3ukths\\con-ajenos\\wt', 'instalador': 'C:/MICD/Coforge Santander/08-caparazon/wt-plantilla/caparazon/instalar_caparazon.py'}
settings.env: {'AJENA': '1', 'SYPNOSE_MODO': 'real'} · hook ajeno conservado: True
reinstalar no cambia nada (20 ficheros, ni contenido ni fecha): True
$ instalar_caparazon.py con-ajenos --desinstalar → exit 0
      INSTALADO retirado: los módulos que se conservan ya no escriben en vivo
desinstalar: settings.json igual al original=True · bytes iguales={'CLAUDE.md': True, '.claude/settings.json': True} · .mcp.json existe=False · módulos activos=False · en .claude queda=['caparazon-desinstalado-20260915-150236', 'settings.json', 'settings.json.bak-caparazon-20260915-150235']
modo por defecto: settings.env={'SYPNOSE_MODO': 'prueba'}
desinstalar deja la carpeta limpia como estaba: True (['CLAUDE.md'])
RESULTADO: CUMPLE
```
Antes de la barrera (34ded4a): `reinstalar no cambia nada (18 ficheros)` con los eventos SessionStart…PostModelSwitch, y con un hook y un
permiso ajenos `reinstalar no cambia nada (19 ficheros, ni contenido ni fecha)`.

### 4.3 Commits, push y modelo real
- Primera entrega: ddc25b5 B1 · c0d4aa3 B2 · d92e6bc B3 · 9cbf14f B4 · eae906f B5 · 88fb6b3 B6 · 4f1c2ef B7 · f2a190f B8 · dda0c4e B9 · ef4407c B1.
- Decisiones del lead: 98e237e B4 · d26ca1d B1 · 878fb1b B2 · 5083a5a B3 · 8545625 B5 · 25cea2a B6 · fe11e25 B7 · eb56ace B8 · d44a9f4 B9.
- Estado real de PLAN-CS-T01: 10c6bfd B1 · 7b558a5 B6 · cb061cc B9.
- Stop en continuación: 38a6fe0 B6 · c63201d B1 · 2ad5a54 B9.
- Casos (a) y (b) de 07 y exit code: a899976 B4 · 270d40b B7 · 8d655e2 B6 · 48dcd4b B1 · 700d77c B9.
- Pie en el último párrafo: 0c9714d B5 · 38e8ca1 B7 · 599f49b B1 · 34ded4a B9.
- Evasiones y hallazgos de 07: 19fcefa B6 · 9b5a6cd B4 · e475d34 B5 · d8e42aa B1 · ee48999 B7 · 0def414 B9.
- BD del registro, hallazgo (s): e918313 B6 · 8a91a01 B1 · 9c33f03 B9.
- Barrera en vivo y `~` en la BD (incidente del 15-sep): 83be252 B4 · c858b6d B6 · 55d6526 B1 · e6f0716 B8 · a81c315 B7 · b33c05f B9.
- Sesión real de 02 (brief sin SessionStart) y `cwd` del arnés: bd38c56 B2 · e3ba4e0 B1 · 78665a5 B9.
- Examen real de 07 (KB caída y evidencia con resumen): 91a6090 B4 · 47e61bf B6 · 2f35a2c B1 · e215054 B9.
- `bloqueo:kb_caida` (decisión del lead): 334a0eb B4 · 8426351 B1 · cc2ad8f B9.
- Cerco de la sesión real de 02 (rutas de shell y `worktrees_extra`): 91038b2 B3 · 00e5a4a B4 · 0c91faf B1 · 577863e B5 · 99764fb B8 · faab629 B9.
- B10, sesión sin tarea (decisión del lead): 59c498e B10.
- B11, el cerco lee el comando entero (decisión del lead): 356d11b B11.
- B12, el requisito vigente sale del registro (decisión del lead): f1ef77f B12.
- B13, varias tareas trabajables en el mismo plan (decisión del lead): 9e41ca1 B13.
- B14, un chat con varios planes abiertos (decisión del lead): 591128d B14.
- B15, la cerca bloquea git de escritura por SSH (orden del lead): dc94097 B15.
- B16+B17, casefold Windows y aviso reintentable (lead, 16-sep): 723787a B16+B17. main bbd6cca.
- B18, túnel aviso (lead, 16-sep): 63c7439 B18. main 7aedb15.
- B19, descubrimiento de planes (lead, 16-sep): a89d1e6 B19. main 9f891bb.
- B6.29b, plan inexistente dice causa real (lead, 16-sep): d8b22ac B6.29b.
- B20, auditoría merge (lead, 16-sep): 0e43d77 B20. 159/159 CUMPLE.
- B21, descriptor de fichero en redirecciones (lead, 16-sep): 9f2bcdd B21. 161/161 CUMPLE.
- B22, forma_pura multi-worktree (lead, 16-sep): 1a98768 B22. 163/163 CUMPLE.
```
   f1ef77f..9e41ca1  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(65d7940) HEAD → exit 0   (f1ef77f ya está en main)
9e41ca1 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B13 Co-Authored-By=Claude Opus 5 <noreply@anthropic.com>
   356d11b..f1ef77f  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(ed32bec) HEAD → exit 0   (356d11b ya está en main)
f1ef77f Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B12
   59c498e..356d11b  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(3926578) HEAD → exit 0   (59c498e ya está en main)
356d11b Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B11
   faab629..59c498e  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(59998e2) HEAD → exit 0   (faab629 ya está en main)
59c498e Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B10
   cc2ad8f..faab629  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(da7c369) HEAD → exit 0   (cc2ad8f ya está en main)
faab629 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
99764fb Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B8
577863e Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B5
0c91faf Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
00e5a4a Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B4
91038b2 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B3
   e215054..cc2ad8f  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(4dc4884) HEAD → exit 0   (e215054 aún no está en main)
cc2ad8f Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
8426351 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
334a0eb Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B4
   78665a5..e215054  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(c5d2324) HEAD → exit 0   (78665a5 ya está en main)
e215054 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
2f35a2c Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
47e61bf Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B6
91a6090 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B4
   b33c05f..78665a5  chat/08-caparazon -> chat/08-caparazon
git merge-tree --write-tree origin/main(91cd029) HEAD → exit 0   (b33c05f ya está en main)
78665a5 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
e3ba4e0 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
bd38c56 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B2
b33c05f Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
a81c315 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B7
e6f0716 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B8
55d6526 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
c858b6d Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B6
83be252 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B4
```
**Model del pie comprobado contra el transcript de esta sesión** (`41c155fe….jsonl`):
- `/model claude-opus-5` a las 09:25:32Z;
- `claude-opus-4-6`: 5 respuestas, de 09:25:30Z a 09:25:33Z;
- `claude-opus-5`: todas las siguientes, desde 09:25:37Z;
- los commits (10:56Z–11:39Z) llevan `Model: claude-opus-5`.

Desde 0c9714d el pie va en el último párrafo junto a `Co-Authored-By` y git lo lee:
```
$ git log -4 --format='%h Chat=%(trailers:key=Chat,valueonly,separator=) Model=… Plan=… Tarea=…'
34ded4a Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B9
599f49b Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B1
38e8ca1 Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B7
0c9714d Chat=08-caparazon Model=claude-opus-5 Plan=PLAN-CS-T01 Tarea=B5
```
Los 30 commits anteriores (ddc25b5…700d77c) llevan el pie en el párrafo previo a `Co-Authored-By`: `%(trailers)` no lo lista y
`grep` sí. No se reescriben: ya están publicados y 07 verificó sobre sus hashes.

### 4.4 Modo real (lo ejecutó el lead, no 08)
- 08 no instaló ni escribió en el registro vivo: no tiene el OK directo de Carlos en este chat, y así se lo dijo al lead.
- El lead instaló el caparazón en 02-backend-api con `--modo real` desde plantilla main 745e8b3, "por delegación explícita de Carlos
  (POC)" (evento 22532). El arquitecto creó la tarea 48 (R1) para 02 (evento 22531).
- X3 real no usa `probar_bloqueos.py --modo real`. 07 lo rechazó por D7 (escribiría en vivo con el actor de otro rol y después lo
  juzgaría) y observa en solo lectura la sesión real de 02. Primeros eventos llegados por la cola, todos con actor
  `IA:02-backend-api:claude-sonnet-5`: `sesion_iniciada` 22533, `tarea_trabajando` 22534, `herramienta:Bash` 22535–22540 y
  `bloqueo:cerco` 22541.
- Esa sesión se abrió antes de instalar y no pasó por SessionStart, así que no recibió el brief (arreglado en bd38c56 y e3ba4e0). Le
  llegó con el primer prompt a las 14:28:12Z, cuando sus módulos pasaron a 78665a5 (plantilla main 04f773f).
- El lead fusionó hasta cc2ad8f (main 3c7a0db) y reinstaló en 02. Comprobado por 08 en solo lectura: los 11 módulos instalados en
  `02-backend-api/.claude/caparazon` son idénticos a los de cc2ad8f (sha256 con los finales de línea normalizados), `INSTALADO`
  sigue ahí y `comun.py` trae `bloqueo:kb_caida`.
- El arquitecto fusionó 59c498e (B10) en main (0f61e49) y reinstaló en 02 en modo real con `--worktree-extra
  "C:\MICD\Coforge Santander\02-backend-api\wt-plantilla:specs/T01/**"`. Comprobado por 08 en solo lectura:
  - los 11 módulos instalados son idénticos a los de 59c498e;
  - `INSTALADO` presente, `settings.env` = `{'SYPNOSE_MODO': 'real'}` y `brief.py` con `sin_tarea`;
  - `worktrees_extra` = `[{'ruta': 'C:\\MICD\\Coforge Santander\\02-backend-api\\wt-plantilla', 'permitidos': ['specs/T01/**']}]`;
  - el worktree extra existe y su `core.hooksPath` apunta a `02-backend-api/.claude/caparazon/githooks`, así que commit-msg está
    enganchado ahí.
- El arquitecto fusionó 356d11b (B11) en main (ed32bec) y reinstaló en 02 en modo real con el mismo `--worktree-extra`. Comprobado
  por 08 en solo lectura: los 11 módulos instalados son idénticos a los de 356d11b, `cerco.py` trae `ComandoIlegible`, `INSTALADO` y
  `SYPNOSE_MODO=real` siguen ahí, `worktrees_extra` no cambia y commit-msg sigue enganchado en `wt-plantilla`.
- El arquitecto fusionó f1ef77f (B12) en main (0e95312) y reinstaló en 02 en modo real con el mismo `--worktree-extra`. Comprobado
  por 08 en solo lectura: los 11 módulos instalados son idénticos a los de f1ef77f y `brief.py` trae `refrescar_trabajo`. `INSTALADO`,
  `SYPNOSE_MODO=real`, `worktrees_extra` y commit-msg en `wt-plantilla` siguen igual. Desde ahora 02 lee el requisito vigente en cada
  prompt y antes de cada ENTREGA.
- **Veredicto de 07: X3 real CUMPLE** (evento `verificado` 22574, evidencia 182). Lo que comprobó:
  - cerco en vivo en 22541 y 22543 (el centinela no está en disco);
  - ENTREGA válida: comprobación exacta en 22547, `tarea_entregada` 22560 y evidencia 170;
  - con la KB caída la cola se conservó y llegó al volver: `leccion_guardada` 22561, `aviso_verificador` 22562 y
    `bloqueo:registro_caido` 22564. Ese `registro_caido` lo causó en realidad la KB (§8, primer hallazgo del examen real);
  - commit-msg no se ejercitó en real porque 02 no hizo commits.

- El arquitecto fusionó 9e41ca1 (B13) en main (0b694b4) y reinstaló en 02 en modo real con el mismo `--worktree-extra`. Comprobado
  por 08 en solo lectura: brief.py tiene 448 líneas con `pendientes_de_juicio`, `entregas_en_cola`, `listado_tareas` y
  `tarea_de_entrega` (B13 completo). `INSTALADO`, `SYPNOSE_MODO=real`, `worktrees_extra` y commit-msg en `wt-plantilla` siguen igual.
  Desde ahora 02 puede entregar una tarea mientras otra está pendiente de juicio.

#### 4.4.1 Instalaciones nuevas (15-sep, 08 por delegación del lead, 22676)

Receta idéntica a la de 02: merge de plantilla origin/main al branch del chat → `instalar_caparazon.py --modo real` → verificar config
→ registrar `caparazon_instalado`. 4 pasos por carpeta, sin diferencias de procedimiento respecto a 02.

| Carpeta | Plan | worktree-extra | Evento | Plantilla |
|---|---|---|---|---|
| 01-git-cicd | PLAN-CS-T07 | `wt-plantilla:specs/T07/**` | 22786 | main 0b694b4 |
| 03-datos-rag | PLAN-CS-T08 | `wt-plantilla:specs/T08/**` | 22789 | main 7334bb2 |
| 04-agentes | (sin plan fijo: T02+T12) | `wt-plantilla:specs/T02/**,specs/T12/**` | 22790 | main 7334bb2 |

Nota sobre 04-agentes: tiene tareas en dos planes (PLAN-CS-T02 tarea 34 y PLAN-CS-T12 tarea 44). El instalador solo acepta un
`--plan-id`; se omitió para que `brief.py` busque por prefijo y encuentre el plan con la tarea de mayor prioridad.

Verificación de las tres instalaciones:
- 11 módulos copiados (comun, cerco, brief, prompt_submit, pre_tool_use, post_tool_use, stop, model_switch, commit_msg, flush,
  cabeceras_github), `precios.yaml`, `config.json`, `INSTALADO`, `githooks/commit-msg`.
- `.claude/settings.json` con hooks (7 eventos), permisos, servidores MCP y `SYPNOSE_MODO=real`.
- `.mcp.json` con sypnose, knowledge-hub y github.
- CLAUDE.md con sección caparazón.
- `core.hooksPath` enganchado en el wt y en el wt-plantilla de cada carpeta.
- `brief.py` con B13 (pendientes_de_juicio, 448 líneas): confirmado en 01.

PLAN-CS-T01 lo abrió `IA:00-lead:claude-fable-5-1` "por delegación de Carlos" (evento 22216); 07 lo tenía como observación
pendiente de confirmación directa de Carlos. Carlos lo confirmó en el chat de 08 el 15-sep hacia las 16:06Z: «sí, lo delegué en el
lead» (instalación en 02 con --modo real y ratificaciones del POC, eventos 22216, 22494 y 22532). Se lo pasé a 07 y al lead.
07 lo comprobó en la fuente (línea 2243 del transcript de 08: mensaje humano de claude-desktop a las 16:06:16Z) y cerró su nota 22529
para 22216, 22494 y 22532 (evento 22656). Queda abierto 22493, el actor_ratificado de 07, porque la pregunta no lo nombraba; 07 se lo
pregunta a Carlos en su chat.

### 4.5 Sesión real de Claude Code (CLI 2.1.267, copia de 02-backend-api en el scratchpad)
Los hooks corrieron aunque la CLI no llegó al modelo (`OAuth session expired`): `hook_success SessionStart`, brief y EARS en
`hook_additional_context`, y `sesion_iniciada` + `tarea_trabajando` en el registro de prueba.

### 4.6 Propuesta de fase SYPNOSE
`05-arquitecto-sypnose/PROPUESTA-FASE-CANAL-EVENTOS.md`: `POST /evento` y `POST /evidencia` solo INSERT, actor `IA:`, lista blanca,
`clave` de idempotencia y test `node:test`.

### 4.8 Propuesta: túnel SSH como servicio de Windows

**Problema:** el túnel muere con cada reinicio de sesión o del PC y los caparazones de 01, 03 y 04 bloquean los prompts con 0 turnos
útiles y sin aviso (hallazgo operativo del lead, 16-sep-2026). Desde el cambio de aviso, el bloqueo dice la causa y el remedio, pero
el túnel sigue siendo manual.

**Propuesta: NSSM (Non-Sucking Service Manager) como servicio de Windows.**

1. Instalar NSSM (`winget install nssm` o descarga de nssm.cc):
   ```
   nssm install SypnoseTunnel "C:\Windows\System32\OpenSSH\ssh.exe" ^
     "-N -i C:\Users\carlo\.ssh\id_ed25519_radelqui -p 2024 ^
      -L 7101:127.0.0.1:7101 -L 18791:127.0.0.1:18791 -L 18793:127.0.0.1:18793 ^
      sypnose@62.171.147.46"
   nssm set SypnoseTunnel AppStdout C:\Users\carlo\.claude\logs\tunnel.log
   nssm set SypnoseTunnel AppStderr C:\Users\carlo\.claude\logs\tunnel.log
   nssm set SypnoseTunnel AppRestartDelay 5000
   nssm set SypnoseTunnel Start SERVICE_AUTO_START
   ```
2. El servicio arranca con Windows, se reinicia solo al caer (5 s de pausa) y deja log.
3. Healthcheck opcional: un Task Scheduler cada 60 s que haga `curl -s http://127.0.0.1:7101/salud` y, si falla,
   `nssm restart SypnoseTunnel`.

**Alternativa nativa (sin NSSM):**
```
sc.exe create SypnoseTunnel binPath= "C:\Windows\System32\OpenSSH\ssh.exe -N -i ..." start= auto
sc.exe failure SypnoseTunnel reset= 60 actions= restart/5000
```
Limitación: `sc.exe` solo acepta ejecutables con `SERVICE_TABLE`, así que ssh.exe necesitaría un wrapper (srvany.exe o un script
PowerShell con `Register-ScheduledJob`). NSSM lo resuelve sin wrapper.

**Riesgo:** la clave SSH (`id_ed25519_radelqui`) queda accesible al servicio SYSTEM. Mitigación: darle una cuenta de servicio
dedicada con permisos solo sobre esa clave.

### 4.7 Vista previa del brief real de 02 (solo lectura contra el registro del 67 y `gh`)
```
Plan: PLAN-CS-T01 · abierto · dueño H:carlos · worktree C:/MICD/Coforge Santander/02-backend-api/wt
Tareas propias trabajables: [(33, 'R0', 'devuelta')]
Tarea 33 · requisito R0 · progreso devuelta
Motivo de la devolución (IA:07-verificador:claude-opus-5, 2026-09-15T10:33:49.663Z): tarea 33 (R0): NO CUMPLE → devuelta (R1 lo copió el arquitecto, no lo registró el rol 02-backend-api)
Comprobación: SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0' → ≥1  ·  parte ejecutable para la ENTREGA: SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T01' AND ref<>'R0'
Archivos permitidos (02-backend-api/CLAUDE.md §Ficheros propios (plan.afecta = '02-backend-api')): app/main.py, app/api/, app/core/config.py
GitHub (gh): rama chat/02-backend-api: CI sin runs · sin PR · main: CI CI/CD failure 2026-09-14T16:45:59Z https://github.com/radelqui/rag-banking-agent/actions/runs/34870628891
```

## 8. Ajustes, hallazgos y feedback

**Cambios respecto al traspaso (§11), aceptados por el lead:**
- sin estado `entregada`; `kb_save` por HTTP; aviso a 07 exigido;
- `sypnose` SSH-stdio y `knowledge-hub` SSE 18793;
- permitidos = `plan.afecta` o §Ficheros propios; presupuesto = `plan.cuesta`;
- cola en `<carpeta>/.claude/caparazon/cola/`; FAIL LOUD = cola + aviso + `bloqueo:registro_caido`;
- worktree propio; GitHub por `gh`; `precios.yaml` canónico;
- tarea devuelta primero; `consulta → esperado`;
- Stop en continuación = `bloqueo:entrega_incompleta`;
- ENTREGA solo con comprobación en verde;
- pie de commit en el último párrafo junto a `Co-Authored-By`, exigido y normalizado por el hook commit-msg;
- comprobación ejecutada exactamente y veredicto sobre su salida completa; claves de pie únicas;
- una comprobación SQL solo cuenta contra la base del registro configurado;
- escritura en vivo solo con `SYPNOSE_MODO=real`, marcador `INSTALADO` y sesión en la carpeta; si falta algo, modo prueba. El
  instalador pide el modo con `--modo real` (por defecto, prueba);
- B10: sin tarea abierta, el prompt humano pasa con un aviso en castellano llano y solo se bloquea escribir o cambiar cosas; el prompt
  solo se bloquea con el registro caído;
- B11: el cerco lee el comando entero y salta los cuerpos de heredoc; un comando ilegible se bloquea con un mensaje que dice qué hacer;
- B12: el requisito, la tarea y los permitidos vigentes se leen del registro en cada prompt y antes de validar una ENTREGA; con el
  registro caído, la ENTREGA se bloquea;
- B13: con varias tareas trabajables, el brief y cada prompt las listan. `Tarea: <id>` en la ENTREGA entrega esa tarea si es del agente,
  está abierta y no está entregada sin juicio. Si la tarea del estado está entregada y pendiente de juicio, el siguiente prompt pasa a
  la siguiente trabajable;
- B14: con varios planes abiertos, el brief lista tareas de todos y los permitidos del cerco son la unión. `Plan: <id>` en la ENTREGA
  selecciona el plan; commit-msg valida `Plan:` contra `planes_trabajables`;
- B15: la cerca bloquea `ssh host "git commit/push/checkout …"` desde los chats de tecnología; SSH solo para scripts de plantilla/
  contra el registro (sqlite3, python3) y consultas git de solo lectura (log, status, diff, show…);
- B16 (lead, 16-sep, eventos 22803/22837 de 01 y 03): la comparación de rutas permitidas en Windows ya es case-insensitive
  (`casefold` + `re.IGNORECASE`). `specs/t01/file.yaml` pasa contra el patrón `specs/T07/**`. Tests B3.25, B3.25b;
- B17 (lead, 16-sep, eventos 22828/22830, 22879/22884): el brief y el aviso del Stop dicen el orden (`1) send_message a 07,
  2) ENTREGA`). Un rechazo por falta de aviso a 07 NO cierra la tarea como `entrega_incompleta`: la deja `trabajando` para
  reintentar en el siguiente turno (`rechazar(reintentable=True)`). Tests B6.32, B6.32b;
- Túnel aviso (lead, 16-sep, hallazgo operativo): cuando el registro no responde (túnel 7101 caído), el aviso dice la causa y el
  remedio en una línea ("túnel 7101 caído: `ssh -N -i …`") y encola `bloqueo:registro_caido` (no `bloqueo:brief`). El prompt
  bloqueado también dice "Remedio: `<comando>`". La dependencia del túnel está documentada en §1 y la propuesta de servicio Windows
  en §4.8. Tests B7.8, B7.9, B2.4;
- B19 (lead, 16-sep, evento 23407 de 01): `planes_trabajables` se calculaba solo en el SessionStart y no se refrescaba; un plan
  abierto después era invisible para `tarea_de_entrega` y se rechazaba con "no es un plan con tareas trabajables de IA:<carpeta>:*".
  Arreglado en `brief.py`:
  - `tarea_de_entrega`: lee `/plan/<id>` del registro antes de comprobar la caché; si el plan no está en `planes_trabajables`,
    verifica en vivo: estado abierto, dueño `H:`, tareas del agente con progreso pendiente/trabajando/devuelta;
  - `refrescar_trabajo`: escanea `/planes` en cada prompt para descubrir planes nuevos que cumplan `buscar_plan`, añade sus tareas,
    permisos y planes al estado, y lo avisa ("planes nuevos descubiertos: <id>");
  - causa raíz del evento 23407: PLAN-CS-T11 se abrió después del SessionStart de 01 → no estaba en `planes_trabajables` →
    `tarea_de_entrega` lo rechazaba. PLAN-CS-T14 pasaba porque existía al arrancar la sesión;
- B20 (lead, 16-sep, evento 23596 de 02): `cambios_git()` compara contra `sucios_inicio` (foto al inicio de sesión). Tras un
  `git merge main` en un worktree extra, los ficheros del merge aparecían como cambios nuevos fuera de `permitidos` → falso
  `bloqueo:cerco`. Arreglado en `post_tool_use.py`:
  - si el comando Bash/PowerShell contiene `git merge`, `git pull` o `git rebase`, la auditoría añade los ficheros actuales al
    baseline (`sucios_inicio` / `sucios_inicio_extra`) con una unión: los ficheros del merge pasan a formar parte de la foto y
    no se marcan como escrituras del agente;
  - una escritura propia posterior fuera de `permitidos` sigue bloqueada, porque no está en el baseline;
  - causa raíz del evento 23596: 02 hizo `git merge main` en su wt-plantilla; los ficheros del merge (caparazón, FASE4.md, etc.)
    estaban fuera de `specs/T01/**` → auditoría los bloqueó como si 02 los hubiera escrito.

- **B21, descriptor de fichero en redirecciones (lead, 16-sep, evento 23641 en 01):** `shlex` tokeniza `cmd 2>&1` como
  `["cmd", "2", ">&", "1"]`. El `">&"` se saltaba en `_segmento()` pero el `"2"` permanecía en `limpio` como argumento posicional.
  Para comandos ESCRIBE_TODOS (touch, rm, mkdir…), ese `"2"` se convertía en objetivo y el cerco lo bloqueaba como ruta fuera de
  `archivos_permitidos`. Arreglado en `cerco.py:_segmento()`:
  - al encontrar un operador de redirección (`>`, `>>`, `>&`, `<`, etc.), si el último token de `limpio` es un solo dígito, se
    descarta (`limpio.pop()`): es un descriptor de fichero (2>, 1>>, 2>&1), no una ruta;
  - el descarte aplica a los tres bloques: REDIRECCIONES, `">&"` y tokens que empiezan por `>`;
  - causa raíz del evento 23641: 01 ejecutó un Bash con `2>&1` dentro de su worktree; el cerco tomó `"2"` como ruta →
    `"Bash bloqueada por el cerco: 2 está fuera de archivos_permitidos"`.

- **B22, forma_pura multi-worktree (lead, 16-sep):** `forma_pura()` en `stop.py` solo aceptaba `cd <worktree_principal> &&` como prefijo
  válido de la comprobación. Cuando un agente ejecutaba la comprobación desde un worktree_extra (e.g. 01 haciendo
  `cd wt-plantilla && python comprobar_esqueleto.py`), `forma_pura` rechazaba "se ejecutó fuera del worktree". Arreglado:
  - `forma_pura()` construye una lista de zonas válidas: worktree principal, `worktrees_extra[].ruta` de la config y `plan.worktree`
    del registro (resuelto relativo al directorio del proyecto);
  - el check `cerco.dentro(base, zona)` acepta si `base` está dentro de cualquiera de las zonas;
  - una ruta que no pertenece a ninguna zona sigue rechazada;
  - `validar()` pasa `estado["plan"]["worktree"]` al nuevo parámetro `plan_worktree` de `forma_pura`.

**Hallazgos:**
- `evento.firma` es el raíl de certificación: la idempotencia de la cola va por clave natural.
- El estado real de PLAN-CS-T01 rompía dos supuestos del brief y de la ENTREGA: corregidos (B1.2, B6.7–B6.10, §4.7).
- 07 encontró que el Stop bloqueaba en continuación: corregido según decisión del lead (B6.12–B6.14).
- **07 encontró que una ENTREGA con pytest en rojo o con `0` frente a `≥1` se registraba como entregada:** el Stop solo comprobaba
  que la salida fuera real, no que pasara. Al corregirlo apareció un agujero más: un Bash con exit code distinto de 0 va a
  PostToolUseFailure, que el caparazón no escuchaba, y el Stop validaba contra la última salida verde. Corregido (B6.2a–B6.2e,
  B6.9a–B6.9c).
- **07 encontró tres evasiones más** y dos fallos del pie:
  - (e) `| grep` esconde el rojo, (f) `; echo 1` da el número esperado y (k) un `echo` del texto de la comprobación cuenta como ejecución;
  - se aceptaban claves de pie repetidas y un `Nota:` se absorbía como trailer.

  Regla del lead: la comprobación solo cuenta ejecutada exactamente, y el veredicto sale de su salida completa. Corregido y con los
  scripts de 07 portados al arnés (B6.2f–B6.2l, B6.9d–B6.9f, B5.6, B5.7, 07-T1–07-T8, 07-E1–07-E5). Añadido sin que se pidiera: la
  comprobación ejecutada en otra carpeta tampoco cuenta (B6.2k).
- **Consecuencia:** la comprobación del registro se ejecuta tal cual está escrita. Si un chat necesita `python -m pytest` en vez de
  `pytest`, hay que cambiar el texto de la comprobación en el requisito, no el comando. Las consultas SQL son la única forma envuelta
  que se admite (`sqlite3 <bd> "<consulta>"`, directa o por ssh), porque `SELECT …` no es un comando de shell.
- **07 encontró (s):** esa forma envuelta aceptaba cualquier base de datos, así que una BD preparada con el número esperado pasaba.
  Corregido (B6.9g–B6.9o y 07-E6):
  - la BD tiene que ser la del registro configurado;
  - ssh solo va al destino configurado y con opciones de una lista blanca: `-o HostName` o `-J` llevarían la conexión a otro servidor
    sin cambiar el destino escrito;
  - sqlite3 solo admite opciones de formato: `-cmd` o `-init` ejecutarían otra orden.

  El brief enseña la forma exacta para las comprobaciones SQL.
- **Incidente del 15-sep 12:34Z (lo contó 07 y lo relevaron el arquitecto y el lead).** Los casos s6c/s6d de
  `x3_entrega4_controles.py` ejecutaron los hooks desde una copia con `SYPNOSE_REGISTRO_ESCRITURA=ssh`, el destino real y la clave del
  PC, y escribieron en el registro vivo los eventos 22437–22450 y las evidencias 148 y 149.
  - Qué hizo 07: backup, `correccion_verificador` y `bloqueo:verificador`. No se borró nada; cómo neutralizar 148/149 lo decide el lead.
  - Lectura del registro hecha por 08: no hay eventos de `IA:08-caparazon` desde el 15-sep, así que el arnés de 08 no escribió en vivo.
  - Causa en el caparazón: la escritura por defecto era ssh y nada distinguía una copia de pruebas de una instalación.
  - Corregido con la barrera del lead (B4.4–B4.9, B9.1). Además, el modo local del arnés ya no tiene un ssh que se pueda ejecutar.
- **07 vio que `~/sypnose-f1/registry.db` se rechazaba** según cómo estuviera escrita la BD en el config: solo se expandía el `~` del
  comando, así que con `ssh.db: ~/sypnose-f1/registry.db` en el config la consulta a esa misma ruta no contaba. Ahora `~` se expande en
  el config y en el comando (B1.3, B6.15–B6.18).
- **Encontrado por 08 antes de X3 real:** en `--modo real`, el arnés llamaba a `flush.py` (B4.2, B4.3 y B7.4) sin `cwd` en la entrada.
  - La barrera tomaba entonces el directorio del proceso (`pruebas/`), fuera de la carpeta.
  - B4.3, B7.4 y B7.5 habrían salido NO CUMPLE sin fallo de los hooks, porque Claude Code siempre pasa `cwd`.
  - El arnés ya pasa el `cwd` de la sesión. B4.9 prueba que cuenta el `cwd` de la entrada aunque el proceso esté fuera.
- **07 vio `sesion_iniciada` con origen "?" en la sesión real de 02 (evento 22533).** La causa:
  - la sesión se abrió en Claude Desktop 2.1.270 el 14-sep a las 10:28Z, antes de la instalación (15-sep 14:16Z), y los hooks se
    cargaron a mitad de sesión;
  - SessionStart no llegó a ejecutarse: en su transcript solo hay hooks UserPromptSubmit y Stop;
  - el estado lo creó el primer UserPromptSubmit, que no trae `source` ni `model`, y el brief completo no llegó al modelo, porque
    solo lo entregaba SessionStart.

  Corregido (B2.1, B2.2): el evento dice qué hook creó el estado y el primer UserPromptSubmit sin brief entregado lo inyecta una sola
  vez; SessionStart deja anotado `brief_entregado`. La sesión viva de 02 lo recibirá en su próximo prompt cuando se actualicen sus
  módulos; reinstalar no toca ni estado ni cola.
- **Examen real de 07 (15-sep, solo lectura sobre la sesión viva de 02), dos hallazgos más:**
  1. Con el túnel de la KB caído (18791, WinError 10061), el envío se paraba en la KB y retenía también la entrega de la tarea 48, su
     evidencia, el aviso y 4 lotes de herramientas. Corregido según la decisión del lead (B6.19 y B6.20):
     - primero va el registro y después la KB;
     - si la KB falla, solo se quedan en la cola la lección y su `leccion_guardada`, porque ese evento no puede llegar antes de que la
       lección exista;
     - al volver la KB se registra `bloqueo:kb_caida` con las operaciones retenidas y su evidencia, para que la vista de bloqueos lo
       cuente. Una caída solo de la KB ya no se anota como `bloqueo:registro_caido`.
  2. La evidencia de la entrega mostraba la línea de puntos de pytest y no "15 passed". La salida no se estaba cortando: pytest no
     imprimió el resumen. La comprobación lleva `-q` y el `pytest.ini` de 02 tiene `addopts = -q`, lo que da `-qq`, y con `-qq` pytest
     omite la línea "N passed in …" (probado: `-q` → "2 passed in 0.01s"; `-qq` → solo los puntos).
     - Corregido en el caparazón (B6.21 y B6.22): la evidencia lleva la línea de resumen si la hay, dice cuando no la hay y guarda la
       salida completa.
     - Decisión del lead: se corrige en el dato, no en el hook. 02 cambia su comprobación en el spec a
       `pytest tests/test_main.py tests/test_engine_mode.py` (el `-q` del `pytest.ini` ya imprime "N passed") y sus tareas vuelven a
       verificación.
- **Sesión real de 02, dos correcciones urgentes del cerco (lead, 15-sep):**
  1. El chat no podía escribir su spec en el repo plantilla (D5): 02 recibió un bloqueo por `git -C "C:\MICD\Coforge Santander\plantilla"
     worktree list`. Ahora existe `worktrees_extra` en `config.json` (instalador: `--worktree-extra "<ruta>:<patrón>"`).
     - Cada escritura se mide contra el worktree que la contiene (el del chat o uno extra, el más interno) y sus permitidos, que admiten
       globs (`**`, `*`, `?`).
     - `git -C` y `--work-tree` valen dentro de cualquiera de esos worktrees; lo que cambien lo revisa la auditoría git, que también
       mira los extra.
     - commit-msg se engancha en los extra.
     - Casos: B3.9–B3.12, B4.10, B4.11 y `probar_instalador.py`.
  2. **Hueco real con rutas de shell.** Con el Python 3.13 de los hooks, `os.path.isabs('/c/…')` es False, así que
     `objetivos_shell` convertía `/c/MICD/…` en `C:\c\MICD\…` y `~/x` en `<worktree>\~\x`. Las escrituras a fuera se bloqueaban con una
     ruta equivocada, una escritura legítima con ruta POSIX dentro del worktree se bloqueaba, y `~/…` pasaba por una ruta interna del
     worktree: con permitidos glob habría podido colarse.
     - Ahora todos los objetivos pasan por `norm()`, que entiende `/c/…`, `~` y rutas relativas.
     - Casos: B3.5 (POSIX), B3.6 (`~`), B3.7 (relativa) y B3.8 (control POSIX dentro del worktree).
  - De paso, dos falsos positivos de la lectura de git: `git worktree list` tomaba "list" como destino, y `git worktree add -b <rama>
    <ruta>` tomaba la rama en vez de la ruta. Casos B3.13 y B3.14.
- **B11, evento 22672 de 02.** La hipótesis inicial del lead era un `cd … && pytest` con espacio en la ruta. Al leer el detalle
  completo del evento y el transcript de 02 salió otra causa, y se le comunicó antes de tocar nada:
  - lo bloqueado era un `git commit -m "$(cat <<'EOF' …)"` cuyo mensaje contenía "->";
  - el cerco lo leía línea a línea;
  - el respaldo `split()` rompía la ruta con espacio.

  Arreglado leyendo el comando entero, saltando los cuerpos de heredoc y bloqueando lo ilegible con un mensaje claro (B3.20–B3.24).
- **B12, eventos 22685–22693 de 02.** El Stop rechazó la entrega con la comprobación nueva y aceptó la vieja. Diagnóstico, comunicado
  al lead antes de tocar nada:
  - la comprobación salía de la foto guardada en el estado de la sesión;
  - el registro (una fila por requisito) y la API ya tenían el texto nuevo.

  Arreglado leyendo el requisito vigente en cada prompt y antes de cada ENTREGA; con el registro caído, la ENTREGA se bloquea (B6.23,
  B6.23b, B2.5 y B6.24). 22693 lo decide 07.
- **B13, tareas 9, 48 y 49 de 02.** La regla de "entregada y pendiente de juicio" se validó contra el registro real, en solo lectura,
  antes de escribir código (§2 B13). No basta con lo que guarda la sesión: 22693 y 22712 ya estaban en el registro antes de B13, así
  que ninguna sesión las tiene anotadas. Por eso cada prompt consulta el registro cuando hay dos o más tareas trabajables.
- **01-git-cicd, 03-datos-rag y 04-agentes instalados el 15-sep** (eventos 22786, 22789, 22790) por delegación del lead (22676).
  Los tres bloqueadores que tenía 01 los resolvió el arquitecto antes de la instalación:
  - `wt-plantilla` creado (rama chat/01-git-cicd del repo plantilla, HEAD 13f4c22 → fast-forward a 0b694b4);
  - `wt` pasado a chat/01-git-cicd;
  - tarea 15 bloqueada por 39 (R0 primero).
  04-agentes tiene dos planes (T02 y T12): se instaló sin `--plan-id` fijo para que el brief busque por prefijo.
- Límites conocidos:
  - el destino relativo de `git clone`/`git worktree add` que lleva `-C` se calcula desde el `cwd` de la sesión y no desde el
    directorio de `-C`. Es conservador: con `-C` fuera de los worktrees el comando ya se bloquea;
  - la barrera toma por KB de pruebas una URL local explícita que no use el puerto 18791: si la KB real se alcanzara por un túnel en
    otro puerto local, una prueba con esa URL escribiría en ella;
  - la barrera evita accidentes, no actos deliberados (lo señaló 07 al verificar b33c05f): `INSTALADO` es un JSON sin firma, así que
    una instalación falsificada a mano la pasa. Firmarlo no cambiaría el fondo: quien puede falsificarla también tiene la clave SSH
    del PC y puede escribir en el registro sin pasar por los hooks;
  - en una comprobación SQL, una ruta de Windows sin comillas pierde las barras invertidas en Bash y no cuenta; una ruta con `..` que
    resuelve a la BD del registro sí cuenta (controles de `x3_entrega4.py` de 07);
  - el cerco de shell y los marcadores de fallo son heurísticos: una salida en verde que imprima una línea que empiece por `ERROR`
    se rechazaría, y la salida es `BLOQUEADO:`;
  - un SessionStart con el registro caído tarda ~6,4 s y con `gh` ~3 s;
  - un `bloqueo:registro_caido` puede duplicarse si un lote llega pero su respuesta se pierde.

**Feedback al SM**
- **Sistema/Repo:**
  - falta un canal de escritura para agentes (§4.6);
  - `/tarea/estado` firma como `HUMANO`;
  - el orden de trabajo entre tareas debería darlo el registro;
  - el pie de commits pasa a regla del CLAUDE.md raíz (último párrafo junto a `Co-Authored-By`); el hook commit-msg la exige y los
    30 primeros commits de 08 quedan con el formato anterior.
- **Prompt/Comunicación:** las contradicciones iniciales están resueltas en el CLAUDE.md de 08 y en X3. Que "entrega con salida
  real" significa "salida real y en verde" no lo decía ningún documento: lo destapó el ataque de 07.
- **Flujo/Proceso:**
  - cambié la ruta del código mientras 07 verificaba: los movimientos de ruta hay que anunciarlos antes;
  - los mensajes de 07 a 08 estuvieron en pausa y el hallazgo llegó por relevo del arquitecto: conviene que 07 escriba también en
    su VERIFICACION.md la línea "Para 08", como hizo;
  - 08 no instaló ni escribió en vivo por relevo: lo ejecutó el lead por delegación, que Carlos confirmó en este chat el 15-sep;
  - un arnés de pruebas no debería poder llegar a destinos reales: el de 08 ya lleva `ssh.bin` sin ejecutable y `SYPNOSE_MODO=prueba`,
    y convendría lo mismo en los scripts de 07.

**Respuesta de Carlos en este chat (15-sep, hacia las 16:06Z):** «sí, lo delegué en el lead». La pregunta era si había delegado en el
lead la instalación en 02 con --modo real y las ratificaciones del POC (eventos 22216, 22494 y 22532).

~~Pregunta abierta a Carlos (15-sep):~~ resuelta. 01-git-cicd, 03-datos-rag y 04-agentes instalados por delegación del lead (22676).

**Medición: pasos distintos en la instalación de 01/03/04 respecto a 02**

Receta común (4 pasos): merge plantilla origin/main → `instalar_caparazon.py --modo real` → verificar config → registrar
`caparazon_instalado`. Las cuatro carpetas usaron el mismo procedimiento. Las diferencias son previas o de parámetros, no de pasos:

| Carpeta | Pasos | Diferencia respecto a 02 |
|---|---|---|
| 02-backend-api | 4 | (referencia) — primera instalación, evento 22532 |
| 01-git-cicd | 4 | el arquitecto resolvió antes 3 bloqueadores: wt-plantilla creado, wt pasado a chat/01-git-cicd, tarea 15 desbloqueada de 39 |
| 03-datos-rag | 4 | ninguna — ya tenía wt-plantilla |
| 04-agentes | 4 | dos planes (T02+T12): se omitió `--plan-id` para que brief.py busque por prefijo; `--worktree-extra` con dos patrones glob |

Conclusión: 0 pasos distintos en el procedimiento. Las diferencias son de prerequisitos (01) o de configuración de parámetros (04),
no de la secuencia de instalación.

═══ FIRMA ═══ 08-caparazon / 150926
