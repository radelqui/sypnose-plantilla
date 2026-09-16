# M2 — Esqueleto de microservicio reutilizable

## Objetivo (Fase 4, TRASPASO-5)

Extraer un esqueleto reutilizable de rag-banking-agent en `plantilla/microservicio/`
con un script `instanciar_microservicio.py` que genera un repo listo (make test en verde,
docker build OK) sin editar ningún fichero a mano.

## R0 — Instanciación funcional del esqueleto

**EARS:**
> Cuando se ejecute `python microservicio/instanciar_microservicio.py demo-x --puerto 8010
> --destino /tmp/demo-x` desde el worktree de plantilla, el sistema DEBERÁ dejar un repo
> en el que `make test` está en verde y `docker build .` termina bien, sin editar ningún
> fichero a mano.

**Comprobación ejecutable:**
```bash
cd /tmp && rm -rf demo-x && python microservicio/instanciar_microservicio.py demo-x --puerto 8010 --destino /tmp/demo-x && make -C /tmp/demo-x test
```

## R1 — Cero ficheros fuera del dominio

**EARS:**
> Cuando se compare el microservicio generado con el esqueleto
> (`git diff --stat esqueleto-v1..HEAD -- . ':!app/<dominio>' ':!tests/<dominio>'`),
> el resultado DEBERÁ ser vacío (0 ficheros fuera de la lógica de negocio).
> El tag `esqueleto-v1` se crea al cerrar las tareas de extracción (53/54/55).

**Comprobación ejecutable:**
```bash
cd /tmp/demo-x && git diff --stat esqueleto-v1..HEAD -- . ':!app/demo_x/' ':!tests/demo_x/' | wc -l
```
