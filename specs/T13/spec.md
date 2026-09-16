# T13 — Docker and Kubernetes knowledge

## Oferta (nice-to-have, literal de `oferta-coforge.txt`)

> Docker and Kubernetes knowledge.

## Solución

`rag-banking-agent` se empaqueta con un Dockerfile multi-stage
(`python:3.11-slim` → builder → runtime) y se despliega con manifests
Kubernetes en `k8s/`.

- **Dockerfile**: imagen base fijada (`python:3.11-slim`), `apt-get upgrade`
  en ambas etapas, dependencias copiadas desde el builder, usuario no root
  (`appuser`, UID 10001), pip eliminado del runtime (reduce superficie de
  ataque), `HEALTHCHECK` declarado.
- **k8s/deployment.yaml**: `readOnlyRootFilesystem: true`,
  `allowPrivilegeEscalation: false`, `capabilities: { drop: ["ALL"] }`,
  `runAsNonRoot: true`, `resources` con requests y limits,
  `startupProbe`/`readinessProbe`/`livenessProbe`, `preStop` para cierre
  limpio de streams SSE.

## R1 — Imagen endurecida con manifiesto seguro

**EARS:**
> Cuando se construya la imagen Docker, esta DEBE ejecutar como usuario no root,
> declarar HEALTHCHECK y usar build multi-stage; el Deployment de Kubernetes
> DEBE establecer readOnlyRootFilesystem: true y eliminar todas las capabilities.

**Comprobación ejecutable** (determinista — valida propiedades de seguridad
en Dockerfile y k8s/deployment.yaml):

```bash
python -c "d=open('Dockerfile').read();k=open('k8s/deployment.yaml').read();assert 'USER appuser' in d;assert 'HEALTHCHECK' in d;assert 'readOnlyRootFilesystem: true' in k;assert 'drop' in k and 'ALL' in k;print('ok')"
```

Resultado esperado: `ok`

---
Chat: 01-git-cicd
Model: claude-opus-4-6
Plan: PLAN-CS-T13
Tarea: 45
