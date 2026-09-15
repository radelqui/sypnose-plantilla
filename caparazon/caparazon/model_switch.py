"""PostModelSwitch: el actor IA:<carpeta>:<modelo> sigue al modelo real cuando se cambia con /model."""
from __future__ import annotations

import comun


def main() -> None:
    entrada = comun.leer_stdin()
    cfg = comun.config()
    sid = entrada.get("session_id") or "sin-sesion"
    modelo = comun.modelo_limpio(entrada.get("to_model"))
    if not modelo or comun.leer_estado(sid) is None:
        return
    estado = comun.actualizar_estado(sid, lambda e: e.update(modelo=modelo, modelo_fuente="PostModelSwitch",
                                                             actor=comun.actor_de(cfg, modelo)))
    comun.encolar(sid, [{"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": modelo},
                        comun.op_evento(estado["actor"], "modelo_cambiado", f"{entrada.get('from_model')} → {modelo} ({entrada.get('source')})",
                                        comun.plan_de(estado, cfg))])


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m}))
