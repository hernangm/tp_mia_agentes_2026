"""Tests unitarios de SlidingWindowContextPolicy (D-09).

Estos tests ejercitan la política de acotado de contexto en forma directa,
con literales `list[dict]` que replican exactamente las formas de mensaje
que `student_framework/agent.py` construye (ver agent.py líneas 131-138 y
162): un mensaje `assistant` con `tool_calls` va seguido de uno o más
mensajes `role: "tool"` con `tool_call_id`. Viven fuera de
`tests/conformance/` porque prueban la política en aislamiento, antes de
que Plan 02 la conecte a `MyAgent.run()` (ver 01-CONTEXT.md D-09).
"""

from __future__ import annotations

from student_framework.context_policy import SlidingWindowContextPolicy


def _assistant_with_tool_calls(call_id: str) -> dict:
    """Construye un mensaje assistant con tool_calls, forma exacta de agent.py."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "function": {"name": "calculator", "arguments": "{}"}}
        ],
    }


def _tool_result(call_id: str, content: str = "42") -> dict:
    """Construye un mensaje tool result, forma exacta de agent.py."""
    return {"role": "tool", "content": content, "tool_call_id": call_id}


def _user(content: str) -> dict:
    return {"role": "user", "content": content}


# ---------------------------------------------------------------------------
# Modo atómico (atomic_turns=True): nunca separa un tool_call de su tool_result
# ---------------------------------------------------------------------------

def test_atomic_turns_keeps_tool_pairs_together() -> None:
    # Cuatro turnos atómicos: user, (assistant+tool_calls + tool), user, (assistant+tool_calls + tool)
    context = [
        _user("hola"),
        _assistant_with_tool_calls("call-1"),
        _tool_result("call-1"),
        _user("segunda pregunta"),
        _assistant_with_tool_calls("call-2"),
        _tool_result("call-2"),
    ]
    policy = SlidingWindowContextPolicy(atomic_turns=True)

    # max_messages=3 fuerza eviction: el último turno atómico completo
    # (user + assistant+tool_calls + tool = 3 mensajes) apenas entra.
    bounded = policy.handle_context(context, max_messages=3)

    assert len(bounded) <= 3
    # Ningún assistant-con-tool_calls que sobreviva debe quedar sin su tool result emparejado.
    for i, msg in enumerate(bounded):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            call_id = msg["tool_calls"][0]["id"]
            # Debe existir, en algún punto posterior de bounded, el tool result correspondiente.
            matching_tool_msgs = [
                m for m in bounded[i + 1:]
                if m.get("role") == "tool" and m.get("tool_call_id") == call_id
            ]
            assert matching_tool_msgs, (
                "Se encontró un assistant+tool_calls sin su tool result emparejado en el resultado"
            )


# ---------------------------------------------------------------------------
# Modo estricto (atomic_turns=False): corte puro por cantidad, sin pairing
# ---------------------------------------------------------------------------

def test_strict_mode_cuts_by_count() -> None:
    context = [
        _user("m1"),
        _assistant_with_tool_calls("call-1"),
        _tool_result("call-1"),
        _user("m4"),
        _user("m5"),
    ]
    policy = SlidingWindowContextPolicy(atomic_turns=False)

    bounded = policy.handle_context(context, max_messages=3)

    # Sin awareness de pairing: exactamente los últimos max_messages mensajes.
    assert bounded == context[-3:]


# ---------------------------------------------------------------------------
# Presupuesto minúsculo (D-04): el tope de CTX-01 gana sobre el pairing
# ---------------------------------------------------------------------------

def test_tiny_budget_fallback() -> None:
    # El único turno atómico reciente ya mide 3 mensajes (assistant+tool_calls, tool, tool)
    # -- con tool_calls múltiples resueltos en dos tool results separados.
    context = [
        _user("previo, será descartado"),
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call-a", "function": {"name": "calculator", "arguments": "{}"}},
                {"id": "call-b", "function": {"name": "calculator", "arguments": "{}"}},
            ],
        },
        _tool_result("call-a"),
        _tool_result("call-b"),
    ]
    policy = SlidingWindowContextPolicy(atomic_turns=True)

    # max_messages=2 es menor que el turno atómico completo (3 mensajes) -> fallback a corte estricto.
    bounded = policy.handle_context(context, max_messages=2)

    # CTX-01 es innegociable: el resultado nunca supera max_messages, aunque
    # eso implique romper el pairing en este caso degenerado (D-04).
    assert len(bounded) <= 2


# ---------------------------------------------------------------------------
# on_evict: se llama una única vez por handle_context(), batched, solo si hubo eviction
# ---------------------------------------------------------------------------

def test_on_evict_called_once_with_batched_messages() -> None:
    evict_calls: list[list[dict]] = []

    class SpyPolicy(SlidingWindowContextPolicy):
        def on_evict(self, evicted: list[dict]) -> None:
            evict_calls.append(evicted)

    context = [
        _user("m1"),
        _user("m2"),
        _user("m3"),
        _user("m4"),
        _user("m5"),
    ]
    policy = SpyPolicy(atomic_turns=False)

    # Caso 1: hay eviction -> on_evict se llama exactamente una vez, con TODOS los descartados.
    bounded = policy.handle_context(context, max_messages=2)
    assert len(evict_calls) == 1
    assert evict_calls[0] == context[:-2]
    assert bounded == context[-2:]

    # Caso 2: no hay eviction (len(context) <= max_messages) -> on_evict NO se llama.
    evict_calls.clear()
    short_context = [_user("único mensaje")]
    policy.handle_context(short_context, max_messages=5)
    assert evict_calls == []
