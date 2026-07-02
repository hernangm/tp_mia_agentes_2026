"""Tests de comportamiento para la statefulness de `structured_call` (Fase 3).

Cubre SESS-02 para `structured_call`: llamadas sucesivas sobre la misma
instancia deben compartir el mismo historial (`self._context`) que usa
`run()`. Este comportamiento NO está cubierto por la suite inmutable de
conformidad (`tests/conformance/test_m2.py`) — esa suite verifica la tool
sintética, la reparación y el agotamiento de reintentos, pero no la
statefulness entre llamadas a `structured_call`. Vive fuera de
`tests/conformance/` siguiendo el patrón de `tests/test_context_policy.py`
y `tests/test_tool_error_handling.py`.
"""

from __future__ import annotations

import json

from mia_agents.testing import MockLLMClient
from mia_agents.tool_schema import FINAL_RESULT_TOOL_NAME
from mia_agents.types import LLMResponse, ToolCall

from student_framework import build_agent


def _final_result_response(
    arguments: dict[str, object],
    *,
    call_id: str = "fr-1",
) -> LLMResponse:
    """Arma una respuesta con un tool_call a final_result (espeja test_m2.py)."""
    return LLMResponse(
        content=None,
        tool_calls=[
            ToolCall(
                id=call_id,
                name=FINAL_RESULT_TOOL_NAME,
                arguments=json.dumps(arguments),
            )
        ],
    )


def test_structured_call_is_stateful_across_calls() -> None:
    """Dos llamadas sucesivas a structured_call() sobre la misma instancia
    deben compartir historial (SESS-02).

    Se verifica que el payload de mensajes de la SEGUNDA llamada incluya
    contenido de la PRIMERA — prueba directa de que structured_call lee y
    escribe sobre self._context, el mismo mecanismo que usa run().
    """
    from pydantic import BaseModel

    class Answer(BaseModel):
        result: int

    mock = MockLLMClient(
        [
            _final_result_response({"result": 1}),
            _final_result_response({"result": 2}, call_id="fr-2"),
        ]
    )
    agent = build_agent({"llm_client": mock})

    agent.structured_call(prompt="primer structured turno: recuerda BETA-9", schema=Answer)
    agent.structured_call(prompt="segundo structured turno: ¿cuál era el código?", schema=Answer)

    payload = str(mock.calls[1]["messages"])
    assert "primer structured turno" in payload or "BETA-9" in payload, (
        "el segundo structured_call debe ver el contenido del primero — "
        "structured_call debe ser estatal (SESS-02)"
    )


def test_structured_call_shares_context_with_run() -> None:
    """Un turno de run() seguido de structured_call() sobre la misma
    instancia: el payload del structured_call debe incluir el contenido
    del turno de run() previo — ambos métodos comparten un único historial.
    """
    from pydantic import BaseModel

    class Answer(BaseModel):
        result: int

    mock = MockLLMClient(
        [
            LLMResponse(content="respuesta del turno run()"),
            _final_result_response({"result": 7}),
        ]
    )
    agent = build_agent({"llm_client": mock})

    agent.run("turno de run(): recuerda GAMMA-3")
    agent.structured_call(prompt="turno structured: ¿cuál era el código?", schema=Answer)

    payload = str(mock.calls[1]["messages"])
    assert "turno de run()" in payload or "GAMMA-3" in payload, (
        "structured_call debe ver el contenido del turno de run() previo — "
        "run() y structured_call comparten self._context"
    )
