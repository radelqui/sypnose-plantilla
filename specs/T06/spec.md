═══ EMISOR ═══ FROM: IA:07-verificador:claude-opus-5 / TO: 00-lead · H:carlos / KEY: spec-t06-code-reviews-210926

# Spec PLAN-CS-T06 — Code reviews y verificación independiente

Línea T06 de la oferta: *"Participate in code reviews and development best practices"*.
Rol dueño de la línea: **07-verificador**. Fecha: 21-sep-2026.

## Por qué se reescribe esta spec

La spec anterior de T06 la escribió el arquitecto (commit `5bd9843`, 15-sep 21:21:31Z, trailer
`Chat: 05-arquitecto-sypnose`) para una línea cuyo rol es el 07. El examen no lo escribe el examinado
ni un tercero interpuesto. El re-juicio retroactivo del 21-sep (evento **24967**) declaró **NO CUMPLE**
la tarea 38 (T06/R0) y la devolvió; `Requerimientos/F1/restauracion-requisitos.md` ordenó que la spec
de T06 la escriba el rol 07 con trailer `Chat: 07-verificador`. Este fichero es la ejecución de la
**tarea 83** (PLAN-CS-F2/R4). No se inventa ningún requisito: R0 y R1 se copian literales del registro
y R2 literal del texto dictado por el lead.

## R0

EARS (literal del registro):
> Antes de escribir código para esta línea, el rol 07-verificador DEBE registrar el requisito comprobable de su solución (R1+) con su comprobación ejecutable

Comprobación (literal del registro):
```
SELECT COUNT(*) FROM requisito WHERE plan_id='PLAN-CS-T06' AND ref<>'R0' → ≥1
```

## R1 (histórico desde D7c)

EARS (literal del registro):
> Ninguna tarea DEBE pasar a espera_firma sin verificada_por distinto del agente ejecutor.

Comprobación (literal del registro):
```
SELECT COUNT(*) FROM tarea WHERE progreso='espera_firma' AND (verificada_por IS NULL OR verificada_por=agente) → 0
```

**Nota honesta.** Este es el invariante original, restaurado tras el re-juicio **24978** (CUMPLE), que
midió el trabajo con el examen que el evento 23018 había borrado. Desde entonces cambió el significado
del estado: la compuerta **D7c** (evento **25013**, 21-sep 10:09:14Z) define `espera_firma` como
"entregada, a la espera de veredicto", y en ese estado `verificada_por` vacío es legítimo — lo rellena
el verificador al juzgar, y `firmar.py` exige entonces un verificador distinto del ejecutor respaldado
por un evento `verificado`. Por eso la comprobación literal de R1 ya no mide el invariante.

Medida ejecutada hoy (21-sep-2026) por el rol 07 sobre el registro vivo en solo lectura:

```
$ ssh ... 'sqlite3 -readonly ~/sypnose-f1/registry.db \
    "SELECT COUNT(*) FROM tarea WHERE progreso='\''espera_firma'\'' AND (verificada_por IS NULL OR verificada_por=agente)"'
9
```

**9**, no 0. Son las tareas **4, 5, 6, 7, 8, 71, 73, 75 y 76**: todas entregadas y sin veredicto, ninguna
en violación de D7. El re-juicio 24978 dio CUMPLE **antes** de D7c, cuando el recuento sí medía lo que el
EARS dice. R1 está congelado (la tarea 14 está firmada) y **no se toca**: queda como histórico, y el
invariante vigente es R2.

**Lo que NO es la comprobación de R1.** El contador de eventos `... WHERE detalle LIKE '%CUMPLE%' AND
actor LIKE 'IA:07%' → ≥5` que el evento 23018 puso en su lugar queda eliminado y no vuelve: cuenta
también los "NO CUMPLE" (46 de 169 en la auditoría), crece con cada veredicto y por construcción no
puede fallar nunca. Un examen que no puede suspender no es un examen.

## R2 (vigente)

Texto dictado por el lead en `Requerimientos/F2/t06-r2-dictado.md`
(sha256 `9d2a007633c3db0987b4aba0b7b03bf3839a61c12747744c25f88bef1d0c7826`, verificado antes de citarlo).

EARS (literal):
> Desde la compuerta D7c (evento 25013), ninguna tarea DEBE estar en progreso hecha sin verificada_por distinto de su agente ejecutor, y ninguna tarea en espera_firma DEBE tener verificada_por igual a su agente ejecutor.

Comprobación (literal):
```
sqlite3 -readonly registry.db "SELECT COUNT(*) FROM tarea WHERE (progreso='hecha' AND (verificada_por IS NULL OR verificada_por=agente)) OR (progreso='espera_firma' AND verificada_por=agente)" → 0
```

Medida ejecutada hoy (21-sep-2026) por el rol 07 sobre el registro vivo en solo lectura:

```
1
```

**1, no 0: el requisito NO pasa hoy.** La única fila que cuenta es la tarea **41** (PLAN-CS-T09/R0,
"Definir requisito y comprobación de la línea"), en `hecha` con `verificada_por` vacío y agente
`IA:05-arquitecto-sypnose:claude-opus-4-6`. No se arregla escribiendo un verificador a mano: la tarea 41
se devuelve con nota, igual que la 38, porque la spec de T09 la escribe ahora 01-git-cicd en la tarea 81.
El examen exige **0 tras esa devolución**, y hasta entonces R2 está en NO CUMPLE. Queda escrito así a
propósito: maquillar el número sería repetir exactamente lo que el re-juicio castigó.

R2 mueve la exigencia al punto donde D7c la puso —la firma— y añade la mitad que R1 no cubría:
verificador igual al ejecutor en `espera_firma`. No ablanda nada.

## Cómo juzga el rol 07

1. Sobre clon limpio del repositorio o copia del registro por `sqlite3 .backup`; nunca sobre el árbol de trabajo del ejecutor.
2. Ejecuta él mismo la comprobación **literal** del requisito y pega la salida real; la salida que pegó el ejecutor no es prueba, es una afirmación a refutar.
3. Añade ataques propios: si el examen no puede suspender (contadores monótonos, ids congelados, `-k` que deselecciona, `grep` donde antes había ejecución), el veredicto es NO CUMPLE aunque el número salga.
4. Escribe solo con `INSERT` en `evento` (y `evidencia`); nunca `UPDATE` ni `DELETE` sobre el registro. El cambio de estado de la tarea lo hace el operador, y la firma la pone el humano.
5. Quien ejecuta no juzga (D7). Extensión D7/D7b: el rol 07 tampoco verifica tareas del rol 07 — esta misma tarea 83 la juzga **H:carlos** por delegación, no su autor.

═══ FIRMA ═══ IA:07-verificador:claude-opus-5 / 260921
