"""F0.3 v2: test de validacion de comprobacion en cargar_requisito.py.

Baterias:
(1) validar_comprobacion: 30+ rechazos + 16 aceptados + sin_exigir_cobertura
(2) auditar_deuda: verifica cuenta y mutaciones sobre copia
(3) requisitos dummy: inserta malos, detecta, verifica motivo

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
        ("false", "literal false"),
        ("El servicio funciona correctamente", "prosa sin ejecutable"),
        ("Verificar que el endpoint responde", "prosa imperativa"),
        ("CUMPLE si el test pasa", "prosa con CUMPLE"),
        ("pytest tests/", "pytest sin --cov-fail-under"),
        ("python3 -m pytest tests/", "python3 -m pytest sin --cov-fail-under"),
        # (1) shell metacharacter bypasses
        ("pytest tests/  # --cov-fail-under=85", "flag en comentario (#)"),
        ("pytest tests/ --cov-fail-under=85 || true", "supresion de error (||)"),
        ("pytest tests/ --cov-fail-under=85 ; exit 0", "separador (;)"),
        ("pytest tests/ --cov-fail-under=85 && echo ok", "encadenamiento (&&)"),
        ("pytest tests/ --cov-fail-under=85 > /dev/null", "redireccion stdout"),
        ("pytest tests/ --cov-fail-under=85 2>/dev/null", "redireccion stderr"),
        ("python3 test.py < input.txt", "redireccion stdin"),
        ("pytest tests/\ntrue", "salto de linea con true"),
        # (1) comandos triviales
        ("echo CUMPLE", "echo trivial"),
        ("test 1 = 1", "test trivial"),
        (": noop", "null command (:)"),
        ("bash -c true", "bash -c trivial"),
        ("sh -c 'exit 0'", "sh -c exit 0"),
        ("bash -c echo", "bash -c echo"),
        # (1) --cov-fail-under umbral
        ("pytest tests/ --cov-fail-under=0", "umbral 0"),
        ("pytest tests/ --cov-fail-under=50", "umbral 50"),
        ("pytest tests/ --cov-fail-under=84", "umbral 84 (justo debajo)"),
        # (3) seleccion de tests
        ("pytest tests/ --cov-fail-under=85 -k test_one", "-k selecciona test"),
        ("pytest tests/test_x.py::test_one --cov-fail-under=85", ":: selecciona test"),
        # (2) prosa con primer token ejecutable
        ("SELECT COUNT(*) FROM tarea WHERE progreso='espera_firma' → 0",
         "SQL con flecha unicode"),
        ('git log --format=%B | grep -c "^Chat:" == git rev-list --count',
         "git con comparacion =="),
        ("tests/integracion/README.md (comando psql) ejecutado en CI",
         "ruta con parentesis prosa"),
        ("gh run list --limit 1 + gh run view <id> (job deploy)",
         "gh con < redireccion/prosa"),
        # pipe a trivial
        ("curl -sf url | echo CUMPLE", "pipe a echo trivial"),
        ("git log | true", "pipe a true"),
    ]

    for comp, desc in rechazados:
        ok, motivo = validar_comprobacion(comp, exigir_cobertura=True)
        if ok:
            fallos.append(f"DEBIO RECHAZAR [{desc}]: '{comp}' → aceptado")

    aceptados = [
        ("pytest tests/ --cov-fail-under=85", "pytest con --cov-fail-under"),
        ("python3 -m pytest tests/ --cov-fail-under=85", "python3 pytest con --cov-fail-under"),
        ("pytest tests/ --cov-fail-under=90", "umbral 90"),
        ("pytest tests/ --cov-fail-under=100", "umbral 100"),
        ("python3 test_algo.py", "python3 script"),
        ("make test", "make"),
        ("curl -sf http://localhost:8000/health", "curl"),
        ("docker build .", "docker"),
        ("gh run list --branch main --limit 1", "gh cli"),
        ("SELECT COUNT(*) FROM tarea", "SQL SELECT"),
        ("git diff --stat esqueleto-v1..HEAD", "git diff"),
        ("./run_tests.sh", "ruta relativa script"),
        ("/usr/bin/python3 test.py", "ruta absoluta"),
        ("~/scripts/check.sh", "ruta con tilde"),
        ("EXPLAIN ANALYZE SELECT 1", "EXPLAIN SQL"),
        ("ENV_VAR=x python3 test.py", "env prefix + ejecutable"),
        ('python3 -c "assert 1 > 0"', "> dentro de comillas OK"),
        ("grep -E 'readOnlyRootFilesystem: true' k8s/deployment.yaml", "grep con patron"),
        ("curl -sf url | grep -q pattern", "pipe legitimo"),
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

    return len(rechazados), len(aceptados), len(sin_cobertura), fallos


def test_auditar_deuda(db_path: Path):
    """Test --auditar-deuda: verifica que detecta mutaciones."""
    copia = db_path.parent / "test-copia-auditoria.db"
    shutil.copy2(db_path, copia)
    fallos = []
    try:
        conn = sqlite3.connect(str(copia))
        conn.execute("PRAGMA journal_mode=WAL")

        deuda_base = auditar_deuda(conn)
        n_base = len(deuda_base)

        mutantes = [
            ("TEST-MUT-PROSA", "R0", "Todo funciona bien", "El servicio funciona correctamente"),
            ("TEST-MUT-TRIVIAL", "R0", "Test trivial", "echo CUMPLE"),
            ("TEST-MUT-COMMENT", "R0", "Test comment bypass", "pytest tests/ # --cov-fail-under=85"),
        ]
        for plan_id, ref, ears, comp in mutantes:
            conn.execute(
                "INSERT OR REPLACE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, ref, ears, comp),
            )
        conn.commit()

        deuda_mut = auditar_deuda(conn)
        n_mut = len(deuda_mut)

        if n_mut < n_base + len(mutantes):
            fallos.append(
                f"auditar_deuda no detecto mutantes: base={n_base}, "
                f"con {len(mutantes)} mutantes={n_mut} (esperado >={n_base + len(mutantes)})"
            )

        ids_mut = {(d[0], d[1]) for d in deuda_mut}
        for plan_id, ref, ears, comp in mutantes:
            if (plan_id, ref) not in ids_mut:
                fallos.append(f"mutante {plan_id}/{ref} no detectado (comp='{comp}')")

        for plan_id, ref, ears, comp in mutantes:
            conn.execute("DELETE FROM requisito WHERE plan_id=? AND ref=?", (plan_id, ref))
        conn.commit()

        deuda_post = auditar_deuda(conn)
        n_post = len(deuda_post)
        if n_post != n_base:
            fallos.append(f"tras borrar mutantes: n_post={n_post} != n_base={n_base}")

        conn.close()
        return n_base, n_mut, fallos
    finally:
        copia.unlink(missing_ok=True)


def test_requisitos_dummy(db_path: Path):
    """Inserta requisitos malos, verifica que auditar_deuda los detecta con motivo correcto."""
    copia = db_path.parent / "test-copia-dummy.db"
    shutil.copy2(db_path, copia)
    fallos = []
    try:
        conn = sqlite3.connect(str(copia))
        conn.execute("PRAGMA journal_mode=WAL")

        dummies = [
            ("TEST-PROSA", "R0", "Todo funciona bien", "El servicio funciona correctamente",
             "parece prosa"),
            ("TEST-TRIVIAL", "R0", "Test trivial", "echo ok",
             "comando trivial"),
            ("TEST-PYTEST-SIN-COV", "R0", "Test pytest", "pytest tests/",
             "bateria incompleta"),
            ("TEST-COMMENT", "R0", "Test comment", "pytest tests/ # --cov-fail-under=85",
             "comentario"),
            ("TEST-UMBRAL", "R0", "Test umbral", "pytest tests/ --cov-fail-under=50",
             "umbral insuficiente"),
        ]

        for plan_id, ref, ears, comp, _ in dummies:
            conn.execute(
                "INSERT OR REPLACE INTO requisito (plan_id, ref, ears, comprobacion) VALUES (?,?,?,?)",
                (plan_id, ref, ears, comp),
            )
        conn.commit()

        deuda = auditar_deuda(conn)
        conn.close()

        ids_deuda = {}
        for d in deuda:
            ids_deuda[(d[0], d[1])] = d[3]

        for plan_id, ref, ears, comp, motivo_esperado in dummies:
            if (plan_id, ref) not in ids_deuda:
                fallos.append(f"auditar_deuda no detecto {plan_id}/{ref} (comp='{comp}')")
            else:
                motivo_real = ids_deuda[(plan_id, ref)]
                if motivo_esperado not in motivo_real:
                    fallos.append(
                        f"{plan_id}/{ref}: motivo esperado contiene '{motivo_esperado}', "
                        f"real='{motivo_real}'"
                    )

        conn = sqlite3.connect(str(copia))
        for plan_id, ref, ears, comp, _ in dummies:
            conn.execute("DELETE FROM requisito WHERE plan_id=? AND ref=?", (plan_id, ref))
        conn.commit()
        conn.close()

    finally:
        copia.unlink(missing_ok=True)
    return fallos


def main():
    ap = argparse.ArgumentParser(description="F0.3 v2: test validacion comprobacion")
    ap.add_argument("--db", required=True, help="ruta a COPIA de registry.db")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        sys.exit(f"[FALLO] {db_path} no existe")

    total_fallos = 0

    print("[1/3] test_validar_comprobacion")
    n_rech, n_acep, n_sin, fallos_vc = test_validar_comprobacion()
    if fallos_vc:
        for f in fallos_vc:
            print(f"  FALLO: {f}")
        total_fallos += len(fallos_vc)
    else:
        print(f"  OK: {n_rech} rechazos + {n_acep} aceptados + {n_sin} sin_exigir = "
              f"{n_rech + n_acep + n_sin} casos, 0 fallos")

    print("\n[2/3] test_auditar_deuda (mutaciones sobre copia)")
    n_base, n_mut, fallos_ad = test_auditar_deuda(db_path)
    if fallos_ad:
        for f in fallos_ad:
            print(f"  FALLO: {f}")
        total_fallos += len(fallos_ad)
    else:
        print(f"  OK: base={n_base} no conformes, con 3 mutantes={n_mut}, delta=+{n_mut - n_base}")

    print("\n[3/3] test_requisitos_dummy (inserta, detecta, verifica motivo)")
    fallos_dummy = test_requisitos_dummy(db_path)
    if fallos_dummy:
        for f in fallos_dummy:
            print(f"  FALLO: {f}")
        total_fallos += len(fallos_dummy)
    else:
        print("  OK: 5 dummies insertados, detectados con motivo correcto")

    print(f"\n{'='*60}")
    if total_fallos:
        print(f"[FALLO] {total_fallos} fallos")
        sys.exit(1)
    else:
        print(f"[OK] F0.3 v2 — 3 baterias, 0 fallos")


if __name__ == "__main__":
    main()
