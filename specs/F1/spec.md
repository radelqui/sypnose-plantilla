═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-4-6) / TO: 00-lead · 07-verificador / KEY: spec-f1-railes-integridad-210926

# Spec PLAN-CS-F1 — Raíles deterministas de integridad de requisitos

Origen: 07-verificador/AUDITORIA-R0-ROLES.md (21-sep-2026), tablas A y B.
Contrato: Requerimientos/F1/requisitos-dictados.md (lead, v1, 21-sep-2026).
Herramienta: plantilla/compuerta_f1.py. Trabaja solo sobre COPIA del registro (sqlite3 .backup).

## RAÍL 1 — Autoría R0: la spec la escribe el rol que nombra el EARS

EARS:
Cuando compuerta_f1.py --verificar r1 examine un plan con tarea R0, DEBE comprobar que: (a) existe al menos un requisito con ref≠'R0' en ese plan; (b) el fichero de spec citado en el evento requisito_cargado o spec_cargada existe en el repositorio; (c) el trailer Chat: del commit que creó o modificó por última vez ese fichero coincide con el rol nombrado en el texto EARS del R0 de ese plan; (d) la ruta de la spec corresponde a la sigla de la línea del plan. Si cualquier condición falla, el raíl nombra la violación con plan, ref y motivo.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --verificar r1

Violaciones existentes que debe detectar: T05 (rol EARS=01-git-cicd, autor=02-backend-api), T06 (EARS=07-verificador, autor=05-arquitecto), T10 (EARS=04-agentes, autor=02-backend-api), T12 (sin artefacto), CS2-M/56 (sin spec.md), CS2-U/66 (spec citada no existe), T11 (spec de T13).

## RAÍL 2 — El examinado no reescribe su examen

EARS:
Cuando un actor intente modificar los campos ears o comprobacion de un requisito, y el rol de ese actor (por campo actor) o el rol del autor interpuesto (por campo autor: del detalle del evento de modificación) coincida con el rol del agente de alguna tarea abierta (progreso NOT IN ('hecha','retirada')) que ese requisito examina, el registro DEBE rechazar la escritura con RAISE(ABORT). Implementación: TRIGGER BEFORE UPDATE OF ears, comprobacion ON requisito, con tabla sesion_actual(actor TEXT, autor TEXT) poblada por el script antes de cada operación. La función de extracción de rol separa el segundo segmento de 'IA:rol:modelo' y el segundo de 'H:nombre'.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r2

Ataque positivo: el arquitecto (05) modifica un requisito cuyo agente es 02 → pasa.
Ataque negativo: el ejecutor (02) intenta modificar su propio requisito → RAISE(ABORT).

## RAÍL 3 — Detector de ablandamiento con aprobación

EARS:
Cuando se modifique un requisito (UPDATE de ears o comprobacion), el evento de registro DEBE contener los campos 'antes:' y 'despues:' con el texto literal del campo modificado, y 'ablanda:' con valor si, no o neutro. Cuando ablanda=si, DEBE existir un evento previo ablandamiento_autorizado para ese (plan_id, ref) con actor humano (H:*) o lead, que sea distinto del actor que realiza el cambio y distinto del rol autor del cambio. Si el evento de modificación carece de la clasificación ablanda: o carece de antes:/despues:, compuerta_f1.py --verificar r3 nombra la violación. Implementación: verificación post-hoc (no trigger) porque requiere comparar texto libre del detalle.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --verificar r3

Violaciones existentes que debe detectar: los 10 casos de la tabla B de la auditoría (T06/R1, T08/R1, T05/R1, T10/R1, T07/R1, T09/R1, T03/R1, M5/R1, M2/R0-R1, 0001/R1).

## RAÍL 4 — Requisito firmado congelado

EARS:
Cuando exista al menos una tarea con progreso='hecha' que referencie un (plan_id, req_ref), el registro DEBE rechazar cualquier UPDATE de ears o comprobacion en ese requisito. Implementación: TRIGGER BEFORE UPDATE OF ears, comprobacion ON requisito que consulta la tabla tarea.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r4

Ataque positivo: modificar un requisito sin tarea firmada → pasa.
Ataque negativo: modificar un requisito con tarea hecha → RAISE(ABORT).
Violación existente: M2/R0 reescrito 19 min después de la firma (ev 23653, tarea 52 ya hecha).

## RAÍL 5 — Ventana mínima entre modificación y entrega

EARS:
Cuando se intente insertar un evento con accion='tarea_entregada' para una tarea cuyo requisito haya sido modificado en los últimos 30 minutos por un evento con ablanda=si o sin campo ablanda: en el detalle, el sistema DEBE rechazar la inserción o nombrar la violación. Los cambios clasificados ablanda=neutro quedan exentos de la ventana. Implementación: verificación post-hoc en compuerta_f1.py --verificar r5, o TRIGGER BEFORE INSERT ON evento WHEN NEW.accion='tarea_entregada' si la tabla de eventos tiene el campo ablanda: parseado.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r5

Ataque positivo: entrega 31 min después de modificación ablanda=si → pasa.
Ataque negativo: entrega 12 s después de modificación ablanda=si → bloquea.
Violaciones existentes: T06/R1 (12 s), T09/R1 (3 m 41 s), T03/R1 (27 m), M4/R0 (6 s), M5/R0 (11 s), CS2-U (4 m 29 s).

## RAÍL 6 — Sin entrega no hay veredicto

EARS:
Cuando se intente insertar un evento con accion='verificado' para una tarea, y no exista un evento previo con accion='tarea_entregada' para esa misma tarea (identificada por 'tarea N' en el detalle del evento), el registro DEBE rechazar la inserción con RAISE(ABORT). Implementación: TRIGGER BEFORE INSERT ON evento WHEN NEW.accion='verificado', con tabla sesion_actual(tarea_id INTEGER) poblada por el script antes de la operación. El trigger consulta la existencia de tarea_entregada con el mismo plan_id y tarea_id.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r6

Ataque positivo: verificado de una tarea con tarea_entregada previa → pasa.
Ataque negativo: verificado de una tarea sin tarea_entregada → RAISE(ABORT).
Violaciones existentes: tareas 13 y 18 con veredicto CUMPLE sin tarea_entregada.

## RAÍL 7 — Eliminar --delegado

EARS:
El flag --delegado NO DEBE existir como argumento de argparse en cargar_requisito.py ni en ningún otro script Python de la plantilla. grep -rn -- '--delegado' sobre el directorio plantilla/ DEBE devolver exactamente 0 líneas. compuerta_f1.py --verificar r7 confirma que no hay ocurrencias.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r7

Ataque positivo: grep sobre plantilla sin --delegado → pasa (0 líneas).
Ataque negativo: grep sobre copia con --delegado inyectado → bloquea (≥1 línea).

═══ FIRMA ═══ 08-caparazon / 260921
