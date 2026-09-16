# M2 — Esqueleto de microservicio reutilizable

## Objetivo (Fase 4, TRASPASO-5)

Extraer un esqueleto reutilizable de rag-banking-agent en `plantilla/microservicio/`
con un script `instanciar_microservicio.py` que genera un repo listo (make test en verde,
docker build OK) sin editar ningún fichero a mano.

## R0 — Instanciación funcional del esqueleto

**EARS:**
> Cuando se ejecute `python microservicio/comprobar_esqueleto.py` desde el worktree de
> plantilla, el sistema DEBERÁ instanciar demo-x en `.tmp/demo-x`, ejecutar `make test`
> (todos en verde) y verificar que el diff fuera de `app/demo_x/` y `tests/demo_x/`
> contra el tag `esqueleto-v1` es vacío, sin editar ningún fichero a mano.

**Comprobación ejecutable:**
```bash
python microservicio/comprobar_esqueleto.py
```

## R1 — Cero ficheros fuera del dominio

**EARS:**
> Cuando se compare el microservicio generado con el esqueleto
> (`git diff --stat esqueleto-v1..HEAD -- . ':!app/<dominio>' ':!tests/<dominio>'`),
> el resultado DEBERÁ ser vacío (0 ficheros fuera de la lógica de negocio).
> El tag `esqueleto-v1` se crea al instanciar. La comprobación está integrada en
> `comprobar_esqueleto.py` (paso 3/3).

**Comprobación ejecutable:**
```bash
python microservicio/comprobar_esqueleto.py
```
