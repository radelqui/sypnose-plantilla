# Fase D7b: D7 es por ROL — tareas de 07 las verifica un humano

## Origen

Decisión del lead, fechada 16-sep-2026: D7 ("quien ejecuta no juzga") es por ROL,
no por modelo. El mismo rol con otro modelo no es verificador independiente.

Caso concreto: tarea 14 de PLAN-CS-T06 (agente IA:07-verificador) fue verificada
por IA:07-verificador con un modelo diferente. Esto viola D7 porque el ROL es el mismo.

Regla del molde: las tareas cuyo agente es el rol 07-verificador las verifica un
HUMANO (H:carlos, por delegación del lead, con la comprobación ejecutada por el
lead y pegada en el detalle del evento).

## Cambios respecto a D7a

### Trigger SQL — compuerta_d7_verificador (REEMPLAZA D7a)

```sql
DROP TRIGGER IF EXISTS compuerta_d7_verificador;
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
  AND NEW.verificada_por NOT LIKE 'H:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:* o H:*');
END;
```

Acepta: `IA:07-verificador:*`, `H:*`, NULL.
Rechaza: cualquier otro actor (05, 03, 04, 01, etc.).

### Trigger SQL — compuerta_d7_auto_verificacion (NUEVO)

```sql
CREATE TRIGGER IF NOT EXISTS compuerta_d7_auto_verificacion
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por LIKE 'IA:07-verificador:%'
  AND OLD.agente LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7b compuerta: mismo rol 07 no puede auto-verificarse');
END;
```

Rechaza: tarea con agente 07 verificada por 07 (cualquier modelo).
Acepta: tarea con agente 07 verificada por H:* (humano).

### Barrera Python (barrera.py)

- `verificar_d7_verificador(conn, verificador)`: ahora acepta `H:*` (humano registrado
  en tabla actor con clase='humano') además de `IA:07-verificador:*` (ratificado).
- `verificar_d7_auto_verificacion(conn, tarea_id, verificador)`: NUEVA. Si el agente
  de la tarea es `IA:07-verificador:*` y el verificador también, sys.exit.

## Tests

Script de prueba: `plantilla/compuerta_d7b.py --db ~/sypnose-f1/registry.db`

| # | Test | Esperado |
|---|------|----------|
| 1 | trigger rechaza verificada_por=05-arquitecto | rechazar |
| 2 | trigger rechaza verificada_por=03-datos-rag | rechazar |
| 3 | trigger rechaza verificada_por=01-git-cicd | rechazar |
| 4 | trigger rechaza verificada_por=04-agentes | rechazar |
| 5 | trigger acepta verificada_por=07 opus-4-6 (agente no-07) | aceptar |
| 6 | trigger acepta verificada_por=07 opus-5 (agente no-07) | aceptar |
| 7 | trigger acepta verificada_por=H:carlos | aceptar |
| 8 | trigger acepta verificada_por=H:lead | aceptar |
| 9 | trigger acepta verificada_por=NULL | aceptar |
| 10 | **trigger rechaza agente-07 + verificada_por-07 (mismo modelo)** | rechazar |
| 11 | **trigger rechaza agente-07 + verificada_por-07 (modelo diferente)** | rechazar |
| 12 | trigger acepta agente-07 + verificada_por=H:carlos | aceptar |
| 13 | barrera acepta H:carlos como verificador | aceptar |
| 14 | barrera rechaza 05 como verificador | rechazar |
| 15 | barrera acepta 07 ratificado como verificador | aceptar |
| 16 | barrera rechaza auto-verificación 07→07 (mismo modelo) | rechazar |
| 17 | barrera rechaza auto-verificación 07→07 (modelo diferente) | rechazar |
| 18 | barrera acepta verificación humana de tarea-07 | aceptar |
| 19 | barrera acepta 07 como verificador de tarea no-07 | aceptar |
| 20 | barrera rechaza entrega por actor ≠ agente | rechazar |

## Vuelta atrás (restaura D7a)

```sql
DROP TRIGGER IF EXISTS compuerta_d7_verificador;
DROP TRIGGER IF EXISTS compuerta_d7_auto_verificacion;
CREATE TRIGGER IF NOT EXISTS compuerta_d7_verificador
BEFORE UPDATE OF verificada_por ON tarea
WHEN NEW.verificada_por IS NOT NULL
  AND NEW.verificada_por NOT LIKE 'IA:07-verificador:%'
BEGIN
  SELECT RAISE(ABORT, 'D7 compuerta: verificada_por debe ser IA:07-verificador:*');
END;
```

## Ejecución

1. 07 examina esta fase y da CUMPLE
2. Lead ejecuta ambos triggers SQL en producción (registro vivo)
3. Lead re-verifica tarea 14 de PLAN-CS-T06 como H:carlos por delegación
