"""Crea PLAN-CS-F0 (Fase 0 determinista) del informe de viabilidad JEV.

Cinco cambios deterministas sin proveedor externo, derivados de §7.1 del
informe-viabilidad-jev-sypnose.md. Cierra R1-R5 del informe.

    python3 crear_plan_f0.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import (
    backup_registro,
    verificar_canonicos_registrados,
    verificar_repo_limpio,
    verificar_sin_delete,
)

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_f0.py"

PLAN_ID = "PLAN-CS-F0"
SOL_ID = "sol:coforge:sypnose-plantilla"

REQUISITOS = [
    {
        "ref": "R1",
        "ears": (
            "Cuando se ejecute python3 plantilla/compuerta_d7c.py --db <copia de registry.db> "
            "desde el worktree, DEBE pasar todos los tests: trigger INSERT gemelo del de UPDATE "
            "que restringe verificada_por a IA:07-verificador:* o H:*; firmar.py exige evento "
            "verificado con actor == tarea.verificada_por y cuando posterior al tarea_entregada; "
            "entregar_tarea.py no escribe verificada_por al entregar; las 7 filas contaminadas "
            "(70, 17, 41, 34, 38, 40, 44) tienen verificada_por corregido o vaciado con evento "
            "y nota_lead."
        ),
        "comprobacion": "python3 plantilla/compuerta_d7c.py --db copia-registry.db",
    },
    {
        "ref": "R2",
        "ears": (
            "Cuando se ejecute python3 caparazon/caparazon/probar_bloqueos.py desde el worktree "
            "del caparazon, DEBE incluir un caso donde la salida '42 skipped in 0.20s' bloquea "
            "la entrega, y el patron FALLO DEBE incluir skipped|deselected|xfailed con exigencia "
            "de al menos un 'passed' en comprobaciones pytest."
        ),
        "comprobacion": "python3 caparazon/caparazon/probar_bloqueos.py",
    },
    {
        "ref": "R3",
        "ears": (
            "Cuando se ejecute python3 plantilla/cargar_requisito.py --db <copia> con un "
            "requisito cuya comprobacion sea prosa, 'true' o un comando sin la bateria completa "
            "(--cov-fail-under) para tareas de codigo en repos con bateria, DEBE rechazar el "
            "requisito con exit != 0. Los requisitos heredados que no cumplan se listan como deuda "
            "en un fichero, no se reescriben."
        ),
        "comprobacion": "python3 plantilla/test_cargar_requisito_f0.py --db copia-registry.db",
    },
    {
        "ref": "R4",
        "ears": (
            "Cuando se consulte la portada de la consola, el coste observado DEBE reflejar la "
            "suma real de coste_sesion_usd (no coste_turno_usd acumulado), la clave de "
            "deduplicacion en oferta.mjs:1096-1101 DEBE usar coste_sesion_usd, y los eventos "
            "herramienta_fallida:* DEBEN incluirse en el computo de coste."
        ),
        "comprobacion": "python3 plantilla/test_coste_dedup.py --db copia-registry.db",
    },
    {
        "ref": "R5",
        "ears": (
            "Cuando se consulte tarea.coste en el registro, DEBE ser la cifra calculada por "
            "atribucion de eventos (no copiada de plan.coste_real). La respuesta 9 del nodo "
            "solucion y portada.numeros DEBEN publicar la cifra observada honesta con su "
            "definicion."
        ),
        "comprobacion": "python3 plantilla/test_coste_tarea.py --db copia-registry.db",
    },
    {
        "ref": "R6",
        "ears": (
            "Cuando cualquier script de plantilla escriba en el registro, el detalle del evento "
            "DEBE incluir host, usuario de sistema y pid del proceso, insertados en un unico "
            "punto (barrera.py o funcion comun) sin repeticion en cada script."
        ),
        "comprobacion": "python3 -c \"from barrera import procedencia; p=procedencia(); assert 'host=' in p and 'user=' in p and 'pid=' in p, p; print('OK:', p)\"",
    },
    {
        "ref": "R7",
        "ears": (
            "Cuando se ejecute python3 plantilla/comprobar_esquema.py --db <copia> desde el "
            "worktree, DEBE calcular sha256 del .schema completo, compararlo con el ultimo "
            "esquema_hash registrado, detectar un DROP TRIGGER como diferencia, y registrar "
            "evento esquema_hash si el hash cambio."
        ),
        "comprobacion": "python3 plantilla/comprobar_esquema.py --db copia-registry.db",
    },
]

TAREAS = [
    {
        "req_ref": "R1",
        "titulo": (
            "F0.1 D7 completo: trigger INSERT gemelo, firmar.py exige verificado, "
            "entregar_tarea.py sin verificada_por, repaso 7 filas contaminadas"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R2",
        "titulo": (
            "F0.2 stop.py: patron FALLO con skipped|deselected|xfailed, "
            "exigir al menos un passed, caso en probar_bloqueos.py"
        ),
        "agente": "IA:08-caparazon:claude-opus-4-6",
    },
    {
        "req_ref": "R3",
        "titulo": (
            "F0.3 cargar_requisito.py: rechazar comprobaciones no ejecutables, "
            "exigir bateria con --cov-fail-under para tareas de codigo"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R4",
        "titulo": (
            "F0.4a coste consola: corregir dedup coste_turno_usd a coste_sesion_usd "
            "en oferta.mjs:1096-1101, incluir herramienta_fallida:*"
        ),
        "agente": "IA:09-sypnose-vista:claude-sonnet-5",
    },
    {
        "req_ref": "R5",
        "titulo": (
            "F0.4b coste tarea: dejar de copiar plan.coste_real a tarea.coste, "
            "recalcular, corregir portada.numeros con cifra honesta"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R6",
        "titulo": (
            "F0.5 procedencia: host, usuario y pid en detalle de cada escritura "
            "al registro, un unico punto en barrera.py"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
    {
        "req_ref": "R7",
        "titulo": (
            "F0.6 hash de esquema: comprobar_esquema.py calcula sha256 del .schema, "
            "compara con ultimo registrado, detecta DROP TRIGGER"
        ),
        "agente": "IA:05-arquitecto-sypnose:claude-opus-4-6",
    },
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    verificar_sin_delete()
    verificar_repo_limpio()

    db = Path(args.db).expanduser()
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    verificar_canonicos_registrados(conn)

    if conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        print(f"[skip] {PLAN_ID} ya existe")
        conn.close()
        return

    sol = conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone()
    if not sol:
        conn.close()
        raise SystemExit(f"[FALLO] {SOL_ID} no existe en nodo")

    if not args.dry_run:
        backup_registro(conn, db, "pre-f0")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, "
            "dueno, worktree, abierto_en) "
            "VALUES (?, 'mantener', "
            "'Fase 0 determinista: cerrar agujeros de rail demostrados por el informe de viabilidad JEV', "
            "'Que los cinco railes fundamentales (D7 verificacion, D5 comprobacion, coste, procedencia, esquema) "
            "funcionen como se documentan antes de anadir cualquier juez externo', "
            "'El informe de viabilidad (21-sep) demuestra que el verificado complaciente es de rail, no de modelo: "
            "tarea 70 con verificada_por escrito en la misma transaccion de la entrega, 0 de 82 requisitos con "
            "--cov-fail-under, coste inflado 11.4x, registro sin procedencia, esquema sin hash', "
            "?, 'abierto', ?, 'H:carlos', 'plantilla/wt-F0', ?)",
            (PLAN_ID, SOL_ID, ACTOR, ts),
        )
        print(f"  [plan] {PLAN_ID} creado y abierto (afecta {SOL_ID})")

        for req in REQUISITOS:
            conn.execute(
                "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (PLAN_ID, req["ref"], req["ears"], req["comprobacion"]),
            )
            print(f"  [req] {PLAN_ID}/{req['ref']}")

        tarea_ids = []
        for t in TAREAS:
            cur = conn.execute(
                "INSERT INTO tarea (plan_id, req_ref, titulo, progreso, agente) "
                "VALUES (?,?,?,?,?)",
                (PLAN_ID, t["req_ref"], t["titulo"], "pendiente", t["agente"]),
            )
            tarea_ids.append(cur.lastrowid)
            print(f"  [tarea] {cur.lastrowid}: {PLAN_ID}/{t['req_ref']} -> {t['agente']}")

        conn.execute(
            "INSERT INTO evento (cuando, actor, accion, plan_id, detalle) VALUES (?,?,?,?,?)",
            (ts, ACTOR, "plan_creado", PLAN_ID,
             f"plan {PLAN_ID} Fase 0 determinista afecta {SOL_ID}, "
             f"{len(REQUISITOS)} requisitos (R1-R7), {len(TAREAS)} tareas "
             f"({','.join(str(t) for t in tarea_ids)}). "
             f"Orden del lead 21-sep derivada del informe de viabilidad JEV seccion 7.1: "
             f"5 cambios deterministas sin proveedor externo."),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(f"\n[OK] {PLAN_ID}: {len(REQUISITOS)} req, {len(TAREAS)} tareas")
    for i, tid in enumerate(tarea_ids):
        print(f"  tarea {tid}: {TAREAS[i]['titulo'][:80]}")
    if args.dry_run:
        print("--dry-run: transaccion deshecha")


if __name__ == "__main__":
    main()
