"""Tests de comportamiento para el manejo resiliente de errores de tools (Fase 2).

Cubre ERR-01..ERR-04: reintento con backoff exponencial, degradación a una
observación role:tool legible, continuación del loop tras agotar reintentos, y
visibilidad del fallo en `AgentResult.steps`. Vive fuera de `tests/conformance/`
porque ejercita un comportamiento no cubierto por el contrato de conformidad
oficial, siguiendo el patrón de `tests/test_context_policy.py`.
"""

from __future__ import annotations

import json
from typing import Annotated

import pytest
from pydantic import Field

from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall, ToolSchema

from student_framework import build_agent
from student_framework.agent import MAX_TOOL_ATTEMPTS, RETRY_BACKOFF_BASE


class _FlakyTool:
    """Tool de test que falla las primeras `fail_times` invocaciones.

    Si `always=True` falla en cada invocación, sin importar `fail_times` —
    usado para probar el camino de agotamiento de reintentos (ERR-02/03/04).
    """

    def __init__(self, fail_times: int = 0, always: bool = False) -> None:
        self._fail_times = fail_times
        self._always = always
        self.calls = 0

    def __call__(self, text: str) -> str:
        self.calls += 1
        if self._always or self.calls <= self._fail_times:
            raise RuntimeError("boom")
        return "ok"


def _flaky_tool_signature(
    text: Annotated[str, Field(description="Texto arbitrario de entrada.")],
) -> str:
    """Herramienta de test que puede fallar de forma controlada.

    Definida a nivel de módulo (no anidada) para que `get_type_hints` resuelva
    `Annotated`/`Field` contra los globals de este módulo — con
    `from __future__ import annotations` los anotadores quedan como strings y
    `ToolSchema.from_callable` los evalúa perezosamente vía `fn.__globals__`.
    """
    raise NotImplementedError("placeholder solo para derivar el schema")


def _make_flaky_schema() -> ToolSchema:
    """Construye el ToolSchema de _FlakyTool con la firma que exige from_callable.

    El callable realmente despachado por el agente es la instancia de
    _FlakyTool (registrada aparte); esta función solo deriva `parameters`
    a partir de una firma compatible, modelada sobre calculator.py.
    """
    return ToolSchema.from_callable(_flaky_tool_signature, name="flaky_tool")


def _tool_call_then_final_text() -> list[LLMResponse]:
    """Dos respuestas programadas: 1 turno con tool_call + 1 turno de texto final.

    Los reintentos internos de la tool NO consumen respuestas del mock — ocurren
    dentro de un único despacho de tool_call, sin llamadas adicionales a chat().
    Por eso dos respuestas alcanzan tanto para el caso "éxito al reintentar" como
    para el caso "agota reintentos".
    """
    return [
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="c1", name="flaky_tool", arguments=json.dumps({"text": "x"})),
            ],
        ),
        LLMResponse(content="respuesta final"),
    ]


def test_tool_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-01: la tool falla 2 veces y tiene éxito en el 3er intento."""
    sleeps: list[float] = []
    monkeypatch.setattr(
        "student_framework.agent.time.sleep", lambda delay: sleeps.append(delay)
    )

    tool = _FlakyTool(fail_times=2)
    schema = _make_flaky_schema()
    mock = MockLLMClient(_tool_call_then_final_text())
    agent = build_agent({"llm_client": mock})
    agent.register_tool(tool, schema)

    result = agent.run("dispara la tool flaky")

    assert result.answer == "respuesta final"
    assert tool.calls == 3
    assert len(result.steps) == 1
    assert result.steps[0].error is None
    assert result.steps[0].tool_output == "ok"
    # Backoff exponencial: base, base*2 — exactamente 2 sleeps (entre los 3 intentos).
    assert sleeps == [RETRY_BACKOFF_BASE, RETRY_BACKOFF_BASE * 2]


def test_tool_exhausts_retries_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """ERR-02/ERR-03: agotados los intentos, el fallo es legible y no crashea run()."""
    sleeps: list[float] = []
    monkeypatch.setattr(
        "student_framework.agent.time.sleep", lambda delay: sleeps.append(delay)
    )

    tool = _FlakyTool(always=True)
    schema = _make_flaky_schema()
    mock = MockLLMClient(_tool_call_then_final_text())
    agent = build_agent({"llm_client": mock})
    agent.register_tool(tool, schema)

    # No debe levantar excepción — run() debe degradar en vez de propagar.
    result = agent.run("dispara la tool flaky")

    assert tool.calls == MAX_TOOL_ATTEMPTS
    assert len(result.steps) == 1
    assert result.steps[0].error is not None
    assert "Traceback" not in result.steps[0].error
    assert "falló tras" in result.steps[0].error

    # La observación role:tool con el mensaje legible es lo que el LLM vio en el
    # 2do chat() (turno siguiente a la falla).
    second_call_payload = str(mock.calls[1]["messages"])
    assert "falló tras" in second_call_payload

    assert sleeps == [RETRY_BACKOFF_BASE, RETRY_BACKOFF_BASE * 2]


@pytest.mark.parametrize(
    "bad_arguments",
    ["not json", json.dumps([1, 2, 3])],
    ids=["invalid-json-syntax", "non-dict-json-shape"],
)
def test_malformed_tool_arguments_fail_fast_without_retry(
    monkeypatch: pytest.MonkeyPatch, bad_arguments: str
) -> None:
    """T-02-03: JSON inválido o de forma no-mapping no se reintenta -- falla rápido."""
    sleeps: list[float] = []
    monkeypatch.setattr(
        "student_framework.agent.time.sleep", lambda delay: sleeps.append(delay)
    )

    tool = _FlakyTool(fail_times=0)  # tendría éxito si llegara a invocarse
    schema = _make_flaky_schema()
    mock = MockLLMClient(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="flaky_tool", arguments=bad_arguments)],
            ),
            LLMResponse(content="respuesta final"),
        ]
    )
    agent = build_agent({"llm_client": mock})
    agent.register_tool(tool, schema)

    result = agent.run("dispara la tool con argumentos rotos")

    assert tool.calls == 0  # nunca se invoca -- falla antes de llegar a la tool
    assert sleeps == []  # sin backoff -- no es un fallo transitorio
    assert result.steps[0].error is not None
    assert "Argumentos inválidos" in result.steps[0].error


def test_run_continues_after_tool_failure() -> None:
    """ERR-02/ERR-04: una tool_call agotada no aborta el resto del turno."""
    tool = _FlakyTool(always=True)
    schema = _make_flaky_schema()
    mock = MockLLMClient(_tool_call_then_final_text())
    agent = build_agent({"llm_client": mock})
    agent.register_tool(tool, schema)

    result = agent.run("dispara la tool flaky")

    # El loop siguió hasta la respuesta final en texto pese a la falla de la tool.
    assert result.answer == "respuesta final"
    assert mock.call_count == 2
    # El fallo sigue visible en steps — nunca se descarta silenciosamente (ERR-04).
    assert result.steps[0].error is not None
