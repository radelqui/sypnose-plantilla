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

    def cambio(e: dict) -> None:
        e.update(modelo=modelo, modelo_fuente="PostModelSwitch", actor=comun.actor_de(cfg, modelo))

    estado = comun.actualizar_estado(sid, cambio)
    ops = [{"op": "actor", "id": estado["actor"], "rol": cfg["carpeta"], "modelo": modelo},
           comun.op_evento(estado["actor"], "modelo_cambiado", f"{entrada.get('from_model')} → {modelo} ({entrada.get('source')})",
                           comun.plan_de(estado, cfg))]
    try:
        comun.emitir(cfg, ops)
    except (comun.RegistroCaido, comun.RegistroRechazo) as e:
        comun.salir_json({"systemMessage": f"Modelo cambiado a {modelo}, pero el registro no lo recogió: {e}"})


if __name__ == "__main__":
    comun.ejecutar(main, lambda m: comun.salir_json({"systemMessage": m}))
