═══ EMISOR ═══ FROM: 08-caparazon (claude-opus-4-6) / TO: 00-lead · 07-verificador / KEY: spec-f1-railes-integridad-210926

# Spec PLAN-CS-F1 — Raíles deterministas de integridad de requisitos

Origen: 07-verificador/AUDITORIA-R0-ROLES.md (21-sep-2026), tablas A y B.
Contrato: Requerimientos/F1/requisitos-dictados.md (lead, v2, 21-sep-2026).
Herramienta: plantilla/compuerta_f1.py. Trabaja solo sobre COPIA del registro (sqlite3 .backup).

## RAÍL 1 — Autoría R0: la spec la escribe el rol que nombra el EARS

EARS:
Cuando compuerta_f1.py --verificar r1 examine un plan con tarea R0, DEBE comprobar que: (a) existe al menos un requisito con ref≠'R0' en ese plan; (b) el fichero de spec citado en el evento requisito_cargado o spec_cargada existe en el repositorio; (c) el trailer Chat: del commit que creó o modificó por última vez ese fichero coincide con el rol nombrado en el texto EARS del R0 de ese plan; (d) la ruta de la spec corresponde a la sigla de la línea del plan. Si cualquier condición falla, el raíl nombra la violación con plan, ref y motivo.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --verificar r1

Violaciones existentes que debe detectar: T05 (rol EARS=01-git-cicd, autor=02-backend-api), T06 (EARS=07-verificador, autor=05-arquitecto), T10 (EARS=04-agentes, autor=02-backend-api), T12 (sin artefacto), CS2-M/56 (sin spec.md), CS2-U/66 (spec citada no existe), T11 (spec de T13).

## RAÍL 2 — El examinado no reescribe su examen

Lo que el raíl IMPIDE (trigger BEFORE UPDATE):
El trigger f1_r2_examinado_no_reescribe bloquea un UPDATE de ears o comprobacion en requisito cuando existen tareas abiertas para ese requisito Y no existe un evento cambio_requisito_aprobado vigente que cumpla estas cuatro condiciones: (a) actor humano (H:*) o lead (IA:00-lead:*); (b) detalle contiene la ref del requisito; (c) detalle contiene fichero=<ruta> y sha256=<64 hex> (formato obligatorio); (d) el evento es posterior al último requisito_modificado para esa ref (consumo: una aprobación vale para un solo cambio); (e) el evento tiene menos de 24 horas de antigüedad.

Lo que el raíl DETECTA (--verificar r2, post-hoc):
La verificación post-hoc comprueba que el actor o autor del evento de modificación no coincide con el agente de las tareas que ese requisito examina.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r2

Ataques: R2+ aprobación válida con fichero= sha256= → pasa; R2- aprobación consumida (segundo UPDATE) → ABORT; R2- sin aprobación → ABORT; R2- formato sin fichero= sha256= → ABORT; R2- aprobación expirada (>24h) → ABORT; R2- aprobación de IA no-lead → ABORT.

## RAÍL 3 — Detector de ablandamiento con aprobación

EARS:
Cuando se modifique un requisito (UPDATE de ears o comprobacion), el evento de registro DEBE contener los campos 'antes:' y 'despues:' con el texto literal del campo modificado, y 'ablanda:' con valor si, no o neutro. Cuando ablanda=si, DEBE existir un evento previo ablandamiento_autorizado para ese (plan_id, ref) con actor humano (H:*) o lead, que sea distinto del actor que realiza el cambio y distinto del rol autor del cambio. Si el evento de modificación carece de la clasificación ablanda: o carece de antes:/despues:, compuerta_f1.py --verificar r3 nombra la violación. Implementación: verificación post-hoc (no trigger) porque requiere comparar texto libre del detalle.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --verificar r3

Violaciones existentes que debe detectar: los 10 casos de la tabla B de la auditoría (T06/R1, T08/R1, T05/R1, T10/R1, T07/R1, T09/R1, T03/R1, M5/R1, M2/R0-R1, 0001/R1).

## RAÍL 4 — Requisito firmado congelado

EARS:
Cuando exista al menos una tarea con progreso='hecha' que referencie un (plan_id, req_ref), el registro DEBE rechazar cualquier UPDATE de ears o comprobacion en ese requisito. Implementación: TRIGGER BEFORE UPDATE OF ears, comprobacion ON requisito que consulta la tabla tarea y la existencia de firma_tarea.

R4b: DELETE de un requisito con tareas asignadas → RAISE(ABORT).

R4c (evasión F3/F4): un UPDATE de req_ref o plan_id en tarea se bloquea cuando esa tarea tiene al menos un evento tarea_entregada o firma_tarea. Impide pivotar una tarea firmada a un requisito diferente para luego modificar el original desbloqueado.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r4

Ataques: R4+ sin firma → pasa; R4- con firma → ABORT; R4- evasión por downgrade progreso → ABORT; R4b- DELETE con tareas → ABORT; R4c- cambiar req_ref firmada → ABORT; R4c+ cambiar req_ref sin firma ni entrega → pasa.

