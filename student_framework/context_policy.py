"""Política de acotado del contexto conversacional (CTX-01, SESS-01).

`MyAgent` mantiene `self._context` completo y sin límite (D-01) durante toda
la vida de la instancia; lo que SÍ tiene un tope es la lista que se envía
en cada llamada a `self._llm.chat(...)`. `ContextPolicy` separa esa decisión
("qué mandar esta vez") del estado en sí, para que la estrategia de acotado
sea reemplazable sin tocar `MyAgent` (D-02).

Se eligió una ABC (no `typing.Protocol`, pese a que Protocol es el estilo
dominante en `mia_agents/protocols.py`) porque acá el objetivo es compartir
comportamiento concreto entre estrategias (el hook `on_evict`, y en el futuro
posibles helpers de segmentación) además de fijar un contrato de método
abstracto — el mismo shape que ya usa `mia_agents/llm_client.py:_BaseLLMProvider`
para variar `chat()` entre proveedores. Un Protocol solo fija la forma, no
compartiría ese comportamiento común.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextPolicy(ABC):
    """Estrategia de acotado del contexto enviado al LLM.

    `handle_context` recibe el historial COMPLETO (`self._context`, que
    `MyAgent` nunca trunca por fuera) y devuelve la sublista a enviar en
    esta llamada puntual a `chat()`. `on_evict` es un hook observable,
    no-op por defecto, para que subclases o tests puedan inspeccionar qué
    se descartó sin acoplar la política a un mecanismo de logging concreto.
    """

    @abstractmethod
    def handle_context(self, context: list[dict], max_messages: int) -> list[dict]:
        """Devuelve la sublista de `context` a enviar, de largo <= max_messages."""
        ...

    def on_evict(self, evicted: list[dict]) -> None:
        """Hook opcional, no-op por defecto.

        Se llama una única vez por invocación de `handle_context()`, con
        TODOS los mensajes descartados en esa llamada agrupados en una
        sola lista (batched) — nunca uno por uno. No se llama si no hubo
        eviction (ver `handle_context` de `SlidingWindowContextPolicy`).
        """
        pass


class SlidingWindowContextPolicy(ContextPolicy):
    """Ventana deslizante por cantidad de mensajes (CTX-01: por cuenta, no por tokens).

    `atomic_turns` controla si el recorte respeta los "turnos atómicos"
    (un mensaje `assistant` con `tool_calls` más los `role: "tool"` que le
    siguen inmediatamente cuentan como una sola unidad indivisible) o si
    corta mensajes sueltos por cantidad, sin awareness de pairing.
    """

    def __init__(self, atomic_turns: bool = True) -> None:
        self._atomic_turns = atomic_turns

    def handle_context(self, context: list[dict], max_messages: int) -> list[dict]:
        if len(context) <= max_messages:
            # Nada que recortar: se devuelve una copia (nunca la referencia
            # original) para no acoplar al llamador a mutaciones futuras,
            # aunque acá no haya eviction que reportar.
            return list(context)

        if self._atomic_turns:
            bounded, evicted = self._atomic_trim(context, max_messages)
        else:
            # Corte estricto por cantidad: sin awareness de pairing, se
            # descartan los mensajes más viejos hasta entrar en el tope.
            cutoff = len(context) - max_messages
            evicted, bounded = context[:cutoff], context[cutoff:]

        # on_evict se llama SOLO si algo se descartó — "se evictó nada" no
        # es un evento de eviction, y llamarlo siempre con lista vacía
        # ensuciaría el hook en el caso común de subclases que loguean.
        if evicted:
            self.on_evict(evicted)
        return bounded

    @staticmethod
    def _segment_into_units(context: list[dict]) -> list[list[dict]]:
        """Agrupa `context` en turnos atómicos.

        Un turno atómico es: (a) un mensaje `assistant` con `tool_calls`
        no vacío más TODOS los `role: "tool"` que lo siguen inmediatamente,
        o (b) cualquier otro mensaje individual (`user`, o `assistant` sin
        tool_calls). Esta segmentación asume que `context` siempre tiene
        límites de turno consistentes porque nunca se trunca desde afuera
        (D-01) — solo `MyAgent.run()` lo construye, turno a turno, con el
        mismo orden con el que los mensajes fueron apendeados originalmente.
        """
        units: list[list[dict]] = []
        i, n = 0, len(context)
        while i < n:
            msg = context[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                unit = [msg]
                j = i + 1
                while j < n and context[j].get("role") == "tool":
                    unit.append(context[j])
                    j += 1
                units.append(unit)
                i = j
            else:
                units.append([msg])
                i += 1
        return units

    @classmethod
    def _atomic_trim(
        cls, context: list[dict], max_messages: int
    ) -> tuple[list[dict], list[dict]]:
        """Conserva el sufijo más reciente de turnos atómicos completos que entra en el tope."""
        units = cls._segment_into_units(context)
        kept_units: list[list[dict]] = []
        total = 0
        for unit in reversed(units):
            if total + len(unit) > max_messages:
                break
            kept_units.append(unit)
            total += len(unit)
        kept_units.reverse()

        if not kept_units:
            # D-04 (tiny-budget fallback): ni el turno atómico más reciente
            # entra en el presupuesto. CTX-01 ("el tope nunca se supera, en
            # NINGUNA llamada") es el requisito no negociable, así que acá
            # se prioriza el corte estricto por sobre el pairing correcto
            # — se acepta romper un tool_call/tool_result en este único
            # caso degenerado, solo para esta llamada (no cambia el modo
            # de la política de forma permanente).
            cutoff = max(len(context) - max_messages, 0)
            return context[cutoff:], context[:cutoff]

        num_dropped_units = len(units) - len(kept_units)
        dropped = units[:num_dropped_units]
        evicted = [m for unit in dropped for m in unit]
        bounded = [m for unit in kept_units for m in unit]
        return bounded, evicted
