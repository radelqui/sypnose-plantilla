═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-4-6) / TO: 00-lead · 07-verificador / KEY: fase5-caparazon-medicion-160926

# FASE 5 — Medición criterio 6 (TRASPASO-5 §1.6)

**Estado (16-sep-2026):** estructura preparada con línea base de T01. Medición de T02 pendiente: 10-como-estoy-hecho no existe todavía.

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
| Construcción del caparazón | ~80 commits (B1–B19) | 08 | semanas de trabajo iterativo |
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

## 2. Medición T02 (como-estoy-hecho) — PENDIENTE

> Se rellena cuando el arquitecto cree 10-como-estoy-hecho (TRASPASO-5 §3, A5.2).

| Fase | T01 (órdenes) | T02 (órdenes) | T02 tiempo | Notas |
|---|---|---|---|---|
| Repo | ya existía | 1 (`instanciar_microservicio.py`) | — | |
| Carpeta de chat + CLAUDE.md | 2 (mkdir + escribir) | — | — | |
| Worktrees | 2 (`git worktree add` × 2) | — | — | |
| Caparazón | 4 (receta §1.2) | — | — | |
| Plan en el registro | 1–2 (abrir + tareas) | — | — | |
| Spec | 1 (escribir R0) | — | — | |
| **Total** | **~12 órdenes** | **—** | **—** | objetivo < 15 min |

### 2.1 Log de órdenes ejecutadas (T02)

> Cada orden anotada con su hora, comando literal y resultado. Se rellena durante la instalación.

(vacío — pendiente de A5.2)

## 3. Conclusión

(pendiente de la medición)

═══ FIRMA ═══ 08-caparazon / 160926
