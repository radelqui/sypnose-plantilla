# M2 — Esqueleto de microservicio reutilizable

## Objetivo (Fase 4, TRASPASO-5)

Extraer un esqueleto reutilizable de rag-banking-agent en `plantilla/microservicio/`
con un script `instanciar_microservicio.py` que genera un repo listo (make test en verde,
docker build OK) sin editar ningún fichero a mano.

## R0 — Spec y requisitos del esqueleto

**EARS:**
> Cuando se ejecute `python plantilla/microservicio/instanciar_microservicio.py demo-x
> --puerto 8010` en un directorio vacío, el sistema DEBERÁ dejar un repo en el que
> `make test` está en verde y `docker build .` termina bien, sin editar ningún fichero
> a mano.

**Comprobación ejecutable:**
```bash
cd /tmp && rm -rf demo-x && python plantilla/microservicio/instanciar_microservicio.py demo-x --puerto 8010 && cd demo-x && make test
```

## R1 — Extracción al esqueleto y generación funcional

**EARS:**
> Cuando se compare el microservicio generado con el esqueleto
> (`git diff --stat <tag esqueleto>..HEAD -- . ':!app/<dominio>' ':!tests/<dominio>'`),
> el resultado DEBERÁ ser vacío (0 ficheros fuera de la lógica de negocio).

**Comprobación ejecutable:**
```bash
cd /tmp && rm -rf demo-x && python plantilla/microservicio/instanciar_microservicio.py demo-x --puerto 8010 && cd demo-x && make test && echo "INSTANCIAR OK"
```
