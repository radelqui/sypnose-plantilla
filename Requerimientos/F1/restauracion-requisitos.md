# Restauración de requisitos ablandados — orden del lead

Versión 1 · 21-sep-2026 · autor: 00-lead · origen: re-juicio retroactivo con el examen ORIGINAL (eventos 24978, 24979, 24981, 24983, 24984, 24986, 24987, 24990; secciones #tareaNN-retro de 07-verificador/VERIFICACION.md) y 07-verificador/AUDITORIA-R0-ROLES.md.

Resultado del re-juicio: 7 de 8 trabajos pasan TAMBIÉN el examen original, así que el ablandamiento fue innecesario y el original se restaura. 1 de 8 no pasa (M5/R1, tarea 63).

Regla: el arquitecto actúa como OPERADOR. El texto a restaurar es el literal de los campos "VIEJO ears" y "VIEJO comprobacion" del evento que lo sustituyó; no se redacta nada nuevo. Cada restauración deja un evento requisito_restaurado con: texto vigente antes, texto restaurado, evento de origen, evento del re-juicio que lo respalda y la frase "aprobado por 00-lead, Requerimientos/F1/restauracion-requisitos.md". El texto que hoy está vigente no se pierde: pasa a un requisito adicional R2 del mismo plan cuando se indica, porque también pasa y aporta cobertura.

| Requisito | Restaurar desde | Re-juicio | Qué hacer con el texto vigente |
|---|---|---|---|
| PLAN-CS-T06/R1 | campos VIEJO del evento 23018 (invariante: ninguna tarea en espera_firma sin verificada_por distinto del ejecutor; COUNT = 0) | 24978 CUMPLE | Se elimina como comprobación: el contador `LIKE '%CUMPLE%'` cuenta también los "NO CUMPLE" (46 de 169) y no puede fallar. No pasa a R2. |
| PLAN-CS-T07/R1 | campos VIEJO del evento 23169 (`gh run list --branch main --limit 1` + `gh run view <id>` con el job deploy en waiting) | 24979 CUMPLE | Se elimina: un run histórico fijo no examina el pipeline de hoy. |
| PLAN-CS-T08/R1 | campos VIEJO del evento 22864 (examen de ejecución contra PostgreSQL con pgvector), con la única enmienda que recomienda el verificador: la precondición de sembrar volumen que le faltaba | 24981 CUMPLE | Pasa a R2 (validación estática del esquema, 20 comprobaciones). |
| PLAN-CS-T03/R1 | campos VIEJO del evento 22941; comprobación final = `pytest tests/test_api.py tests/test_identity.py` sin `-k` (superconjunto de la original y de la vigente, 15 tests, en verde hoy) | 24984 CUMPLE | Absorbido por el superconjunto; no hace falta R2. |
| PLAN-CS-T05/R1 | campos VIEJO del evento 22925 | 24983 CUMPLE | Pasa a R2 (PII). |
| PLAN-CS-T10/R1 | campos VIEJO del evento 22909 | 24987 CUMPLE | Pasa a R2. |
| PLAN-CS-M2/R0 y R1 | texto de specs/M2/spec.md @7a4f4b4, el que cita la firma 23472 (cargas 23470/23471): vuelve la cláusula `docker build .`; R1 con comprobación separada de la de R0 | 24990 CUMPLE | Se conserva solo lo que exige el bloqueo técnico del cerco, documentado. |
| PLAN-CS-T09/R1 | NO se restaura sin más: el original (igualdad trailers = commits) falla hoy (304 frente a 320). Requisito nuevo escrito por 01-git-cicd, no por el ejecutor: desde el commit de corte en que se instaló el hook commit-msg, el 100 % de los commits lleva los tres trailers (igualdad); los anteriores se listan como deuda histórica, sin reescribir la historia | 24966 NO CUMPLE | La tarea 17 se devuelve. |
| PLAN-CS-T06/R0 | La spec de T06 la escribe el rol 07 (verificador Opus del lead, commit en el worktree de 07 con trailer Chat: 07-verificador) | 24967 NO CUMPLE | La tarea 38 se devuelve. |
| PLAN-CS-M5/R1 | campos VIEJO del evento 24248: `docker compose -f microservicio/demo/docker-compose.demo.yml config --quiet`, que el VERIFICADOR ejecuta en el 67 sobre clon limpio del repo público | 24986 NO CUMPLE: el fichero no existe en ninguna rama pública | La tarea 63 se devuelve: 01 publica el compose y el README en main de radelqui/sypnose-plantilla. La comprobación de PC (`python microservicio/demo/comprobar_compose.py`) queda como R2 para la entrega por el caparazón; el veredicto exige además R1 ejecutado por el verificador en el 67. |

Tareas 13 y 18 (CUMPLE y firma sin evento tarea_entregada): no se fabrica una entrega con fecha antigua. Se deja un evento nota_lead que lo declara y cita los re-juicios 24983 y 24987 como veredicto válido de hoy sobre clon limpio.

Orden de ejecución: primero T06/R1, T07/R1, T03/R1, T05/R1, T10/R1, T08/R1 y M2 (no cambian ningún estado público porque pasan); después las devoluciones de 17, 38 y 63 con nota. Todo con backup por sqlite3 .backup y sin UPDATE ni DELETE sobre evento ni evidencia.
