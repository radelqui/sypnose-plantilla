# PLAN-CS-F2 — Reparaciones tras el re-juicio: texto dictado por el lead

Versión 2 · 21-sep-2026 (v1 sha256 d36404c1...8c2e; v2: cambio NEUTRO en la comprobación de R4: el formato de git va entre comillas dobles porque sin ellas los paréntesis no son ejecutables en un shell; aprobado por el lead tras el veredicto 25067) · autor: 00-lead · origen: re-juicio retroactivo (eventos 24966, 24967, 24986), informe de viabilidad de Jev (§2.1, §7.3) y Requerimientos/F1/restauracion-requisitos.md.
El arquitecto abre el plan y carga estos requisitos LITERAL como operador (sin --delegado, tareas sin verificada_por). El veredicto de cada tarea lo decide el examen que ejecuta el verificador Opus del lead sobre clon limpio; la comprobación literal es la orden que el ejecutor corre para entregar por el caparazón.

Plan: PLAN-CS-F2 · afecta: sol:coforge:rag-banking-agent · dueño: H:carlos (por delegación registrada 22656/22676).

## R1 — CI de main en verde y rama protegida (ejecutor: 01-git-cicd)

EARS:
Cuando se consulte la última ejecución del workflow de CI en la rama main de radelqui/rag-banking-agent, el job de tests DEBE haber terminado en success con las cinco puertas ejecutadas (ruff, bandit, pytest con cobertura mínima del 85 %, gitleaks y trivy) y el job de despliegue DEBE quedar esperando la aprobación humana; la rama main DEBE tener protección de rama con el check de tests como requerido; y el main local de los worktrees DEBE coincidir con origin/main.

Comprobación:
python ci/comprobar_ci_main.py

Examen del verificador (decide el veredicto): `gh run list --repo radelqui/rag-banking-agent --branch main --limit 1 --json databaseId,status,conclusion`, `gh run view <id> --repo radelqui/rag-banking-agent --json jobs`, y `gh api repos/radelqui/rag-banking-agent/branches/main/protection`. Si el token no tiene permiso de administración para aplicar la protección, la entrega incluye la orden exacta para que la ejecute Carlos y el veredicto queda como CUMPLE PARCIAL declarado, no como CUMPLE.

## R2 — Requisito honesto de la línea de Git (ejecutor: 01-git-cicd, que no es el ejecutor de la línea T09)

EARS:
El fichero specs/T09/spec.md del repositorio de la plantilla DEBE contener, escrito por 01-git-cicd (trailer Chat: 01-git-cicd), el requisito R1 de la línea T09 con esta regla: desde el commit de corte en que se instaló el hook commit-msg en cada repositorio (identificado por su sha y su fecha), el 100 % de los commits lleva los trailers Chat, Model y Plan, medido como igualdad y no como umbral; los commits anteriores al corte se listan como deuda histórica con su recuento y no se reescribe la historia. La comprobación del requisito es un script que recorre los commits posteriores al corte en rag-banking-agent, sypnose-plantilla y como-estoy-hecho, termina con código distinto de 0 si a alguno le falta un trailer, e imprime el recuento de deuda anterior al corte.

Comprobación:
python plantilla/comprobar_trailers.py

## R3 — Compose de la demo publicado (ejecutor: 01-git-cicd; re-entrega de la tarea 63)

EARS:
El fichero microservicio/demo/docker-compose.demo.yml y su README de tres órdenes DEBEN existir en la rama main de radelqui/sypnose-plantilla, con los servicios rag-banking-agent, como-estoy-hecho y la base efímera, healthcheck en cada servicio de aplicación y ninguna variable con valor de secreto.

Comprobación:
python microservicio/demo/comprobar_compose.py

Examen del verificador (decide el veredicto): en el servidor 67, sobre clon limpio de main de radelqui/sypnose-plantilla, `docker compose -f microservicio/demo/docker-compose.demo.yml config --quiet` con código 0.

## R4 — Spec de la línea de code reviews escrita por el rol verificador (ejecutor: rol 07)

EARS:
El fichero specs/T06/spec.md DEBE estar escrito por el rol 07-verificador (trailer Chat: 07-verificador en el commit que lo crea o lo reescribe), con el requisito R1 de T06 restaurado a su invariante original (ninguna tarea pasa a espera_firma sin verificada_por distinto del agente ejecutor; recuento igual a 0) y sin el contador de eventos con la palabra CUMPLE.

Comprobación:
git log -1 --format="%(trailers:key=Chat,valueonly)" -- specs/T06/spec.md

Salida esperada, literal: 07-verificador.

## Tareas

- Tarea R1: "CI de main en verde y protección de rama" · agente IA:01-git-cicd:claude-opus-4-6.
- Tarea R2: "Requisito honesto de trailers para la línea de Git" · agente IA:01-git-cicd:claude-opus-4-6.
- Tarea R3: "Compose de la demo publicado en main" · agente IA:01-git-cicd:claude-opus-4-6.
- Tarea R4: "Spec de T06 escrita por el rol verificador" · agente IA:07-verificador:claude-opus-5 · su veredicto lo da un humano o el segundo verificador, nunca el propio rol 07 que la escribe (D7b).

Al abrir el plan, el worktree de 01 debe poder trabajar estas tres tareas (su caparazón hoy le bloquea por no tener tarea abierta).
