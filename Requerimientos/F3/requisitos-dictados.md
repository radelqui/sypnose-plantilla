# PLAN-CS-F3 — Remates tras los veredictos del 21-sep: texto dictado por el lead

Versión 1 · 21-sep-2026 · autor: 00-lead · origen: veredictos 24971 (tarea 72), 25068 (tarea 79 v3), 25156 (tarea 80) y 25126 (tarea 82), secciones #tarea72, #tarea79-v3, #tarea80 y #tarea82 de 07-verificador/VERIFICACION.md.
El arquitecto abre el plan y carga estos requisitos LITERAL como operador (tareas sin verificada_por). El veredicto de cada tarea lo decide el examen que ejecuta el verificador Opus del lead; la comprobación es la orden que el ejecutor corre para entregar. Formato canónico de comprobación: [cd "<ruta>" && ]<comando>[ → <valor esperado>].

Plan: PLAN-CS-F3 · afecta: sol:coforge:sypnose-plantilla · dueño: H:carlos (por delegación registrada 22656/22676).

## R1 — Hook de parada: pytest por ejecutable, recuento real y evidencia con cabecera (72-bis; ejecutor: 08-caparazon)

EARS:
Cuando el hook Stop valide una ENTREGA, DEBE decidir que la comprobación ejecuta pytest solo por el nombre base del primer token del comando (pytest, pytest.exe) o por la forma python -m pytest, y en ese caso exigir en la línea de resumen de pytest al menos un test pasado con recuento distinto de cero; una comprobación que contiene la palabra pytest sin ejecutarlo, como la de PLAN-CS-T14/R1, NO DEBE quedar bloqueada por esa regla; y cuando la salida supere el máximo de evidencia, lo guardado DEBE conservar la cabecera, la línea de resumen de pytest y la cola, con un marcador que diga cuántos caracteres se omiten.

Comprobación:
python caparazon/pruebas/probar_bloqueos.py --carpeta "C:\MICD\Coforge Santander\02-backend-api" --modo local

Examen del verificador (decide el veredicto): la batería completa sin NO CUMPLE y ataques propios: "0 passed in 0.10s" bloquea; la comprobación literal de PLAN-CS-T14/R1 con salida "ok" pasa; ".venv/Scripts/pytest.exe" con "42 skipped" bloquea; salida de 10.000 caracteres conserva cabecera, resumen y cola dentro del máximo.

## R2 — Raíles de requisitos: ventana de aprobación cerrada y detección fuerte (79-bis; ejecutor: 08-caparazon)

EARS:
Cuando el trigger del raíl 2 evalúe un evento cambio_requisito_aprobado, DEBE aceptarlo solo si su fecha está dentro de las últimas 24 horas y no es posterior al momento actual; y cuando se ejecute compuerta_f1.py --verificar r2, el sistema DEBE separar en su salida lo que el raíl impide de lo que detecta, y DEBE marcar como violación detectada toda aprobación cuyo fichero citado no exista con ese sha256, o no nombre ese plan y esa referencia, o cuya procedencia coincida con la del ejecutor de la tarea examinada; el recuento de --verificar DEBE ser reproducible desde cualquier máquina, con desglose por raíl y referencia de git fija; y los actores S:* DEBEN quedar documentados como sensores o el propio registro, sin marcarse como violación.

Comprobación:
python plantilla/compuerta_f1.py --db registro-copia.db --atacar

Examen del verificador (decide el veredicto): aprobación fechada en 2099 rechazada; aprobación con fichero inexistente o hash distinto detectada en --verificar r2; mismo recuento en el PC y en el servidor 67; mutación raíl a raíl sin ataques vacuos; el molde completo sigue funcionando con los triggers puestos; ningún cambio de esquema en el vivo sin compuerta del lead.

## R3 — Comprobación de la CI que no caduca (80-bis; ejecutor: 01-git-cicd)

EARS:
Cuando se ejecute ci/comprobar_ci_main.py, el sistema DEBE consultar la última ejecución de main sin fijar su identificador, aceptar el job de despliegue tanto esperando aprobación como completado con éxito, verificar el umbral de cobertura del 85 % leyendo el workflow de la rama main y no una copia local, y terminar con código distinto de 0 si el job de tests no está en success, si falta alguna de las cinco puertas o si main no tiene el check de tests como requerido; y la entrega DEBE incluir, sin ejecutarla, la orden exacta de gh para activar la protección también para administradores, que es decisión de Carlos.

Comprobación:
python ci/comprobar_ci_main.py

Examen del verificador (decide el veredicto): mutaciones sobre copia con gh simulado: tests en failure, deploy en success, workflow sin umbral, sin protección; cada una con el resultado esperado.

## R4 — La demo se levanta siguiendo el README desde cero (82-bis; ejecutor: 01-git-cicd)

EARS:
Cuando alguien siga literalmente las órdenes del README de microservicio/demo en un directorio vacío, todos los contextos de build que declara docker-compose.demo.yml DEBEN existir, o el compose DEBE usar imágenes publicadas sin construir; el README DEBE decir que el puerto de PostgreSQL es interno y no se publica, y que la base solo es efímera con down -v.

Comprobación:
python microservicio/demo/comprobar_compose.py

Examen del verificador (decide el veredicto): en el servidor 67, en un directorio temporal vacío, ejecutar las órdenes de preparación del README y comprobar que docker compose -f microservicio/demo/docker-compose.demo.yml config --quiet sale con 0 y que cada build.context resuelto existe; sin levantar contenedores ni tocar la demo viva.

## Tareas

- Tarea R1: "Stop: pytest por ejecutable, recuento real y evidencia con cabecera" · agente IA:08-caparazon:claude-opus-4-6.
- Tarea R2: "Raíl 2: ventana cerrada y detección fuerte en --verificar" · agente IA:08-caparazon:claude-opus-4-6.
- Tarea R3: "comprobar_ci_main.py que no caduca" · agente IA:01-git-cicd:claude-opus-4-6.
- Tarea R4: "README de la demo reproducible desde cero" · agente IA:01-git-cicd:claude-opus-4-6.
