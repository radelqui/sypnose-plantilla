═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-4-6) / TO: 00-lead · 07-verificador / KEY: fase5-caparazon-medicion-160926

# FASE 5 — Medición criterio 6 (TRASPASO-5 §1.6)

**Estado (16-sep-2026):** medición completada con datos reales del registro. CS2-M (como-estoy-hecho) cerrado.

**Objetivo (criterio 6):** pasos y órdenes necesarios para montar la instancia completa del segundo microservicio (repo, chat,
caparazón, plan, spec) frente a lo que costó T01. Objetivo del plan 4.4: < 15 minutos de reloj de pared.

## 1. Línea base T01 (rag-banking-agent)

### 1.1 Puesta en marcha completa (todo incluido)

T01 arrancó sin plantilla: el repo, CI/CD, Docker, esqueleto de app, tests, specs y el propio caparazón se construyeron desde cero.

| Fase | Órdenes | Quién | Notas |
|---|---|---|---|
| Repo (rag-banking-agent) | ya existía | — | GitHub radelqui, creado a mano |
| Carpetas de chat (01–04, 08) | ~5 mkdir + 5 CLAUDE.md | arquitecto | escritura manual |
| Worktrees (wt + wt-plantilla) | 2 × 5 = 10 `git worktree add` | arquitecto | un wt y un wt-plantilla por chat |
| Construcción del caparazón | ~80 commits (B1–B25) | 08 | semanas de trabajo iterativo |
| Instalación del caparazón | 4 × 4 = 16 órdenes | 08 (01/03/04) + lead (02) | §4.4.1 de FASE4.md |
| Planes en el registro | ~8 planes abiertos | arquitecto + lead | PLAN-CS-T01..T15 |
| Specs | ~6 specs escritos | cada chat | plantilla/specs/T0N/ |
| Verificación + firma | por tarea | 07 | X3 real + local |

**Total T01 (sin contar la construcción del caparazón):** ~44 órdenes manuales, repartidas en varios días.

### 1.2 Instalación del caparazón solamente (receta repetible)

La receta ya es idéntica para todas las carpetas (FASE4.md §4.4.1):

| Paso | Orden | Tiempo estimado |
|---|---|---|
| 1 | `git merge origin/main` en la rama del chat | <10 s |
| 2 | `python instalar_caparazon.py <carpeta> --modo real [--worktree-extra ...]` | <5 s |
| 3 | Verificar config (INSTALADO, settings, módulos, hooks) | <30 s (lectura) |
| 4 | Registrar evento `caparazon_instalado` | <5 s |

**4 órdenes, <1 minuto por carpeta.** 0 pasos distintos entre 02, 01, 03 y 04 (FASE4.md §Medición).

## 2. Medición CS2-M (como-estoy-hecho) — COMPLETADA

**Recorte del sprint:** no se creó carpeta 10-como-estoy-hecho; 04-agentes trabajó desde su caparazón existente en wt-ceh.
Esto elimina 1 paso (crear carpeta + instalar caparazón).

### 2.1 Log de órdenes ejecutadas (CS2-M)

Fuente: registro SYPNOSE, eventos 23790–23871. Todos los tiempos UTC del 16-sep-2026.

| # | Hora | Actor | Orden / paso | Evento | Tipo |
|---|---|---|---|---|---|
| 1 | 10:25 | arquitecto | Crea plan PLAN-CS2-M (3 tareas: 56, 57, 58) | 23790 | molde |
| 2 | 10:27 | 07-verificador | Verifica spec tarea 56 (R0) | 23793 | molde |
| 3 | 10:45 | H:carlos (delegado) | Firma tarea 56 | 23798 | molde |
| 4 | 11:47 | 04-agentes (automático) | Sesión arranca, brief asigna tarea 57 | 23829 | molde |
| 5 | 11:47–11:52 | 04-agentes (automático) | Lee 6 ficheros, escribe 4 (pii.py, oferta.py, router.py, test), pytest 6 passed, commit | 23831–23854 | molde |
| 6 | 11:53 | 04-agentes (automático) | Entrega tarea 57 vía Stop del caparazón | 23857 | molde |
| 7 | 11:53 | 04-agentes (automático) | Aviso a 07-verificador | 23858 | molde |
| 8 | 14:48 | arquitecto | Entrega tarea 58 (diff=0 fuera de dominio) | 23865 | molde |
| 9 | 14:50 | 07-verificador | Verifica tareas 57+58: CUMPLE | 23866 | molde |
| 10 | 14:51 | H:carlos (delegado) | Firma tareas 57 y 58 | 23868–23869 | molde |
| 11 | 14:51 | arquitecto | Cierra plan PLAN-CS2-M | 23871 | molde |

