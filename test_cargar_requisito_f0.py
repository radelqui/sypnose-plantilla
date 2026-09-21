"""F0.3: test de validación de comprobacion en cargar_requisito.py.

Verifica que cargar_requisito.py rechaza (exit≠0):
- comprobacion vacía
- literal 'true'
- prosa (texto sin ejecutable conocido)
- pytest sin --cov-fail-under

Y acepta:
- comandos ejecutables reales
- pytest CON --cov-fail-under
- SQL (SELECT, EXPLAIN)
- rutas absolutas/relativas

Sobre COPIA de la BD: --auditar-deuda no debe explotar.

    python3 test_cargar_requisito_f0.py --db copia-registry.db
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cargar_requisito import validar_comprobacion, auditar_deuda


def test_validar_comprobacion():
    """Unit tests para validar_comprobacion."""
    fallos = []

    rechazados = [
        ("", "comprobacion vacia"),
        ("true", "literal true"),
        ("El servicio funciona correctamente", "prosa sin ejecutable"),
        ("Verificar que el endpoint responde", "prosa imperativa"),
        ("CUMPLE si el test pasa", "prosa con CUMPLE"),
        ("pytest tests/", "pytest sin --cov-fail-under"),
        ("python3 -m pytest tests/", "python3 -m pytest sin --cov-fail-under"),
    ]

    for comp, desc in rechazados:
        ok, motivo = validar_comprobacion(comp, exigir_cobertura=True)
        if ok:
            fallos.append(f"DEBIO RECHAZAR [{desc}]: '{comp}' → aceptado")

    aceptados = [
        ("pytest tests/ --cov-fail-under=85", "pytest con --cov-fail-under"),
        ("python3 -m pytest tests/ --cov-fail-under=85", "python3 pytest con --cov-fail-under"),
        ("python3 test_algo.py", "python3 script"),
        ("bash -c 'echo ok'", "bash comando"),
        ("make test", "make"),
        ("curl http://localhost:8000/health", "curl"),
        ("docker build .", "docker"),
        ("gh run list --branch main --limit 1", "gh cli"),
        ("SELECT COUNT(*) FROM tarea", "SQL SELECT"),
        ("git diff --stat esqueleto-v1..HEAD", "git diff"),
        ("./run_tests.sh", "ruta relativa script"),
        ("/usr/bin/python3 test.py", "ruta absoluta"),
        ("~/scripts/check.sh", "ruta con tilde"),
        ("cd /tmp && make test", "cd + make"),
        ("EXPLAIN ANALYZE SELECT 1", "EXPLAIN SQL"),
        ("ENV_VAR=x python3 test.py", "env prefix + ejecutable"),
    ]

    for comp, desc in aceptados:
        ok, motivo = validar_comprobacion(comp, exigir_cobertura=True)
        if not ok:
            fallos.append(f"DEBIO ACEPTAR [{desc}]: '{comp}' → rechazado: {motivo}")

    sin_cobertura = [
        ("pytest tests/", "pytest sin --cov, sin exigir cobertura"),
    ]
    for comp, desc in sin_cobertura:
        ok, motivo = validar_comprobacion(comp, exigir_cobertura=False)
        if not ok:
            fallos.append(f"DEBIO ACEPTAR (sin exigir cobertura) [{desc}]: '{comp}' → rechazado: {motivo}")

    return fallos


def test_auditar_deuda(db_path: Path):
    """Test --auditar-deuda sobre copia de la BD: no debe explotar."""
    copia = db_path.parent / "test-copia-auditoria.db"
    shutil.copy2(db_path, copia)
    try:
        conn = sqlite3.connect(str(copia))
        conn.execute("PRAGMA journal_mode=WAL")
        deuda = auditar_deuda(conn)
        conn.close()
        return deuda
    finally:
        copia.unlink(missing_ok=True)


def test_requisitos_dummy(db_path: Path):
    """Inserta requisitos con comprobaciones malas en una copia y verifica que auditar_deuda los detecta."""
    copia = db_path.parent / "test-copia-dummy.db"
    shutil.copy2(db_path, copia)
    fallos = []
    try:
        conn = sqlite3.connect(str(copia))
        conn.execute("PRAGMA journal_mode=WAL")

        dummies = [
            ("TEST-PROSA", "R0", "Todo funciona bien", "El servicio funciona bien y responde correctamente"),
            ("TEST-TRUE", "R0", "Todo funciona bien", "true"),
            ("TEST-PYTEST-SIN-COV", "R0", "Todo funciona bien", "pytest tests/"),
        ]

        for plan_id, ref, ears, comp in dummies:
            conn.execute(
                "INSERT OR REPLACE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, ref, ears, comp),
            )
        conn.commit()

        deuda = auditar_deuda(conn)
        conn.close()

        ids_deuda = {(d[0], d[1]) for d in deuda}
        for plan_id, ref, ears, comp in dummies:
            if (plan_id, ref) not in ids_deuda:
                fallos.append(f"auditar_deuda no detectó {plan_id}/{ref} (comp='{comp}')")

        conn = sqlite3.connect(str(copia))
        for plan_id, ref, ears, comp in dummies:
            conn.execute("DELETE FROM requisito WHERE plan_id=? AND ref=?", (plan_id, ref))
        conn.commit()
        conn.close()

    finally:
        copia.unlink(missing_ok=True)
    return fallos


def main():
    ap = argparse.ArgumentParser(description="F0.3: test validación comprobacion")
    ap.add_argument("--db", required=True, help="ruta a COPIA de registry.db")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    total_fallos = 0

    print("[1/3] test_validar_comprobacion")
    fallos_vc = test_validar_comprobacion()
    if fallos_vc:
        for f in fallos_vc:
            print(f"  FALLO: {f}")
        total_fallos += len(fallos_vc)
    else:
        print(f"  OK: {7 + 16 + 1} casos pasados (7 rechazos + 16 aceptados + 1 sin_exigir_cobertura)")

    print("\n[2/3] test_auditar_deuda (sobre copia)")
    deuda = test_auditar_deuda(db_path)
    if deuda is not None:
        print(f"  OK: auditar_deuda ejecutado, {len(deuda)} no conformes en la BD actual")
    else:
        print("  FALLO: auditar_deuda devolvió None")
        total_fallos += 1

    print("\n[3/3] test_requisitos_dummy (inserta y detecta en copia)")
    fallos_dummy = test_requisitos_dummy(db_path)
    if fallos_dummy:
        for f in fallos_dummy:
            print(f"  FALLO: {f}")
        total_fallos += len(fallos_dummy)
    else:
        print("  OK: 3 requisitos dummy insertados y detectados por auditar_deuda")

    print(f"\n{'='*60}")
    if total_fallos:
        print(f"[FALLO] {total_fallos} fallos")
        sys.exit(1)
    else:
        print("[OK] F0.3 — 3 baterías, 0 fallos")


if __name__ == "__main__":
    main()
