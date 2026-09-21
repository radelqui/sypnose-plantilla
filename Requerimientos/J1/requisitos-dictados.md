# PLAN-CS-J1 — Jev como segunda opinión de otra familia: texto dictado por el lead

Versión 2 · 21-sep-2026 (v1 sha256 ce6adb45942e4e4a25aa08075c63185d6e57db04471dff5e5696c9d63e506c65, en git 656dd90, nunca cargada en el registro; v2 amplía R3 por orden de Carlos: "se debería ver Jev en la plantilla, poder mostrar qué hace") · autor: 00-lead · origen: orden de Carlos del 21-sep ("Jev incorporado en los procesos"), Requerimientos/JEV/informe-viabilidad-jev-sypnose.md y 11-JEV/PLAN-JEV.md v2.
El arquitecto abre el plan y carga estos requisitos LITERAL como operador (tareas sin verificada_por). El veredicto lo dan verificadores Opus del lead. Formato canónico de comprobación.

Plan: PLAN-CS-J1 · afecta: sol:coforge:sypnose-plantilla · dueño: H:carlos (por delegación registrada 22656/22676).

## Decisión de diseño (no se negocia dentro del plan)

Jev NO es juez ni compuerta. En las evaluaciones de su propio fabricante acierta menos que Opus 5 (67,8 % frente a 73,1 %) y pierde 16,6 puntos en cotejo documental, que es el perfil del microservicio bancario. Lo que aporta es otra familia de modelo y coste casi nulo. Entra en UN punto del flujo: después de cada tarea_entregada, como observador. Su nota se guarda como afirmación de un sensor (actor S:jev, tratado como sensor, sin alta en la tabla actor). Nunca escribe verificada_por, nunca firma, nunca bloquea una entrega, y no se conecta al hook de parada. Si su nota discrepa del veredicto del verificador, la tarea se marca para que el humano la mire primero al firmar. Solo recibe datos ya públicos (el JSON público de la vista, ya redactado, y los diffs públicos de GitHub). Si la API cae, no hay nota y nada se rompe. Precondición de todo el plan: T1 (contrato) de 11-JEV pasado con clave real y versión de modelo sellada.

## R1 — Observador de entregas (ejecutor: 11-jev)

EARS:
Cuando se ejecute observar_entregas.py, el sistema DEBE, para cada tarea con evento tarea_entregada cuyas piezas (requisito, diff, salida y, si existe, veredicto) estén en fuentes públicas, preguntar a Jev con el banco de preguntas congelado en git y el modelo sellado, y escribir un fichero opiniones/tarea-<id>.json con: tarea, evento de entrega, commit del banco, modelo, nota por pregunta, nota de la tarea como eslabón más débil, abstenciones, señales de inyección, latencia, coste y el sha256 de la entrada enviada; DEBE enviar solo datos públicos y pasar la entrada por el saneado; DEBE degradar a "sin nota" con código 0 si la API no responde; DEBE respetar un tope de gasto configurable; y NO DEBE leer ni escribir el registro.

Comprobación:
python observar_entregas.py --autotest

Examen del verificador (decide el veredicto): ejecución real sobre las tareas públicas; API inalcanzable → "sin nota" y código 0; entrada con un secreto sembrado o una ruta interna → rechazada antes de enviarse; repetición → misma estructura y coste acumulado declarado; ningún acceso al registro en el código.

## R2 — Carga de opiniones por el molde (ejecutor: 05-arquitecto-sypnose)

EARS:
Cuando se ejecute registrar_opinion.py sobre un fichero de opinión, el sistema DEBE insertar, por la barrera y solo con INSERT, una afirmación del actor S:jev sobre el nodo de la tarea con la nota, el modelo, el commit del banco y el sha256 del fichero, y un evento opinion_registrada; DEBE rechazar un fichero cuyo sha256 no coincida o cuya tarea no tenga evento tarea_entregada; NO DEBE tocar la fila de la tarea, ni verificada_por, ni ningún evento verificado o firma_tarea; y una opinión NUNCA DEBE contar como veredicto para firmar.py.

Comprobación:
python plantilla/registrar_opinion.py --db registro-copia.db --atacar

Examen del verificador (decide el veredicto): ataques sobre copia: opinión sin entrega, hash falso, intento de usar la opinión como veredicto en firmar.py (debe rechazarse), doble carga de la misma opinión (idempotente o rechazada con mensaje), compuerta_d7c.py y compuerta_f1.py siguen en verde con opiniones cargadas.

## R3 — La segunda opinión en la vista (ejecutor: 09-sypnose-vista)

EARS:
Cuando una tarea tenga una opinión de S:jev, la vista DEBE mostrar en esa tarea "Segunda opinión (Jev, otra familia de modelo)" con la nota, si coincide o DISCREPA con el veredicto del verificador y el enlace a su evidencia, y al desplegarla DEBE enseñar qué hizo Jev: cada pregunta del banco congelado con su probabilidad, las abstenciones, cuál fue el eslabón más débil, el modelo sellado, el commit del banco, la latencia y el coste; la portada DEBE mostrar el lugar de Jev en el flujo como una cadena de cinco pasos (entrega · comprobación determinista del caparazón · veredicto del verificador independiente · segunda opinión probabilística de Jev · firma humana), con un paso de modo demostración que abra una tarea real opinada; la portada DEBE mostrar en la plataforma agéntica la pieza "evaluador barato de otra familia" con los números MEDIDOS por nosotros (tareas opinadas, coincidencias, discrepancias, coste total, latencia media) y la frase literal "no es juez: en las evaluaciones de su fabricante acierta menos que Opus 5"; las tareas con discrepancia DEBEN aparecer primero en la lista de lo pendiente de firma; y sin opiniones cargadas la vista NO DEBE mostrar nada de Jev.

Comprobación:
node --test tests/opinion-jev.test.mjs

Examen del verificador (decide el veredicto): por contenido sobre copia con opiniones sembradas (coincide, discrepa, sin nota) y sobre el registro real; 0 datos no públicos; examen corto y compuerta del lead para desplegar.

## Tareas

- Tarea R1: "Observador de entregas con Jev" · agente IA:11-jev:claude-opus-5 · bloqueada hasta T1 pasado.
- Tarea R2: "registrar_opinion.py por el molde" · agente IA:05-arquitecto-sypnose:claude-opus-4-6.
- Tarea R3: "Segunda opinión en la vista" · agente IA:09-sypnose-vista:claude-opus-4-6 · bloqueada por R2.
