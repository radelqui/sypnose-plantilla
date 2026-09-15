# plantilla/ — Molde SYPNOSE microservicio-ia

Repo git propio. El PC es el origen; el servidor 67 es clon vía remoto bare.

## Ficheros canónicos

- `oferta-coforge.txt` — 15 líneas literales de la oferta (fuente de verdad del parser)
- `oferta.yaml` — estructura del molde: líneas, roles, comprobaciones, roles_por_linea
- `precios.yaml` — precios por modelo para calcular_coste.py

Cualquier script que escriba en el registro verifica antes que estos ficheros estén
rastreados en git y sin cambios (barrera.py: verificar_repo_limpio).

## Afirmaciones canónicas

- `oferta_hash` — SHA-256 truncado a 16 hex del contenido de oferta-coforge.txt
- `oferta_commit` — último commit que tocó oferta-coforge.txt (`git log -1 --format=%H -- oferta-coforge.txt`),
  NO HEAD; así un commit de scripts no obliga a re-registrar

Registrar/actualizar: `python3 raiz.py sync --db <db> --registrar-hash`

## Sincronización PC ↔ servidor 67

```bash
# PC (origen):
git push origin main

# Servidor 67 (clon):
git pull origin main
python3 raiz.py sync --db ~/sypnose-f1/registry.db --registrar-hash
```

## Regla: sin SQL manual en el registro

NINGUNA escritura directa (SQL manual por SSH o consola) en registry.db. Toda
escritura va por un script de este directorio que pasa la barrera
(`verificar_repo_limpio`, `verificar_canonicos_registrados`) y llama a
`backup_registro()` ANTES de `BEGIN IMMEDIATE`. Scripts de escritura:

| Script | Qué escribe |
|---|---|
| `enlazar_solucion.py` | nodos, relaciones cubre, afirmaciones, certeza |
| `cargar_requisito.py` | requisitos (EARS + comprobación desde spec.md) |
| `cargar_raices.py` | nodos linea_oferta |
| `raiz.py` | operaciones de raíz (add/edit/retirar/sync) |
| `firmar.py` | firmas de tareas |
| `calcular_coste.py` | coste por modelo |
| `instanciar.py` | instanciación de planes |
| `cargar_molde.py` | versiones del molde |
| `cargar_spec.py` | afirmaciones descripcion/por_que desde spec.md |
| `crear_tarea.py` | tareas (con validación plan/agente/rol/idempotencia) |

## historico/

Scripts de corrección de un solo uso (corregir_x1x2.py, corregir_d1d2.py). Conservados
para auditoría. Tienen guardia de idempotencia: si su evento ya existe, abortan sin escribir.
