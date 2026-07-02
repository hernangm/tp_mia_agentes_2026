"""Implementación de su agente.

Completen `register_tool` y `run` para el Milestone 1.
En el Milestone 2 amplíen `MyAgent` para que sea estatal y respete
`max_history_messages`.

Los tests de conformidad en `tests/conformance/test_m1.py` y
`test_m2.py` describen con precisión qué comportamientos deben funcionar
— léanlos antes de empezar.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from mia_agents.protocols import LLMClient
from mia_agents.types import AgentResult, AgentStep, ToolSchema

from student_framework.context_policy import ContextPolicy, SlidingWindowContextPolicy

# Reintentos de tools fallidas (ERR-01): 1 intento inicial + 2 reintentos = 3 intentos
# totales. Se fija como constante de módulo (no como parámetro de MyAgent ni de
# build_agent) porque el requerimiento lo deja explícitamente fuera de alcance como
# configurable — un valor fijo es una decisión de diseño, no una perilla del usuario.
# El valor 3 espeja `max_repair_attempts=2` de structured_call (1 + 2), manteniendo
# consistencia entre los dos mecanismos de reintento del agente.
MAX_TOOL_ATTEMPTS = 3
# Base del backoff exponencial en segundos: el intento N espera
# RETRY_BACKOFF_BASE * 2**N antes del siguiente intento. Un valor chico (0.1s)
# mantiene los tests rápidos sin monkeypatch y evita que una tool lenta bloquee
# el loop por mucho tiempo (mitiga T-02-01: DoS por reintentos sin cota).
RETRY_BACKOFF_BASE = 0.1


class MyAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str = "Eres un asistente útil.",
        max_iterations: int = 10,
        max_history_messages: int = 50,
        context_policy: ContextPolicy | None = None,
    ) -> None:
        """Inicializa el agente.

        Parameters
        ----------
        llm_client : LLMClient
            Cliente LLM (real o mock) que el agente utilizará.
        system_prompt : str
            System prompt por defecto.
        max_iterations : int
            Tope de iteraciones del bucle del agente (M1).
        max_history_messages : int
            Tope de mensajes en la lista enviada a `self._llm.chat(...)`
            en cada llamada (nunca se supera, sea cual sea la iteración).
        context_policy : ContextPolicy | None
            Estrategia de acotado del contexto (D-05). Por defecto,
            `SlidingWindowContextPolicy()`.
        """
        self._llm = llm_client
        self._system = system_prompt
        self._max_iterations = max_iterations
        self._max_history_messages = max_history_messages
        # Dos diccionarios indexados por schema.name: uno guarda el callable, otro el esquema.
        # Separarlos evita acoplar el despacho de herramientas a la búsqueda del esquema —
        # register_tool escribe en ambos; run lee _tools para invocar y _schemas para exponer al LLM.
        self._tools: dict[str, Callable[..., str]] = {}
        self._schemas: dict[str, ToolSchema] = {}
        # self._context: memoria completa, nunca truncada (D-01).
        # self._context_policy: decide qué sublista se manda en cada chat().
        self._context_policy: ContextPolicy = context_policy or SlidingWindowContextPolicy()
        self._context: list[dict] = []

    def register_tool(
        self,
        tool: Callable[..., str],
        schema: ToolSchema,
    ) -> None:
        """Registra una herramienta callable junto a su esquema.

        El esquema suele obtenerse con `ToolSchema.from_callable(fn)`. En
        `run`, pasá `tools=list(self._schemas.values())`; el cliente LLM
        aplica `to_llm_spec()` al llamar al proveedor.

        El callable se invoca con kwargs que coinciden con la firma.
        Debe devolver una cadena. Debe ser idempotente/sin side-effects
        relevantes: `run()` puede reintentarlo hasta `MAX_TOOL_ATTEMPTS`
        veces si lanza una excepción.
        """
        # schema.name es la clave que el LLM usará en tool_call.name — usarla como clave del registro
        # hace que el despacho en run() sea una búsqueda directa en el dict sin traducción de nombres.
        self._tools[schema.name] = tool
        self._schemas[schema.name] = schema

    def run(self, user_message: str) -> AgentResult:
        """Ejecuta el bucle del agente hasta una respuesta final o hasta max_iterations.

        Comportamiento esperado (consulta tests/conformance/test_m1.py
        para el contrato exacto del M1):
          - Llama a `self._llm.chat(..., tools=list(self._schemas.values()))`.
          - Si la respuesta contiene tool_calls, ejecuta cada uno y vuelca
            los resultados en la siguiente llamada al chat.
          - Si la respuesta solo contiene texto (sin `tool_calls`),
            devuélvelo en `AgentResult.answer`. En M1 no uses la tool
            sintética `final_result`; ese patrón es de M2 (ver README y
            ENUNCIADO_M2.md).
          - Limita el bucle a `self._max_iterations` y termina de forma
            limpia cuando se alcance.
          - Registra cada invocación de herramienta como un `AgentStep`
            dentro de `result.steps`.

        En el M2, además, llamadas sucesivas sobre la misma instancia
        deben continuar la conversación, y la longitud de la lista de
        mensajes enviada al LLM no debe superar `self._max_history_messages`.
        Acumula los tokens de entrada/salida reportados por los
        `LLMResponse` y exponlos en `AgentResult.input_tokens` /
        `AgentResult.output_tokens`.
        """
        # Se persiste en self._context, no en variable local (SESS-01/D-01).
        self._context.append({"role": "user", "content": user_message})
        steps: list = []
        # Locales a este run(), no self._*: input_tokens/output_tokens son el
        # total de ESTA llamada, no un acumulado de toda la sesión (CTX-02).
        total_input: int | None = None
        total_output: int | None = None

        for _ in range(self._max_iterations):
            # Se acota en cada iteración, no solo antes del loop, porque el
            # tope debe valer en toda llamada a chat() (CTX-01).
            bounded = self._context_policy.handle_context(
                self._context, self._max_history_messages
            )
            resp = self._llm.chat(
                messages=bounded,
                tools=list(self._schemas.values()) if self._schemas else None,
                system=self._system,
            )

            # Se suman los tokens de cada turno; (x or 0) trata None como 0 sin cambiar el tipo del acumulador.
            if resp.input_tokens is not None:
                total_input = (total_input or 0) + resp.input_tokens
            if resp.output_tokens is not None:
                total_output = (total_output or 0) + resp.output_tokens

            # Sin tool_calls: el LLM produjo una respuesta final en texto — el bucle termina aquí.
            # Esta es la única condición de parada válida en M1; final_result pertenece a M2.
            if not resp.tool_calls:
                return AgentResult(answer=resp.content or "", steps=steps,
                                   input_tokens=total_input, output_tokens=total_output)

            # Se agrega el turno del asistente con tool_calls serializados al formato dict que espera
            # _normalize_messages del scaffold: {"id": ..., "function": {"name": ..., "arguments": ...}}.
            # Pasar objetos ToolCall directamente falla porque el scaffold llama .get() sobre cada elemento.
            self._context.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": [
                    {"id": tc.id, "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in resp.tool_calls
                ],
            })

            # Se despacha cada tool_call y se recolectan los resultados.
            for tool_call in resp.tool_calls:
                if tool_call.name not in self._tools:
                    # Herramienta desconocida: se registra el error pero el bucle continúa — nunca crashear por alucinaciones del LLM.
                    steps.append(AgentStep(
                        tool_name=tool_call.name,
                        tool_input=tool_call.arguments,
                        tool_output=None,
                        error=f"Herramienta desconocida: {tool_call.name}",
                    ))
                    tool_output = f"Error: herramienta desconocida '{tool_call.name}'"
                else:
                    tool_output = None
                    error_msg = None

                    # JSON inválido o con forma no-mapping: error determinístico, mismo
                    # resultado en cada intento -> se falla rápido, sin retry (T-02-03).
                    try:
                        kwargs = json.loads(tool_call.arguments)
                        if not isinstance(kwargs, dict):
                            raise TypeError(
                                f"se esperaba un objeto JSON, se recibió {type(kwargs).__name__}"
                            )
                    except Exception as exc:
                        error_msg = (
                            f"Argumentos inválidos para '{tool_call.name}': "
                            f"{type(exc).__name__}: {exc}"
                        )

                    if error_msg is None:
                        # Retry con backoff exponencial (ERR-01): fallo transitorio de
                        # tool, no de parseo. Éxito -> break; agotamiento -> error_msg
                        # queda seteado y el turno sigue (ERR-02), sin propagar la excepción.
                        for attempt in range(MAX_TOOL_ATTEMPTS):
                            try:
                                tool_output = self._tools[tool_call.name](**kwargs)
                                error_msg = None
                                break
                            except Exception as exc:
                                # Tipo + str(exc), nunca traceback.format_exc() — no
                                # exponer rutas internas al modelo/usuario (ERR-03).
                                error_msg = (
                                    f"La herramienta '{tool_call.name}' falló tras "
                                    f"{attempt + 1} intento(s): {type(exc).__name__}: {exc}"
                                )
                                tool_output = None
                                if attempt < MAX_TOOL_ATTEMPTS - 1:  # sin sleep tras el último intento
                                    time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))

                    steps.append(AgentStep(
                        tool_name=tool_call.name,
                        tool_input=tool_call.arguments,
                        tool_output=tool_output,
                        error=error_msg,
                    ))

                    if error_msg is not None:
                        # El LLM debe VER el fallo para poder razonar sobre él en el
                        # próximo turno (p. ej. reintentar con otros argumentos o
                        # informar al usuario) — la observación role:tool lleva el
                        # mensaje legible, nunca None (ERR-02, ERR-04: el fallo queda
                        # visible tanto en AgentStep.error como en el historial).
                        tool_output = error_msg

                # Se vuelca el resultado para que el LLM pueda razonar sobre él en el próximo turno.
                self._context.append({"role": "tool", "content": tool_output, "tool_call_id": tool_call.id})

        # Se alcanzó max_iterations sin respuesta de texto — se retorna lo que hay en lugar de loopear indefinidamente.
        return AgentResult(answer="", steps=steps, input_tokens=total_input, output_tokens=total_output)

    def structured_call(
        self,
        prompt: str,
        schema: Any,
        max_repair_attempts: int = 2,
    ) -> Any:
        """Pide al LLM una respuesta validada contra `schema` (M2).

        Obligatorio: herramienta sintética `final_result` (ver
        `mia_agents.final_result_tool_schema` / `FINAL_RESULT_TOOL_NAME`).
        El agente ofrece esa tool al LLM, valida los `arguments` del
        `tool_call` y reintenta con contexto de reparación si el modelo
        responde con texto libre o con argumentos inválidos.

        Implementa esto en el M2:
          - Pasa `tools=[final_result_tool_schema(schema)]` en cada
            llamada a `chat` dentro de este método.
          - Termina solo cuando llega un `tool_call` a `final_result`
            cuyos argumentos validan con `schema.model_validate(...)`.
          - Reintenta hasta `max_repair_attempts` incluyendo el fallo en
            los mensajes (respuesta previa, mensaje `tool`, o user de
            reparación).
          - Si tras los reintentos sigue fallando, levanta una excepción
            limpia (no devuelvas valores parciales ni `None` sin avisar).

        El M1 deja esto como stub; los tests de M2 verifican el contrato.
        """
        raise NotImplementedError("M2: implementa salida estructurada con reparación")
