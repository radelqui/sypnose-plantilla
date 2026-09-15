## Caparazón SYPNOSE (lo instala plantilla/caparazon/instalar_caparazon.py; no se edita a mano)
- Al arrancar, el hook SessionStart te da el BRIEF leído del registro: plan abierto, tarea, requisito EARS, comprobación, archivos permitidos, presupuesto, grafo del repo y última lección de la línea. Si dice ABORTADO no hay trabajo posible hasta que Carlos abra el plan; cada prompt vuelve a consultarlo.
- Solo escribes dentro de `{{WORKTREE}}` y en los archivos permitidos del brief. Lo demás se bloquea y queda como `bloqueo:cerco` en el registro.
- Cada herramienta deja un evento en el registro con tokens y coste del turno. Si el registro no responde, la sesión se para.
- Commits con pie obligatorio: `Chat: {{CARPETA}}` / `Model: <modelo real>` / `Plan: <plan del brief>` / `Tarea: <id de tarea del brief>`.
- Cierre: ejecuta la comprobación, avisa a 07-verificador con send_message (incluye el bloque ENTREGA) y termina con el bloque `ENTREGA` (Comprobación literal, Salida real pegada, `LECCIÓN:`). Si necesitas a Carlos antes, acaba con `PREGUNTA: ...`.
- Túnel del registro y la KB: `{{TUNEL}}`
