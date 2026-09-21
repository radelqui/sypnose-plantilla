═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-4-6) / TO: 00-lead · 07-verificador / KEY: fase5-caparazon-medicion-160926

# FASE 5 — Medición criterio 6 (TRASPASO-5 §1.6)

**Estado (16-sep-2026):** medición T02 completada con datos reales del registro. CS2-M cerrado, CS2-U cerrado.

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

## 3. Medición T02 completa (como-estoy-hecho)

T02 = el segundo microservicio (como-estoy-hecho), montado desde el esqueleto y operado bajo protocolo SYPNOSE.
Incluye los dos planes que lo cubrieron: CS2-M (lógica de dominio) y CS2-U (interfaz React real, correctivo tras hallazgo de 07).

### 3.1 (a) Órdenes de instanciación

Fuente: `plantilla/microservicio/instanciar_microservicio.py` (tag esqueleto-v1, c915051; resync 4afdfde/198b391).

| # | Orden | Qué hace |
|---|---|---|
| 1 | `python microservicio/instanciar_microservicio.py como-estoy-hecho --puerto 8010 --destino <ruta>` | Copia esqueleto, parametriza nombre/puerto/dominio, crea app/como_estoy_hecho/ y tests/como_estoy_hecho/, git init + commit + tag esqueleto-v1 |
| 2 | `cd <repo> && make test` | Ejecuta pytest sobre el esqueleto instanciado (14 tests) |
| 3 | `docker build .` | Verifica que el Dockerfile genera imagen |

**3 órdenes de instanciación.** El esqueleto genera un repo completo con CI, Docker, K8s, health endpoint, middleware de seguridad y tests en verde.

### 3.2 (b) Órdenes del molde SYPNOSE (CS2-M + CS2-U)

Fuente: registro SYPNOSE, solo lectura. Eventos de PLAN-CS2-M (23790–23871) y PLAN-CS2-U (24006–24246).

#### CS2-M — lógica de dominio (11 pasos, ya medidos en §2.1)

| Acción protocolo | Cantidad | Actor(es) | Automático |
|---|---|---|---|
| plan_creado | 1 | arquitecto | no |
| firma_tarea | 3 | H:carlos | no |
| tarea_entregada | 2 | 04-agentes (1), arquitecto (1) | 1 sí, 1 no |
| aviso_verificador | 1 | 04-agentes | sí |
| verificado + evidencia | 1+1 | 07-verificador | no |
| plan_cerrado | 1 | arquitecto | no |
| sesion_iniciada + tarea_trabajando | 1+1 | 04-agentes | sí |
| **Total CS2-M** | **11** | | **3 automáticos** |

#### CS2-U — interfaz React real, correctivo (13 pasos)

Motivado por hallazgo de 07 (eventos 23939–23942): la UI era un placeholder sin React ni fetch.

| # | Actor | Paso | Evento(s) | Automático |
|---|---|---|---|---|
| 1 | 08-caparazon | Crea plan PLAN-CS2-U (2 tareas: 66, 67) | 24006 | no |
| 2 | 04-agentes | Sesión arranca, toma tarea 66 R0 | 24008–24009 | sí |
| 3 | 04-agentes | Escribe index.html, edita router.py, escribe test_ui.py, pytest 3 passed, commit | 24018–24033 | sí |
| 4 | 04-agentes | Entrega tarea 66 | 24034 | sí |
| 5 | 04-agentes | Aviso a 07 | 24035 | sí |
| 6 | 07-verificador | Verifica tarea 66: CUMPLE | 24146 | no |
| 7 | H:carlos | Firma tarea 66 | 24155 | no |
| 8 | arquitecto | Desbloquea tarea 67 | 24156 | no |
| 9 | 04-agentes | Sesión arranca, toma tarea 67 R1 | 24168–24169 | sí |
| 10 | 04-agentes | Merge main, edita router (streaming), reescribe test, pytest 4 passed, commit | 24179–24203 | sí |
| 11 | 04-agentes | Entrega tarea 67 | 24205 | sí |
| 12 | 07-verificador | Verifica tarea 67: CUMPLE | 24223 | no |
| 13 | H:carlos (firma) + arquitecto (cierra) | Firma tarea 67 + cierra plan | 24242, 24246 | no |