## RAÍL 5 — Ventana mínima entre modificación y entrega

EARS:
Cuando se intente insertar un evento con accion='tarea_entregada' para una tarea cuyo requisito haya sido modificado en los últimos 30 minutos por un evento con ablanda=si o sin campo ablanda: en el detalle, el sistema DEBE rechazar la inserción o nombrar la violación. Los cambios clasificados ablanda=neutro quedan exentos de la ventana. Implementación: verificación post-hoc en compuerta_f1.py --verificar r5, o TRIGGER BEFORE INSERT ON evento WHEN NEW.accion='tarea_entregada' si la tabla de eventos tiene el campo ablanda: parseado.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r5

Ataque positivo: entrega 31 min después de modificación ablanda=si → pasa.
Ataque negativo: entrega 12 s después de modificación ablanda=si → bloquea.
Violaciones existentes: T06/R1 (12 s), T09/R1 (3 m 41 s), T03/R1 (27 m), M4/R0 (6 s), M5/R0 (11 s), CS2-U (4 m 29 s).

## RAÍL 6 — Sin entrega no hay veredicto

Alcance: solo gobierna eventos verificado cuyo detalle empieza por "tarea N" (N entero, con espacio o dos puntos). Cualquier otro veredicto (vistas, mediciones, planes) queda FUERA del raíl y pasa libremente (PRINCIPIO 2: no romper el molde).

EARS:
Cuando se intente insertar un evento con accion='verificado' cuyo detalle siga el formato "tarea N" (N dígito), y no exista un evento previo con accion='tarea_entregada' para esa misma tarea, el registro DEBE rechazar la inserción con RAISE(ABORT). Implementación: TRIGGER BEFORE INSERT ON evento con WHEN que filtra por formato "tarea N".

R6b: si el detalle sigue el formato "tarea N" pero la tarea no existe en ese plan o el plan_id es NULL, el registro DEBE rechazar con RAISE(ABORT).

Limitación conocida (F5): un detalle podría empezar por "tarea 79" pero contener el juicio de otra tarea en el cuerpo del texto. El script firmar.py ya ancla el formato, y el trigger solo parsea el número tras "tarea ". Se anota como límite aceptado.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r6

Ataques: R6- sin tarea_entregada → ABORT; R6+ con entrega previa → pasa; R6b- tarea inexistente → ABORT; R6b- plan_id NULL → ABORT; R6+ veredicto sin formato "tarea N" → pasa.

## RAÍL 7 — Eliminar --delegado

EARS:
El flag --delegado NO DEBE existir como argumento de argparse en cargar_requisito.py ni en ningún otro script Python de la plantilla. grep -rn -- '--delegado' sobre el directorio plantilla/ DEBE devolver exactamente 0 líneas. compuerta_f1.py --verificar r7 confirma que no hay ocurrencias.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r7

Ataque positivo: grep sobre plantilla sin --delegado → pasa (0 líneas).
Ataque negativo: grep sobre copia con --delegado inyectado → bloquea (≥1 línea).

## PRINCIPIO 3 — El rastro lo deja la base

Triggers AFTER INSERT y AFTER UPDATE OF ears, comprobacion en requisito insertan automáticamente un evento con el texto íntegro:

- f1_rastro_requisito_insertado (AFTER INSERT): accion='requisito_insertado', actor='S:registro', detalle con ref=, ears=, comprobacion= (texto completo del INSERT).
- f1_rastro_requisito_modificado (AFTER UPDATE): accion='requisito_modificado', actor='S:registro', detalle con ref=, antes_ears=, despues_ears=, antes_comprobacion=, despues_comprobacion= (texto ÍNTEGRO de OLD y NEW).

Estos eventos habilitan el consumo de aprobación en R2: un cambio_requisito_aprobado debe ser posterior al último requisito_modificado para esa ref.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar rastro

Ataques: RASTRO+ INSERT requisito genera evento requisito_insertado; RASTRO+ UPDATE requisito genera evento requisito_modificado.

## RAÍL 8 — Evidencia de solo inserción

EARS:
La tabla evidencia DEBE ser de solo inserción: cualquier UPDATE o DELETE sobre evidencia DEBE ser rechazado con RAISE(ABORT) por triggers BEFORE UPDATE y BEFORE DELETE. Invalidar una evidencia se hace añadiendo una fila marcadora con su evento autorizado, nunca borrando ni sobreescribiendo. Implementación: dos triggers (f1_r8_evidencia_inmutable_u, f1_r8_evidencia_inmutable_d) instalados por compuerta_f1.py --aplicar. Si la tabla evidencia no existe en el esquema, los triggers se omiten sin error.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar r8

Ataque positivo: INSERT en evidencia → pasa.
Ataque negativo (UPDATE): UPDATE evidencia → RAISE(ABORT).
Ataque negativo (DELETE): DELETE evidencia → RAISE(ABORT).

═══ FIRMA ═══ 08-caparazon / 260921
