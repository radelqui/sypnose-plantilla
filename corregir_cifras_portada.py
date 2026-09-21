"""Corregir cifras portada: unificar puertas y practicas (lead item 4).

Crea portada_numeros como fuente unica de verdad y actualiza
portada_pregunta_06 para que coincida.

Puertas: 5 CI (ruff, bandit, pytest>=85%, gitleaks, trivy) + aprobacion humana = 6
Practicas: cuenta real del grupo cicd-calidad (10 al 21-sep)

    python3 corregir_cifras_portada.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barrera import backup_registro, procedencia, registrar_evento

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
NODO = "plantilla:microservicio-ia"
PUERTAS_CI = ["ruff", "bandit", "pytest ≥85 %", "gitleaks", "trivy"]


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser(description="Unificar cifras portada (puertas/practicas)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    n_cicd = conn.execute(
        "SELECT COUNT(*) FROM afirmacion WHERE campo='grupo' AND valor='cicd-calidad' AND vigente=1"
    ).fetchone()[0]
    n_practicas = conn.execute(
        "SELECT COUNT(*) FROM afirmacion WHERE campo='grupo' AND valor='practicas-ingenieria' AND vigente=1"
    ).fetchone()[0]
    n_puertas = len(PUERTAS_CI) + 1

    print(f"[conteo] puertas CI: {len(PUERTAS_CI)} + aprobacion humana = {n_puertas}")
    print(f"[conteo] cicd-calidad: {n_cicd}")
    print(f"[conteo] practicas-ingenieria: {n_practicas}")

    numeros = {
        "puertas_ci": len(PUERTAS_CI),
        "puertas_total": n_puertas,
        "puertas_lista": PUERTAS_CI + ["aprobación humana"],
        "practicas_cicd": n_cicd,
        "practicas_ingenieria": n_practicas,
        "nota": f"5 CI + 1 humana = {n_puertas} puertas; {n_cicd} piezas cicd-calidad; {n_practicas} practicas-ingenieria",
    }
    print(f"\n[numeros] {json.dumps(numeros, ensure_ascii=False, indent=2)}")

    pregunta_06_actual = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='portada_pregunta_06' AND vigente=1",
        (NODO,),
    ).fetchone()

    if pregunta_06_actual:
        p06 = json.loads(pregunta_06_actual[1])
        print(f"\n[actual pregunta_06] {p06.get('respuesta', '')[:150]}")

    p06_nuevo = {
        "pregunta": "¿Qué puertas tiene el pipeline y están fijadas?",
        "respuesta": (
            f"Seis puertas: cinco en la CI del servicio ({', '.join(PUERTAS_CI)}) "
            f"y aprobación humana obligatoria. "
            f"{n_cicd} piezas de calidad CI/CD en el stack "
            f"y {n_practicas} prácticas de ingeniería. "
            f"Todas fijadas por SHA de commit, no por etiqueta móvil, "
            f"porque una etiqueta borrada en el upstream ya rompió un paso."
        ),
        "prueba": ".github/workflows/ci.yml@a582cb2",
    }
    print(f"\n[nuevo pregunta_06] {p06_nuevo['respuesta'][:150]}")

    if args.dry_run:
        print("\n[dry-run] sin cambios")
        conn.close()
        return

    backup_registro(conn, db_path, "pre-cifras-portada")

    ts = ahora()
    conn.execute("BEGIN IMMEDIATE")
    try:
        numeros_existente = conn.execute(
            "SELECT id FROM afirmacion WHERE nodo_id=? AND campo='portada_numeros' AND vigente=1",
            (NODO,),
        ).fetchone()
        if numeros_existente:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (numeros_existente[0],))

        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
            "VALUES (?,?,?,?,?,?,?)",
            (NODO, "portada_numeros", json.dumps(numeros, ensure_ascii=False),
             "observado", "plantilla/corregir_cifras_portada.py", ACTOR, ts),
        )

        if pregunta_06_actual:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (pregunta_06_actual[0],))
        conn.execute(
            "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando) "
            "VALUES (?,?,?,?,?,?,?)",
            (NODO, "portada_pregunta_06", json.dumps(p06_nuevo, ensure_ascii=False),
             "observado", "plantilla/corregir_cifras_portada.py", ACTOR, ts),
        )

        registrar_evento(
            conn, ts, ACTOR, "portada_corregida",
            f"cifras unificadas (lead item 4): {n_puertas} puertas ({len(PUERTAS_CI)} CI + humana), "
            f"{n_cicd} cicd-calidad, {n_practicas} practicas-ingenieria. "
            f"portada_numeros creado, portada_pregunta_06 actualizada.",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    eid = conn.execute(
        "SELECT max(id) FROM evento WHERE accion='portada_corregida'"
    ).fetchone()[0]
    print(f"\n[OK] cifras portada unificadas, evento {eid}")
    conn.close()


if __name__ == "__main__":
    main()
