"""Crea PLAN-CS-F1 (Integridad de requisitos) — operador, no autor.

Requisitos dictados por 00-lead en Requerimientos/F1/requisitos-dictados.md
(sha256 12715e8622f5a6a6b73f95c54a199b0d9adb58a0f82bd4cf8888b251a214757c).
El arquitecto actua como operador: no es autor ni ejecutor.

    python3 crear_plan_f1.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/crear_plan_f1.py"

PLAN_ID = "PLAN-CS-F1"
SOL_ID = "sol:coforge:sypnose-plantilla"
FICHERO_HASH = "12715e8622f5a6a6b73f95c54a199b0d9adb58a0f82bd4cf8888b251a214757c"

EARS_R0 = (
    'El fichero specs/F1/spec.md DEBE existir en el repositorio de la plantilla, '
    'escrito por 08-caparazon (trailer Chat: 08-caparazon en el commit que lo crea), '
    'con una sección "## RAÍL n" para cada n de 1 a 7, y en cada sección '
    'un enunciado EARS y una línea "Comprobación:" con un comando ejecutable: '
    '(1) autoría R0: el trailer Chat: del commit de la spec coincide con el rol '
    'que nombra el EARS del R0 y el fichero de la spec existe en la ruta citada; '
    '(2) el examinado no reescribe su examen: un requisito no lo modifica ni el '
    'agente de una tarea abierta que ese requisito examina ni su rol autor interpuesto; '
    '(3) todo cambio de requisito deja un evento con el texto anterior y el posterior '
    'y la clasificación ablanda=si|no|neutro, y un cambio con ablanda=si exige una '
    'aprobación previa registrada de un actor humano o del lead, distinto del ejecutor '
    'y del autor; (4) un requisito con alguna tarea firmada queda congelado; '
    '(5) entre un cambio con ablanda=si o sin clasificar y la entrega de la tarea que '
    'examina pasan al menos 30 minutos (los cambios neutro quedan exentos); '
    '(6) sin evento tarea_entregada de una tarea no se admite un evento verificado de '
    'esa tarea; (7) el flag --delegado deja de existir en cargar_requisito.py y en '
    'cualquier otro script.'
)

COMPROBACION_R0 = 'grep -c "^## RAÍL [1-7]" specs/F1/spec.md'

EARS_R1 = (
    'Cuando se ejecute python plantilla/compuerta_f1.py --db registro-copia.db --atacar '
    'sobre una copia del registro vivo hecha con sqlite3 .backup, el sistema DEBE: '
    '(a) trabajar solo sobre esa copia, sin escribir jamás en el registro vivo; '
    '(b) instalar como triggers los raíles que SQLite permite (al menos 2, 4 y 6) '
    'y como comprobaciones de script los demás; '
    '(c) ejecutar al menos 14 ataques, dos por raíl, uno que debe pasar y uno que '
    'debe bloquearse, e imprimir una línea por ataque con su resultado; '
    '(d) terminar con código 0 solo si los 14 o más ataques dan el resultado esperado, '
    'y con código distinto de 0 en cualquier otro caso. '
    'El modo --verificar DEBE recorrer el registro y nombrar, por raíl, las violaciones '
    'ya existentes, entre ellas las diez de la auditoría: '
    'PLAN-CS-T06/R1, PLAN-CS-T08/R1, PLAN-CS-T05/R1, PLAN-CS-T10/R1, PLAN-CS-T07/R1, '
    'PLAN-CS-T09/R1, PLAN-CS-T03/R1, PLAN-CS-M5/R1, PLAN-CS-M2/R0-R1 y PLAN-CS-0001/R1, '
    'y las tareas 13 y 18 con veredicto sin entrega. '
    'El modo --aplicar DEBE hacer backup con sqlite3 .backup, instalar los triggers, '
    'registrar un evento con el hash del esquema resultante y no modificar ninguna fila '
    'existente. Ningún otro trigger del esquema (C8, D4, D5, D7, D7b, D7c) cambia.'
)

COMPROBACION_R1 = 'python plantilla/compuerta_f1.py --db registro-copia.db --atacar'

TAREAS = [
    {
        "req_ref": "R0",
        "titulo": "Spec de los siete raíles de integridad de requisitos",
        "agente": "IA:08-caparazon:claude-opus-4-6",
    },
    {
        "req_ref": "R1",
        "titulo": "compuerta_f1.py: raíles, ataques, verificar y aplicar",
        "agente": "IA:08-caparazon:claude-opus-4-6",
    },
]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(description="Crear PLAN-CS-F1 (integridad de requisitos)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    if conn.execute("SELECT 1 FROM plan WHERE id=?", (PLAN_ID,)).fetchone():
        print(f"[skip] {PLAN_ID} ya existe")
        conn.close()
        return

    sol = conn.execute("SELECT 1 FROM nodo WHERE id=?", (SOL_ID,)).fetchone()
    if not sol:
        sys.exit(f"[FALLO] nodo {SOL_ID} no existe")

    if not args.dry_run:
        backup_registro(conn, db_path, "pre-f1")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, "
            "dueno, worktree, abierto_en) "
            "VALUES (?, 'mantener', "
            "'Integridad de requisitos: siete raíles contra manipulación del examen', "
            "'Que ningún agente pueda reescribir su propio examen, ablandar un requisito sin "
            "aprobación, ni obtener veredicto sin entrega', "
            "'Auditoría 07-verificador/AUDITORIA-R0-ROLES.md: 10 de 16 requisitos ablandan "
            "el examen, 8 R0 fallan, tareas 13/18 con CUMPLE sin tarea_entregada, flag --delegado "
            "usado 16s antes de cargar T06/R1', "
            "?, 'abierto', ?, 'H:carlos', 'plantilla/wt-F1', ?)",
            (PLAN_ID, SOL_ID, ACTOR, ts),
        )
        print(f"  [plan] {PLAN_ID} creado (afecta {SOL_ID})")

        conn.execute(
            "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
            (PLAN_ID, "R0", EARS_R0, COMPROBACION_R0),
        )
        print(f"  [req] {PLAN_ID}/R0")

        conn.execute(
            "INSERT INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
            (PLAN_ID, "R1", EARS_R1, COMPROBACION_R1),
        )
        print(f"  [req] {PLAN_ID}/R1")

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
             f"plan {PLAN_ID} integridad de requisitos, afecta {SOL_ID}, "
             f"2 requisitos (R0, R1), 2 tareas ({','.join(str(t) for t in tarea_ids)}). "
             f"Requisitos dictados por 00-lead, fichero Requerimientos/F1/requisitos-dictados.md "
             f"sha256 {FICHERO_HASH[:16]}...; el arquitecto actúa como operador, "
             f"no es autor ni ejecutor. Tarea R1 ({tarea_ids[1]}) bloqueada por R0 ({tarea_ids[0]})."),
        )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(f"\n[OK] {PLAN_ID}: 2 req, 2 tareas")
    for i, tid in enumerate(tarea_ids):
        print(f"  tarea {tid}: {TAREAS[i]['titulo']}")
    if args.dry_run:
        print("--dry-run: transaccion deshecha")


if __name__ == "__main__":
    main()
