# M4 — Opciones del banco preparadas

## Objetivo

Preparar las opciones tecnológicas que el banco puede sustituir: directorio
Terraform con módulos base (EKS, IAM, Secrets Manager, Bedrock), y
observabilidad mínima en el esqueleto (X-Request-Id, log JSON, GET /metrics).

## R0 — Spec EARS: terraform y observabilidad del esqueleto

**EARS (R1 — Terraform):**
> Cuando exista `microservicio/esqueleto/terraform/main.tf`, el directorio DEBE
> contener al menos los providers `aws` y `kubernetes`, un módulo `eks` y un
> `README.md` que documente los tres comandos de despliegue; `terraform validate`
> (o `python-hcl2` parse) DEBE pasar sin errores.

**EARS (R2 — Observabilidad):**
> Cuando el esqueleto reciba una petición HTTP, la respuesta DEBE incluir la
> cabecera `X-Request-Id` (UUID); GET /metrics DEBE devolver 200 con al menos
> una métrica `http_requests_total`; los logs de uvicorn DEBEN emitirse en formato
> JSON con los campos `timestamp`, `level`, `request_id`.

**Comprobación ejecutable (literal, única):**

```bash
python microservicio/comprobar_opciones.py
```

Valida:
1. `terraform/main.tf` existe y parsea sin errores (python-hcl2 o `terraform validate`)
2. `terraform/README.md` existe y contiene los tres comandos
3. pytest del esqueleto para GET /metrics (status 200, contiene `http_requests_total`)
4. pytest del esqueleto para X-Request-Id (presente en respuesta de /health/live)
