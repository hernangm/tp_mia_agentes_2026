"""Salida estructurada garantizada (STRUCT-01..04, SESS-02).

Aísla la lógica de `structured_call` en una función libre en vez de un método
de `MyAgent`: las dependencias (cliente LLM, historial compartido, política de
contexto) quedan explícitas en la firma en lugar de implícitas en `self`, lo
que la hace testeable sin construir un `MyAgent` completo y deja el mecanismo
de reparación (loop de `chat()` + validación + reintento) visible como una
unidad separada del bucle de `run()` — son dos condiciones de parada distintas
(texto libre vs. `final_result` validado) que conviene no mezclar en una
misma clase larga.

`run_structured_call` recibe `context` por referencia y lo muta con
`.append(...)` — no lo copia ni lo retorna — porque es el MISMO
`self._context` que usa `run()` (SESS-02): las apariciones agregadas acá
quedan visibles para la próxima llamada a `run()` o `structured_call()` sobre
la misma instancia sin que `MyAgent` tenga que sincronizar dos historiales.
"""

from __future__ import annotations

import json
from typing import Any

from mia_agents.protocols import LLMClient
from mia_agents.tool_schema import FINAL_RESULT_TOOL_NAME, final_result_tool_schema

from student_framework.context_policy import ContextPolicy


def run_structured_call(
    llm: LLMClient,
    context: list[dict],
    context_policy: ContextPolicy,
    max_history_messages: int,
    system_prompt: str,
    prompt: str,
    schema: Any,
    max_repair_attempts: int = 2,
) -> Any:
    """Pide al LLM una respuesta validada contra `schema`, con reparación.

    Obligatorio: herramienta sintética `final_result` (ver
    `mia_agents.tool_schema.final_result_tool_schema` / `FINAL_RESULT_TOOL_NAME`).
    Se ofrece esa tool al LLM, se validan los `arguments` del `tool_call` y se
    reintenta con contexto de reparación si el modelo responde con texto
    libre, una tool distinta, o argumentos inválidos.

    - Cada llamada a `chat()` dentro de esta función pasa
      `tools=[final_result_tool_schema(schema)]` — nunca las tools de negocio
      del agente (STRUCT-01).
    - Termina solo cuando llega un `tool_call` a `final_result` cuyos
      argumentos validan con `schema.model_validate(...)` (STRUCT-02).
    - Reintenta hasta `max_repair_attempts` incluyendo el fallo en los
      mensajes (STRUCT-03).
    - Si tras los reintentos sigue fallando, levanta una excepción limpia —
      nunca devuelve valores parciales ni `None` (STRUCT-04).
    """
    # SESS-02: se reutiliza el MISMO `context` que usa run() (pasado por
    # referencia), no una lista local — así una llamada posterior a
    # structured_call() o a run() sobre la misma instancia ve este prompt.
    context.append({"role": "user", "content": prompt})

    # El ToolSchema sintético se deriva UNA sola vez del schema pydantic; se
    # ofrece en cada chat() de esta función y nunca junto a las tools de
    # negocio (STRUCT-01): el LLM no debe poder invocar herramientas de
    # negocio durante una llamada estructurada.
    final_tool = final_result_tool_schema(schema)

    # Se recuerda el último motivo de fallo para incluirlo en el mensaje de
    # excepción si se agotan los intentos (mensaje legible, sin traceback).
    last_error: str | None = None

    # max_repair_attempts cuenta REPARACIONES, no intentos totales (a
    # diferencia de MAX_TOOL_ATTEMPTS de run(), que cuenta intentos totales).
    # Por eso el rango es max_repair_attempts + 1: 1 llamada inicial + N
    # reparaciones = N+1 llamadas a chat() como máximo. Con
    # max_repair_attempts=2 esto da exactamente 3 chat().
    for _ in range(max_repair_attempts + 1):
        # Se acota el historial en cada intento, igual que run() (CTX-01) —
        # el tope de max_history_messages vale también acá.
        bounded = context_policy.handle_context(context, max_history_messages)
        resp = llm.chat(
            messages=bounded,
            tools=[final_tool],
            system=system_prompt,
        )

        # Se busca específicamente un tool_call a "final_result"; cualquier
        # otro nombre (alucinado) o texto libre sin tool_calls es un fallo.
        final_call = next(
            (tc for tc in (resp.tool_calls or []) if tc.name == FINAL_RESULT_TOOL_NAME),
            None,
        )

        if final_call is None:
            # STRUCT-02/03: el modelo no cerró con final_result — texto libre
            # o una tool_call a otro nombre. No hay nada que validar; se
            # arma reparación.
            last_error = (
                "El modelo no llamó a final_result; respondió con texto libre "
                "o una tool incorrecta."
            )
            # Se vuelca el turno del asistente tal cual lo vio el modelo, con
            # los tool_calls serializados al mismo formato dict que usa
            # run() (para que _normalize_messages del scaffold los lea sin
            # traducción extra).
            context.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc.id, "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in (resp.tool_calls or [])
                ],
            })
            context.append({
                "role": "user",
                "content": (
                    f"{last_error} Debés cerrar SIEMPRE invocando la herramienta "
                    f"'{FINAL_RESULT_TOOL_NAME}' con argumentos válidos según el schema."
                ),
            })
            continue

        # Se encontró un tool_call a final_result: intentar parsear y validar.
        try:
            args = json.loads(final_call.arguments)
            parsed = schema.model_validate(args)
        except Exception as exc:
            # STRUCT-03: JSON inválido o validación de schema fallida. Se
            # responde el tool_call con una observación role:tool (igual que
            # run() responde cada tool_call) para que el modelo vea el error
            # puntual, y se agrega un mensaje de reparación pidiendo
            # argumentos corregidos.
            last_error = f"{type(exc).__name__}: {exc}"
            context.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc.id, "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in (resp.tool_calls or [])
                ],
            })
            context.append({
                "role": "tool",
                "content": last_error,
                "tool_call_id": final_call.id,
            })
            context.append({
                "role": "user",
                "content": (
                    f"Los argumentos de '{FINAL_RESULT_TOOL_NAME}' no son válidos: "
                    f"{last_error}. Volvé a invocar '{FINAL_RESULT_TOOL_NAME}' con "
                    "argumentos corregidos que cumplan el schema."
                ),
            })
            continue

        # Éxito (STRUCT-02): se persiste el turno ganador en context (sin
        # mensaje de reparación) para que quede disponible en la próxima
        # llamada sobre esta instancia (SESS-02), y se retorna la instancia
        # validada.
        context.append({
            "role": "assistant",
            "content": resp.content,
            "tool_calls": [
                {"id": tc.id, "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in (resp.tool_calls or [])
            ],
        })
        context.append({
            "role": "tool",
            "content": "final_result recibido y validado.",
            "tool_call_id": final_call.id,
        })
        return parsed

    # STRUCT-04: se agotaron max_repair_attempts reparaciones sin una
    # respuesta válida. Se levanta una excepción limpia (nunca None, nunca
    # una instancia parcial) llevando el último motivo de fallo, sin
    # traceback interno.
    raise ValueError(
        f"structured_call agotó {max_repair_attempts} reparación(es) sin una "
        f"respuesta válida: {last_error}"
    )
