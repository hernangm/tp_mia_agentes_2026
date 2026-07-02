#!/usr/bin/env python3
"""Demo de M2 contra un proveedor real (statefulness + structured_call).

No es un test de conformidad ni forma parte de la entrega — es un script
manual para ver en vivo, contra un LLM real, lo que `tests/conformance/test_m2.py`
ya prueba con `MockLLMClient`: memoria entre turnos (SESS-01), `structured_call`
con salida validada (STRUCT-01..04), y que ambos comparten el mismo historial
de conversación (SESS-02).

Requiere credenciales configuradas (ver scripts/set-env.ps1 o las variables
de entorno de ENUNCIADO_M1.md — BEDROCK_MODEL_ID/AWS_* u OLLAMA_HOST/OLLAMA_MODEL).

Uso, desde la raíz del repo:

    . .\\scripts\\set-env.ps1
    python scripts\\demo_m2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel


def _add_repo_root_to_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


def _print_tokens(result) -> None:
    # AgentResult.input_tokens/output_tokens son el total de ESTA llamada a
    # run() (CTX-02), no un acumulado de sesión — por eso se imprimen
    # por turno en vez de una sola vez al final.
    print(f"  (tokens: input={result.input_tokens}, output={result.output_tokens})")


def demo_statefulness() -> None:
    print("=== Statefulness (SESS-01): dos llamadas a run() sobre la misma instancia ===")
    agent = build_agent()

    r1 = agent.run("Recorda este código secreto: ALFA-7. Solo confirmá que lo anotaste.")
    print("Turno 1:", r1.answer)
    _print_tokens(r1)

    r2 = agent.run("¿Cuál era el código secreto que te pedí que recordaras?")
    print("Turno 2:", r2.answer)
    _print_tokens(r2)
    print()


def demo_structured_call() -> None:
    print("=== structured_call (STRUCT-01..04): salida validada contra un schema Pydantic ===")

    class Persona(BaseModel):
        nombre: str
        edad: int
        profesion: str

    agent = build_agent()
    persona = agent.structured_call(
        prompt=(
            "Generame los datos de un personaje ficticio: un ingeniero de software "
            "argentino de unos 30 años. Inventá un nombre."
        ),
        schema=Persona,
    )
    print("Tipo devuelto:", type(persona).__name__)
    print("Instancia:", persona.model_dump_json(indent=2))
    # Nota: structured_call() no expone tokens — devuelve la instancia del
    # schema (contrato fijo de Agent.structured_call en mia_agents/protocols.py),
    # no un AgentResult, y run_structured_call() tampoco los acumula
    # internamente. A diferencia de run(), no hay input_tokens/output_tokens
    # para imprimir acá.
    print("  (structured_call no expone tokens — ver nota arriba)")
    print()


def demo_structured_call_stateful() -> None:
    print("=== SESS-02: structured_call comparte contexto con run() ===")

    class Respuesta(BaseModel):
        respuesta: str

    agent = build_agent()
    r1 = agent.run("Mi color favorito es el verde esmeralda. Solo confirmá que lo escuchaste.")
    _print_tokens(r1)  # el run() previo sí expone tokens
    resp = agent.structured_call(
        prompt="¿Cuál dije que era mi color favorito? Respondé solo con esa info.",
        schema=Respuesta,
    )
    print("Respuesta estructurada:", resp.model_dump_json(indent=2))


if __name__ == "__main__":
    _add_repo_root_to_path()
    from student_framework import build_agent  # noqa: E402 (import tras sys.path fix)

    demo_statefulness()
    demo_structured_call()
    demo_structured_call_stateful()
