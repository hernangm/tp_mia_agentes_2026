"""Política de acotado de contexto (CTX-01, D-02).

`self._context` de `MyAgent` es completo y sin límite (D-01); esta política
decide qué sublista mandar en cada `chat()`. ABC y no `typing.Protocol`
porque comparte comportamiento concreto (`on_evict`), igual que
`_BaseLLMProvider` en `mia_agents/llm_client.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextPolicy(ABC):
    """Decide qué sublista de `self._context` se manda en cada `chat()`."""

    @abstractmethod
    def handle_context(self, context: list[dict], max_messages: int) -> list[dict]:
        """Sublista de `context` a enviar, de largo <= max_messages."""
        ...

    def on_evict(self, evicted: list[dict]) -> None:
        """No-op por defecto. Se llama una vez por `handle_context()`, con
        todos los descartes de esa llamada juntos, solo si hubo eviction."""
        pass


class SlidingWindowContextPolicy(ContextPolicy):
    """Ventana deslizante por cantidad de mensajes (CTX-01: cuenta, no tokens).

    `atomic_turns=True`: nunca separa un `assistant`+`tool_calls` de sus
    `tool` results. `atomic_turns=False`: corta por cantidad sin pairing.
    """

    def __init__(self, atomic_turns: bool = True) -> None:
        self._atomic_turns = atomic_turns

    def handle_context(self, context: list[dict], max_messages: int) -> list[dict]:
        if len(context) <= max_messages:
            return list(context)  # copia, no la referencia original

        if self._atomic_turns:
            bounded, evicted = self._atomic_trim(context, max_messages)
        else:
            # Corte estricto: descarta los más viejos hasta entrar en el tope.
            cutoff = len(context) - max_messages
            evicted, bounded = context[:cutoff], context[cutoff:]

        if evicted:  # on_evict solo si hubo descarte real
            self.on_evict([dict(m) for m in evicted])  # copias: no exponer self._context
        return bounded

    @staticmethod
    def _segment_into_units(context: list[dict]) -> list[list[dict]]:
        """Agrupa `context` en turnos atómicos: `assistant`+`tool_calls` con
        sus `tool` results, o cualquier otro mensaje individual."""
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
            # D-04: ni el turno más reciente entra en el tope. CTX-01 manda:
            # se prioriza el corte estricto sobre el pairing, solo esta llamada.
            # Igual se descarta un `tool` huérfano al inicio: un tool_result
            # sin su tool_call en la misma ventana rompe la Converse API real.
            cutoff = max(len(context) - max_messages, 0)
            bounded = context[cutoff:]
            while bounded and bounded[0].get("role") == "tool":
                bounded = bounded[1:]
            evicted = context[: len(context) - len(bounded)]
            return bounded, evicted

        num_dropped_units = len(units) - len(kept_units)
        dropped = units[:num_dropped_units]
        evicted = [m for unit in dropped for m in unit]
        bounded = [m for unit in kept_units for m in unit]
        return bounded, evicted
