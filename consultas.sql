-- Consultas del molde sobre planes, evidencias y actores (registro SYPNOSE, sqlite3 registry.db).
-- No son vista_guardada: las vistas guardadas de la consola solo filtran la rejilla de nodos
-- (limitación anotada para la fase de SYPNOSE). Decisión 00-lead 14-sep.
-- Uso: sqlite3 -header ~/sypnose-f1/registry.db < consultas.sql

-- 1. Oferta contestada: cada línea T-xx de cada instancia con su tarea y sus evidencias.
.print '== Oferta contestada =='
SELECT p.id AS plan,
       p.que,
       t.progreso,
       t.agente,
       t.verificada_por,
       (SELECT COUNT(*) FROM evidencia e WHERE e.plan_id = p.id
          AND e.fuente NOT LIKE 'bloqueo:%' AND e.dice NOT LIKE 'PARCIAL%')              AS evidencias_que_cubren,
       (SELECT COUNT(*) FROM evidencia e WHERE e.plan_id = p.id AND e.fuente LIKE 'bloqueo:%') AS bloqueos,
       (SELECT group_concat(e.fuente, ' | ') FROM evidencia e WHERE e.plan_id = p.id)    AS fuentes
FROM plan p
LEFT JOIN tarea t ON t.plan_id = p.id AND t.req_ref = 'R1'
WHERE p.id LIKE 'PLAN-%-T%'
ORDER BY p.id;

-- 2. Pruebas de bloqueo (decisión b): cada bloqueo deja evidencia 'bloqueo:<tipo>' en su plan, además del evento.
.print '== Pruebas de bloqueo: evidencias =='
SELECT e.plan_id, e.fuente, e.dice
FROM evidencia e
WHERE e.fuente LIKE 'bloqueo:%'
ORDER BY e.plan_id, e.fuente;

.print '== Pruebas de bloqueo: eventos (traza) =='
SELECT v.id, v.cuando, v.actor, v.accion, v.plan_id, v.detalle
FROM evento v
WHERE v.accion LIKE 'bloqueo:%'
ORDER BY v.id;

-- 3. Actores y modelos: quién es cada IA, qué ejecuta y qué verifica.
.print '== Actores y modelos =='
SELECT a.id,
       a.rol,
       a.modelo,
       (SELECT COUNT(*) FROM tarea t WHERE t.agente = a.id)         AS tareas_asignadas,
       (SELECT COUNT(*) FROM tarea t WHERE t.verificada_por = a.id) AS tareas_verificadas
FROM actor a
WHERE a.clase = 'ia'
ORDER BY a.rol, a.modelo;
