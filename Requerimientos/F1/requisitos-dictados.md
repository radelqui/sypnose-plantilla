# PLAN-CS-F1 — Integridad de requisitos: texto dictado por el lead

Versión 2 · 21-sep-2026 (v1 sha256 12715e86...757c; v2 añade el raíl 8 y las lecciones del veredicto 25019) · autor: 00-lead (Fable, solo diseño) · origen: 07-verificador/AUDITORIA-R0-ROLES.md.
Este fichero es la fuente de los requisitos de PLAN-CS-F1. El arquitecto solo los carga, literal, sin tocar una coma. El verificador compara el texto registrado con este fichero (hash del fichero citado en el evento de apertura). Ejecutor: 08-caparazon. Juez: verificador Opus del lead. Compuerta en el vivo: el lead.

Plan: PLAN-CS-F1 · afecta: sol:coforge:sypnose-plantilla · dueño: H:carlos (por delegación registrada 22656/22676).

## R0 — Spec de los siete raíles

EARS:
El fichero specs/F1/spec.md DEBE existir en el repositorio de la plantilla, escrito por 08-caparazon (trailer Chat: 08-caparazon en el commit que lo crea), con una sección "## RAÍL n" para cada n de 1 a 7, y en cada sección un enunciado EARS y una línea "Comprobación:" con un comando ejecutable: (1) autoría R0: el trailer Chat: del commit de la spec coincide con el rol que nombra el EARS del R0 y el fichero de la spec existe en la ruta citada; (2) el examinado no reescribe su examen: un requisito no lo modifica ni el agente de una tarea abierta que ese requisito examina ni su rol autor interpuesto; (3) todo cambio de requisito deja un evento con el texto anterior y el posterior y la clasificación ablanda=si|no|neutro, y un cambio con ablanda=si exige una aprobación previa registrada de un actor humano o del lead, distinto del ejecutor y del autor; (4) un requisito con alguna tarea firmada queda congelado; (5) entre un cambio con ablanda=si o sin clasificar y la entrega de la tarea que examina pasan al menos 30 minutos (los cambios neutro quedan exentos); (6) sin evento tarea_entregada de una tarea no se admite un evento verificado de esa tarea; (7) el flag --delegado deja de existir en cargar_requisito.py y en cualquier otro script.

Comprobación:
grep -c "^## RAÍL [1-7]" specs/F1/spec.md

Salida esperada, literal: 7. El verificador exige igualdad, no "al menos".

## R1 — compuerta_f1.py con los siete raíles y sus ataques

EARS:
Cuando se ejecute python plantilla/compuerta_f1.py --db registro-copia.db --atacar sobre una copia del registro vivo hecha con sqlite3 .backup, el sistema DEBE: (a) trabajar solo sobre esa copia, sin escribir jamás en el registro vivo; (b) instalar como triggers los raíles que SQLite permite (al menos 2, 4 y 6) y como comprobaciones de script los demás; (c) ejecutar al menos 14 ataques, dos por raíl, uno que debe pasar y uno que debe bloquearse, e imprimir una línea por ataque con su resultado; (d) terminar con código 0 solo si los 14 o más ataques dan el resultado esperado, y con código distinto de 0 en cualquier otro caso. El modo --verificar DEBE recorrer el registro y nombrar, por raíl, las violaciones ya existentes, entre ellas las diez de la auditoría: PLAN-CS-T06/R1, PLAN-CS-T08/R1, PLAN-CS-T05/R1, PLAN-CS-T10/R1, PLAN-CS-T07/R1, PLAN-CS-T09/R1, PLAN-CS-T03/R1, PLAN-CS-M5/R1, PLAN-CS-M2/R0-R1 y PLAN-CS-0001/R1, y las tareas 13 y 18 con veredicto sin entrega. El modo --aplicar DEBE hacer backup con sqlite3 .backup, instalar los triggers, registrar un evento con el hash del esquema resultante y no modificar ninguna fila existente. Ningún otro trigger del esquema (C8, D4, D5, D7, D7b, D7c) cambia.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar

## Tareas

- Tarea R0: "Spec de los siete raíles de integridad de requisitos" · agente IA:08-caparazon:claude-opus-4-6.
- Tarea R1: "compuerta_f1.py: raíles, ataques, verificar y aplicar" · agente IA:08-caparazon:claude-opus-4-6 · bloqueada por la tarea R0.

## Reglas de este plan

- Estos requisitos no se modifican sin una versión nueva de este fichero escrita por el lead.
- El arquitecto abre el plan y carga los requisitos como operador; no es autor ni ejecutor.
- 08 no toca el registro vivo; todo sobre copia.
- El veredicto lo dan verificadores Opus lanzados por el lead; la compuerta --aplicar la ejecuta el lead tras CUMPLE.

## Versión 2 — añadidos tras el veredicto 25019 (tarea 79 NO CUMPLE)

R0 y R1 no cambian en lo ya dictado. Se añade, con el mismo ejecutor y el mismo juez:

**Raíl 8 (nuevo, entra en R1):** la tabla evidencia es de solo inserción por trigger (BEFORE UPDATE y BEFORE DELETE abortan), igual que evento; invalidar una evidencia sigue siendo añadir una fila marcadora con su evento autorizado.

**Principios obligatorios para todos los raíles (lecciones del veredicto):**
1. Ningún raíl depende de una tabla de sesión ni de que quien escribe se identifique: decide solo con hechos ya escritos en el registro (eventos de entrega, de firma, de aprobación).
2. Ningún raíl puede romper el molde: con los triggers puestos deben seguir funcionando abrir plan, cargar requisito nuevo, crear tarea, entregar, el INSERT directo del evento verificado que hacen los verificadores, firmar y cerrar plan.
3. El rastro lo deja la base: triggers AFTER INSERT y AFTER UPDATE sobre requisito insertan ellos mismos un evento con el texto íntegro anterior y posterior.
4. Cada raíl tiene al menos una pareja de ataques reales, uno que debe pasar y uno que debe bloquearse; un ataque que sigue en verde con el raíl desactivado no cuenta.
5. El backup de --aplicar lleva fecha y nunca se pisa.
6. compuerta_f1.py y compuerta_d7c.py son re-ejecutables en cualquier orden sobre la misma base.

La comprobación literal de R1 no cambia: python plantilla/compuerta_f1.py --db registro-copia.db --atacar
