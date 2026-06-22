from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema


# Conversión vía unidad canónica: en lugar de una matriz N×N de pares,
# cada unidad define solo dos factores (hacia_canónico, desde_canónico).
# Agregar una unidad nueva es una línea; no hay que tocar la lógica de despacho.
#
# Canónicos: metro (longitud), kilogramo (masa), segundo (tiempo), Celsius (temperatura).

_LONGITUD: dict[str, tuple[float, float]] = {  # (factor → metro, factor ← metro)
    "m":  (1.0,          1.0),
    "km": (1_000.0,      0.001),
    "cm": (0.01,         100.0),
    "mm": (0.001,        1_000.0),
    "mi": (1_609.344,    1 / 1_609.344),
    "ft": (0.3048,       1 / 0.3048),
    "in": (0.0254,       1 / 0.0254),
    "yd": (0.9144,       1 / 0.9144),
}

_MASA: dict[str, tuple[float, float]] = {  # (factor → kg, factor ← kg)
    "kg": (1.0,          1.0),
    "g":  (0.001,        1_000.0),
    "mg": (1e-6,         1e6),
    "lb": (0.453592,     1 / 0.453592),
    "oz": (0.0283495,    1 / 0.0283495),
}

_TIEMPO: dict[str, tuple[float, float]] = {  # (factor → segundo, factor ← segundo)
    "s":   (1.0,         1.0),
    "min": (60.0,        1 / 60.0),
    "h":   (3_600.0,     1 / 3_600.0),
    "d":   (86_400.0,    1 / 86_400.0),
}

# Mapa plano: unidad → dict de su categoría (identidad de objeto para comparar categorías).
_TABLA: dict[str, dict] = {u: d for d in (_LONGITUD, _MASA, _TIEMPO) for u in d}

_TEMPERATURA = {"C", "F", "K"}
_TODAS_LAS_UNIDADES = sorted(_TABLA) + sorted(_TEMPERATURA)


def _convertir_temperatura(valor: float, origen: str, destino: str) -> float:
    # Paso 1: convertir a Celsius (canónico de temperatura).
    if origen == "F":
        celsius = (valor - 32) * 5 / 9
    elif origen == "K":
        celsius = valor - 273.15
    else:
        celsius = valor

    # Paso 2: convertir desde Celsius al destino.
    if destino == "F":
        return celsius * 9 / 5 + 32
    if destino == "K":
        return celsius + 273.15
    return celsius


def unit_converter(
    value: Annotated[float, Field(description="Valor numérico a convertir.")],
    from_unit: Annotated[str, Field(
        description=(
            "Unidad de origen. "
            "Longitud: m, km, cm, mm, mi, ft, in, yd. "
            "Masa: kg, g, mg, lb, oz. "
            "Tiempo: s, min, h, d. "
            "Temperatura: C, F, K."
        )
    )],
    to_unit: Annotated[str, Field(
        description="Unidad de destino. Debe pertenecer a la misma categoría que from_unit."
    )],
) -> str:
    """Convierte un valor numérico entre unidades de la misma categoría.

    Categorías soportadas: longitud, masa, tiempo, temperatura.
    Rechaza conversiones entre categorías distintas (ej: km → kg).
    Devuelve el resultado redondeado a 6 decimales como cadena de texto.
    """
    # Temperatura: conversión no lineal, se trata aparte.
    if from_unit in _TEMPERATURA or to_unit in _TEMPERATURA:
        if from_unit not in _TEMPERATURA:
            return f"Error: '{from_unit}' no es una unidad de temperatura. Unidades válidas: C, F, K."
        if to_unit not in _TEMPERATURA:
            return f"Error: '{to_unit}' no es una unidad de temperatura. Unidades válidas: C, F, K."
        resultado = _convertir_temperatura(value, from_unit, to_unit)
        return str(round(resultado, 6))

    # Unidades lineales: verificar que ambas existan en la tabla.
    if from_unit not in _TABLA:
        return f"Error: unidad '{from_unit}' no reconocida. Unidades válidas: {', '.join(_TODAS_LAS_UNIDADES)}."
    if to_unit not in _TABLA:
        return f"Error: unidad '{to_unit}' no reconocida. Unidades válidas: {', '.join(_TODAS_LAS_UNIDADES)}."

    # Verificar que ambas unidades pertenezcan a la misma categoría (comparación por identidad de objeto).
    # Esto es lo que hace imposible mezclar km con kg aunque ambas estén en la tabla.
    if _TABLA[from_unit] is not _TABLA[to_unit]:
        return f"Error: '{from_unit}' y '{to_unit}' pertenecen a categorías distintas — no se puede convertir entre ellas."

    # Conversión en dos pasos: valor → canónico → destino.
    hacia_canonico, _ = _TABLA[from_unit][from_unit]
    _, desde_canonico = _TABLA[to_unit][to_unit]
    resultado = value * hacia_canonico * desde_canonico
    return str(round(resultado, 6))


unit_converter_schema = ToolSchema.from_callable(unit_converter)