**13 pasos, de los cuales 7 automáticos por el caparazón** (sesiones, entregas, avisos).

#### Bloqueos del caparazón durante CS2-U

| Evento | Acción | Causa | ¿Incidente? |
|---|---|---|---|
| 24090, 24127 | bloqueo:entrega | 04 intentó re-entregar T66 ya entregada (esperando juicio) | No — protección correcta |
| 24232 | bloqueo:brief | Sesión nueva sin tarea abierta (ambas entregadas) | No — operación normal |

**0 incidentes de caparazón (B-números) durante CS2-U.**

#### Resumen protocolo combinado CS2-M + CS2-U

| Dimensión | CS2-M | CS2-U | Total T02 |
|---|---|---|---|
| **Pasos protocolo** | 11 | 13 | 24 |
| **De los cuales automáticos (caparazón)** | 3 | 7 | 10 |
| **Órdenes manuales** | 8 | 6 | 14 |
| **Firmas humanas** | 3 | 2 | 5 |
| **Verificaciones 07** | 1 | 2 | 3 |
| **Incidentes caparazón** | 0 | 0 | 0 |

### 3.3 (c) Comparación T01 vs T02

| Dimensión | T01 (rag-banking-agent) | T02 (como-estoy-hecho) |
|---|---|---|
| **Instanciación** | manual (~15 mkdir + configs) | 3 órdenes (instanciar + make test + docker build) |
| **Protocolo SYPNOSE** | ~29 órdenes manuales restantes | 24 pasos (14 manuales + 10 automáticos) |
| **Total órdenes** | ~44 manuales | 27 (3 instanciación + 24 protocolo) |
| **Incidentes caparazón** | 25 (B1–B25) | 0 |
| **Planes necesarios** | ~8 | 2 (CS2-M + CS2-U) |
| **Correctivos** | continuos (B-numbers) | 1 plan (CS2-U, por placeholder UI) |
| **Código escrito por agentes** | repartido en días | 04 escribió 8 ficheros en 2 sesiones |
| **Verificaciones X3 caparazón** | 10+ rondas | 0 (07 solo verificó entregas de negocio) |

**Nota honesta sobre CS2-U:** el plan correctivo (13 pasos extra) existió porque CS2-M entregó un placeholder como UI.
Sin ese defecto, T02 habría costado solo 3 + 11 = 14 órdenes. Con él, costó 27. Ambas cifras son significativamente
menores que las 44 de T01, pero la diferencia (14 vs 27) muestra que un defecto en la entrega duplica el coste del protocolo.

## 4. Conclusión

**Montar el segundo microservicio (como-estoy-hecho) costó 27 órdenes totales: 3 de instanciación + 24 de protocolo SYPNOSE.**
De las 24 de protocolo, 10 fueron automáticas del caparazón (sesiones, entregas, avisos) y 14 manuales.
Sin el defecto del placeholder (CS2-U), habrían bastado 14 órdenes (3 + 11).

Comparado con T01 (~44 órdenes manuales + 25 incidentes B-number + 10+ rondas X3), T02 tuvo 0 incidentes de caparazón
y 0 rondas de verificación X3 sobre el caparazón — 07 solo verificó entregas de negocio.

La diferencia es estructural: T01 construyó el caparazón desde cero (B1–B25); T02 lo heredó funcionando.
Lo que queda por microservicio es el molde (abrir plan, escribir lógica, verificar, firmar, cerrar) y la
instanciación del esqueleto (3 órdenes, <1 minuto). El coste del esqueleto (PLAN-CS-M2, 4 tareas, 3h09m)
se pagó una sola vez.

═══ FIRMA ═══ 08-caparazon / 160926
