# T06 — Participate in code reviews and development best practices

## Oferta (línea 6, literal de `oferta-coforge.txt`)

> Participate in code reviews and development best practices

## Solución

La plantilla SYPNOSE implementa code review por diseño:

- **D7 — quien ejecuta no juzga**: un trigger en la tabla `tarea` impide que
  `verificada_por` sea igual a `agente`. Ninguna tarea puede pasar a
  `espera_firma` sin un verificador distinto del ejecutor.
- **07-verificador**: actor dedicado a la verificación. Ejecuta la comprobación
  EARS de cada tarea R1, emite veredicto CUMPLE/NO CUMPLE y registra evento.
- **Registro inmutable**: los eventos de verificación (tarea_entregada con
  CUMPLE en detalle) quedan registrados en la tabla `evento`, solo INSERT.
- **Firmas separadas**: la firma humana (firma_tarea, firma_humana) requiere
  que la tarea esté en espera_firma con verificada_por ≠ agente.

## R1 — Verificación independiente de cada tarea

**EARS:**
> Ninguna tarea DEBE pasar a espera_firma sin verificada_por distinto del
> agente ejecutor (D7). Los actores 07-verificador DEBEN haber emitido al
> menos 5 eventos con veredicto CUMPLE registrados en la tabla evento del
> registro SYPNOSE.

**Comprobación (determinista, sobre el registro)**

```bash
sqlite3 ~/sypnose-f1/registry.db "SELECT COUNT(*) FROM evento WHERE detalle LIKE '%CUMPLE%' AND actor LIKE 'IA:07%'" → ≥5
```
