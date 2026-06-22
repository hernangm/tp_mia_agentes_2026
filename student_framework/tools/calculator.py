from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema


# Operadores permitidos explícitos — sin eval ni expresiones arbitrarias.
# La decisión de usar un dict de funciones en lugar de un if/elif hace que
# agregar un operador nuevo sea un cambio de una línea sin tocar la lógica de despacho.
_OPERADORES = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "%": lambda a, b: a % b,
}


def calculator(
    left_operand: Annotated[float, Field(description="Operando izquierdo de la operación.")],
    operator: Annotated[str, Field(description="Operador aritmético: +, -, *, %.")],
    right_operand: Annotated[float, Field(description="Operando derecho de la operación.")],
) -> str:
    """Realiza una operación aritmética binaria entre dos números.

    Operadores soportados: + (suma), - (resta), * (multiplicación), % (módulo).
    Devuelve el resultado como cadena de texto.
    """
    if operator not in _OPERADORES:
        return f"Error: operador '{operator}' no soportado. Usá uno de: {', '.join(_OPERADORES)}"

    try:
        resultado = _OPERADORES[operator](left_operand, right_operand)
    except ZeroDivisionError:
        return "Error: división por cero."
    return str(resultado)


calculator_schema = ToolSchema.from_callable(calculator)
