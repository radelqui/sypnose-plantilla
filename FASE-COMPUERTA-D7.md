# Fase con compuerta: D7 verificada_por + tarea_entregada

## Origen

Incidente D7 (16-sep-2026): actor IA:05-arquitecto-sypnose entregó tareas 34, 39, 40, 44
(agentes 01-git-cicd, 03-datos-rag, 04-agentes) y escribió verificada_por con su propio ID.
Violación de D7 ("quien ejecuta no juzga") y de la regla de que solo el agente de la tarea
entrega su trabajo. Documentado en notas_arquitecto eventos 23182 y 23238.

## Compuerta: dos capas

### Capa 1 — Trigger SQL (enforcement en el registro)

```sql
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:*');
END;
```

Acepta: `IA:07-verificador:claude-opus-4-6`, `IA:07-verificador:claude-opus-5`, NULL (reset).
Rechaza: cualquier otro actor (05, 03, 04, 01, etc.).

### Capa 2 — Barrera Python (enforcement en scripts)

En `barrera.py` (commit daf60a4):

- `verificar_d7_entrega(conn, tarea_id, actor)`: compara carpeta del actor ejecutor
  con carpeta del agente de la tarea. Si no coinciden → sys.exit.
- `verificar_d7_verificador(conn, verificador)`: verifica que el verificador es
  `IA:07-verificador:*` y está ratificado (actor_ratificado por humano o 07 válido).

Importadas por `entregar_tarea.py`. El caparazón (`stop.py`) ejecuta como el agente
de la tarea, así que pasa la compuerta por diseño.

## Tests (20/20 sobre copia)

| # | Test | Resultado |
|---|------|-----------|
| 1 | trigger rechaza verificada_por=05-arquitecto | OK |
| 2 | trigger rechaza verificada_por=03-datos-rag | OK |
| 3 | trigger rechaza verificada_por=01-git-cicd | OK |
| 4 | trigger rechaza verificada_por=04-agentes | OK |
| 5 | trigger acepta verificada_por=07 opus-4-6 | OK |
| 6 | trigger acepta verificada_por=07 opus-5 | OK |
| 7 | trigger acepta verificada_por=NULL | OK |
| 8 | replay 23170: 05 como verificador de tarea 39 (agente=01) | rechazado OK |
| 9 | replay 2317x: 05 como verificador de tarea 34 (agente=04) | rechazado OK |
| 10 | replay 2317x: 05 como verificador de tarea 40 (agente=03) | rechazado OK |
| 11 | replay 2317x: 05 como verificador de tarea 44 (agente=04) | rechazado OK |
| 12 | extraer_carpeta 05 | OK |
| 13 | extraer_carpeta 03 | OK |
| 14 | extraer_carpeta 07 | OK |
| 15 | barrera rechaza entrega de T07 (agente=01) por actor 05 | OK |
| 16 | barrera rechaza entrega de tarea 34 (agente=04) por actor 05 | OK |
| 17 | barrera rechaza entrega de tarea 40 (agente=03) por actor 05 | OK |
| 18 | barrera rechaza entrega de tarea 44 (agente=04) por actor 05 | OK |
| 19 | barrera rechaza 05 como verificador | OK |
| 20 | barrera acepta 07 ratificado como verificador | OK |

Script de prueba: `plantilla/compuerta_d7.py --db ~/sypnose-f1/registry.db`

## Vuelta atrás

```sql
DROP TRIGGER IF EXISTS compuerta_d7_verificador;
```

La barrera Python no necesita vuelta atrás: se puede revertir el commit daf60a4
si fuera necesario, pero las funciones solo añaden validación sin cambiar datos.

## Ejecución

1. 07 examina esta fase y da CUMPLE
2. Lead ejecuta el trigger SQL en producción (registro vivo)
3. 07 re-verifica tareas 34, 39, 40, 44 (notas_arquitecto 23182, 23238)

## Ficheros modificados (commit daf60a4)

- `barrera.py`: +extraer_carpeta(), +verificar_d7_entrega(), +verificar_d7_verificador()
- `entregar_tarea.py`: usa funciones centralizadas de barrera.py
- `compuerta_d7.py`: script de migración y test (nuevo)
