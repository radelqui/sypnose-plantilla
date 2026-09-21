# PLAN-CS-T06/R2 — Invariante de verificación independiente tras D7c: texto dictado por el lead

Versión 1 · 21-sep-2026 · autor: 00-lead · origen: compuerta D7c (evento 25013), restauración de T06/R1 (Requerimientos/F1/restauracion-requisitos.md) y medida del lead de hoy sobre el registro vivo.

## Por qué hace falta

T06/R1 se restauró a su texto original: "ninguna tarea pasa a espera_firma sin verificada_por distinto del agente ejecutor", con recuento igual a 0. Ese texto está congelado (la tarea 14 está firmada) y no se toca. Pero desde D7c el estado espera_firma significa "entregada, a la espera de veredicto", y en él verificada_por vacío es legítimo: el verificador lo rellena al juzgar y firmar.py exige entonces un verificador distinto del ejecutor respaldado por un evento verificado. Medido hoy, la comprobación literal de R1 da 9 (tareas 4, 5, 6, 7, 8, 71, 73, 75 y 76, todas entregadas y sin veredicto), así que R1 ya no mide el invariante. R1 queda como histórico y el invariante vigente es R2. No se ablanda nada: R2 mueve la exigencia al punto donde D7c la puso, la firma, y añade la mitad que R1 no cubría (verificador igual al ejecutor en espera_firma).

## R2

EARS:
Desde la compuerta D7c (evento 25013), ninguna tarea DEBE estar en progreso hecha sin verificada_por distinto de su agente ejecutor, y ninguna tarea en espera_firma DEBE tener verificada_por igual a su agente ejecutor.

Comprobación:
sqlite3 -readonly registry.db "SELECT COUNT(*) FROM tarea WHERE (progreso='hecha' AND (verificada_por IS NULL OR verificada_por=agente)) OR (progreso='espera_firma' AND verificada_por=agente)" → 0

Medida del lead hoy: 1. La tarea 41 (PLAN-CS-T09/R0, "Definir requisito y comprobación de la línea") está en hecha sin verificada_por. No se arregla escribiendo un verificador a mano: la tarea 41 se devuelve con nota, igual que la 38, porque la spec de T09 la escribe ahora 01-git-cicd en la tarea 81. Tras esa devolución el recuento debe dar 0, y ese es el examen.

## Tarea

Ninguna nueva: R2 lo examina el verificador Opus del lead dentro del veredicto de la tarea 83 (spec de T06 escrita por el rol 07, que debe contener R1 literal como histórico y R2 literal como vigente).