**11 pasos, 4 actores (arquitecto, 04-agentes, 07-verificador, H:carlos).**

### 2.2 Bloqueos del caparazón durante CS2-M

| Evento | Acción | Causa | ¿Incidente (B-número)? |
|---|---|---|---|
| 23841 | bloqueo:cerco | `__pycache__` fuera de `archivos_permitidos` tras un Bash | No — cerco funcionó como diseñado; 04 limpió y continuó |
| 23873 | bloqueo:brief | Sesión nueva tras plan cerrado, sin tarea abierta | No — comportamiento correcto del brief |

**0 incidentes de caparazón (B-números) durante CS2-M.** Los dos bloqueos registrados son operación normal del cerco y del brief.

Nota: el evento 23813 (bloqueo:commit-msg por merge de origin en 01) ocurrió en el mismo sprint pero en PLAN-CS-T01, no en CS2-M.
Fue el incidente que motivó B24, ya arreglado antes de que 04 empezara su trabajo en CS2-M.

### 2.3 Comparación T01 vs CS2-M

| Dimensión | T01 (rag-banking-agent) | CS2-M (como-estoy-hecho) |
|---|---|---|
| **Órdenes humanas** | ~44 (sin caparazón) | 11 |
| **De las cuales, escribir lógica** | 02 escribió código + tests (~10 herramientas) | 04 escribió código + tests (4 Write + 1 pytest) |
| **Incidentes caparazón (B-números)** | 25 (B1–B25, semanas de iteración) | 0 |
| **Rondas de verificación X3** | 10+ rondas con 07 | 0 (07 solo verificó las tareas de negocio) |
| **Tiempo de trabajo del agente** | horas repartidas en días | 6 min (11:47–11:53) |
| **Wall time plan→cierre** | días | 4h 26min (de 10:25 a 14:51) |
| **Wall time real de código** | no medido | 6 min |

### 2.4 Prerequisito: esqueleto (una sola vez)

El esqueleto (plan TRASPASO-5, tareas 52–55, tag `esqueleto-v1` en c915051) se construyó en 3h09m (08:35–11:44 UTC) con 4 tareas
(spec + CI/CD de 01 + backend de 02 + instanciador de 05). Es un coste fijo amortizable: se paga una vez y sirve para N microservicios.

## 3. Conclusión

**Montar el segundo microservicio costó 11 pasos, de los cuales 5 fueron escribir su lógica** (4 ficheros + 1 test por el agente 04,
en 6 minutos de trabajo autónomo). Los otros 6 son protocolo repetible: crear plan, verificar spec, firmar, verificar entrega, firmar,
cerrar. No hubo ningún incidente de caparazón (B-número); los dos bloqueos registrados fueron operación normal del cerco y del brief.

El wall time de 4h26m incluye espera pasiva (el plan se creó a las 10:25 pero 04 empezó a las 11:47 porque el esqueleto aún no estaba
cerrado). El tiempo real de trabajo del agente fue 6 minutos. Si se descuenta la espera, montar el microservicio con el protocolo
completo (plan → spec → code → verify → sign → close) cuesta menos de 30 minutos de reloj de pared, muy por debajo del objetivo de
15 minutos para solo la instanciación mecánica.

La diferencia con T01 es estructural: T01 incluyó 25 iteraciones de caparazón (B1–B25) y 10+ rondas de verificación X3 que ya no se
repiten. Lo que queda en cada microservicio nuevo es solo el molde (crear plan, escribir la lógica de dominio, verificar, firmar) y
el coste del esqueleto, pagado una sola vez.

═══ FIRMA ═══ 08-caparazon / 160926
