"""Carga datos de portada faltantes para la vista pública.

1. Corrige por_que:T01 truncado (retira viejo, inserta texto completo)
2. Convierte defensa:01-12 → portada_pregunta_01-12 (JSON)
3. Crea portada_recorrido (5 pasos de navegación)
4. Crea contrato_banco (CONTRATO-BANCO.md@sha)

    python3 cargar_portada_vista.py --db ~/sypnose-f1/registry.db [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from barrera import backup_registro, verificar_canonicos_registrados, verificar_repo_limpio

ACTOR = "IA:05-arquitecto-sypnose:claude-opus-4-6"
FUENTE = "plantilla/cargar_portada_vista.py"

RAG_SOL = "sol:coforge:rag-banking-agent"
PLANTILLA_SOL = "sol:coforge:sypnose-plantilla"
CEH_SOL = "sol:coforge:como-estoy-hecho"

POR_QUE_T01_COMPLETO = (
    "Mantener un backend Python en producción significa, ante todo, que el servicio "
    "nunca mienta sobre su propio estado: si `ENGINE_MODE` pide un motor real (`rag` "
    "o `agent`) y faltan las credenciales de los modelos de frontera "
    "(`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`), el pod no puede anunciarse \"listo\" y "
    "luego fallar en silencio en cada petición — eso es exactamente lo que un banco "
    "no puede permitirse (ver hallazgo B1 de 07-verificador sobre el commit "
    "`97ede33`, corregido en `c6e1407`)."
)

CONTRATO_SHA = "f57a252"

RECORRIDO = {
    "portada": "Portada con las tres capas del proyecto (gobierno, ingeniería, ejecución), los números clave y la tecnología intercambiable.",
    "linea": "Cada línea de la oferta: qué se pidió, qué se hizo, con qué archivos y qué pruebas.",
    "solucion": "La solución completa: repositorio, stack tecnológico, explorador de archivos y relaciones.",
    "como": "Cómo se construyó: agentes, modelos, herramientas y coste por turno.",
    "estado": "Estado actual: requisitos verificados, tareas cerradas, líneas firmadas.",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def retirar_vigente(conn, nodo_id: str, campo: str, valor_actual: str | None = None) -> int:
    if valor_actual is not None:
        return conn.execute(
            "UPDATE afirmacion SET vigente=0 WHERE nodo_id=? AND campo=? AND vigente=1 AND valor=?",
            (nodo_id, campo, valor_actual),
        ).rowcount
    return conn.execute(
        "UPDATE afirmacion SET vigente=0 WHERE nodo_id=? AND campo=? AND vigente=1",
        (nodo_id, campo),
    ).rowcount


def insertar(conn, nodo_id: str, campo: str, valor: str, ts: str) -> None:
    conn.execute(
        "INSERT INTO afirmacion (nodo_id, campo, valor, certeza, fuente, actor_id, cuando, vigente) "
        "VALUES (?, ?, ?, 'observado', ?, ?, ?, 1)",
        (nodo_id, campo, valor, FUENTE, ACTOR, ts),
    )


def upsert(conn, nodo_id: str, campo: str, valor: str, ts: str) -> str:
    row = conn.execute(
        "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo=? AND vigente=1",
        (nodo_id, campo),
    ).fetchone()
    if row and row[1] == valor:
        return "skip"
    if row:
        conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (row[0],))
    insertar(conn, nodo_id, campo, valor, ts)
    return "update" if row else "new"


def parsear_defensa(texto: str) -> dict:
    m_p = re.match(r"P:\s*(.+?)(?:\nR:)", texto, re.DOTALL)
    m_r = re.search(r"R:\s*(.+?)(?:\nPrueba:)", texto, re.DOTALL)
    m_pr = re.search(r"Prueba:\s*(.+)", texto, re.DOTALL)
    return {
        "pregunta": m_p.group(1).strip() if m_p else texto.split("\n")[0],
        "respuesta": m_r.group(1).strip() if m_r else "",
        "prueba": m_pr.group(1).strip() if m_pr else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    verificar_repo_limpio()

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")

    verificar_canonicos_registrados(conn)

    if not args.dry_run:
        backup_registro(conn, db_path, "portada-vista")

    conn.execute("BEGIN IMMEDIATE")
    try:
        ts = ahora()
        cambios = []

        # --- 1. Corregir por_que:T01 truncado ---
        old = conn.execute(
            "SELECT id, valor FROM afirmacion WHERE nodo_id=? AND campo='por_que:T01' AND vigente=1",
            (RAG_SOL,),
        ).fetchone()
        if old and old[1] != POR_QUE_T01_COMPLETO:
            conn.execute("UPDATE afirmacion SET vigente=0 WHERE id=?", (old[0],))
            insertar(conn, RAG_SOL, "por_que:T01", POR_QUE_T01_COMPLETO, ts)
            cambios.append("por_que:T01 corregido")
            print(f"  [por_que:T01] truncado retirado (id {old[0]}), texto completo insertado")
        elif not old:
            insertar(conn, RAG_SOL, "por_que:T01", POR_QUE_T01_COMPLETO, ts)
            cambios.append("por_que:T01 nuevo")
            print("  [por_que:T01] insertado (no existía)")
        else:
            print("  [por_que:T01] ya correcto — skip")

        # --- 2. Convertir defensa:01-12 → portada_pregunta_01-12 ---
        defensas = conn.execute(
            "SELECT campo, valor FROM afirmacion WHERE nodo_id=? AND campo LIKE 'defensa:%' AND vigente=1 ORDER BY campo",
            (RAG_SOL,),
        ).fetchall()
        preguntas_ok = 0
        for campo_def, valor_def in defensas:
            num = campo_def.split(":")[1]
            campo_preg = f"portada_pregunta_{num}"
            obj = parsear_defensa(valor_def)
            json_val = json.dumps(obj, ensure_ascii=False)
            res = upsert(conn, RAG_SOL, campo_preg, json_val, ts)
            if res != "skip":
                preguntas_ok += 1
                print(f"  [{campo_preg}] {res}: {obj['pregunta'][:60]}...")
            else:
                print(f"  [{campo_preg}] skip (ya existe)")
        if preguntas_ok:
            cambios.append(f"{preguntas_ok} portada_pregunta")

        # --- 3. Crear portada_recorrido ---
        recorrido_ok = 0
        for paso, texto in RECORRIDO.items():
            campo_nuevo = f"portada_recorrido.{paso}"
            campo_viejo = f"portada_recorrido_{paso}"
            retirar_vigente(conn, RAG_SOL, campo_viejo)
            campo = campo_nuevo
            res = upsert(conn, RAG_SOL, campo, texto, ts)
            if res != "skip":
                recorrido_ok += 1
                print(f"  [recorrido.{paso}] {res}")
            else:
                print(f"  [recorrido.{paso}] skip")
        if recorrido_ok:
            cambios.append(f"{recorrido_ok} recorrido")

        # --- 4. Crear contrato_banco ---
        contrato_val = f"CONTRATO-BANCO.md@{CONTRATO_SHA}"
        retirar_vigente(conn, PLANTILLA_SOL, "contrato_banco")
        res = upsert(conn, RAG_SOL, "contrato_banco", contrato_val, ts)
        if res != "skip":
            cambios.append("contrato_banco")
            print(f"  [contrato_banco] {res}: {contrato_val}")
        else:
            print(f"  [contrato_banco] skip")

        # --- Evento ---
        if cambios:
            conn.execute(
                "INSERT INTO evento (cuando, actor, accion, nodo_id, plan_id, detalle) "
                "VALUES (?, ?, 'cargar_portada_vista', NULL, NULL, ?)",
                (ts, ACTOR, "; ".join(cambios)),
            )

        conn.execute("ROLLBACK" if args.dry_run else "COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    print(f"\n[OK] {len(cambios)} grupos de cambios: {'; '.join(cambios) if cambios else 'ninguno'}")
    if args.dry_run:
        print("--dry-run: transacción deshecha")
    conn.close()


if __name__ == "__main__":
    main()
