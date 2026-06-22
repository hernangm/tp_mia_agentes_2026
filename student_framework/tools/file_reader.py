from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema


# Directorio base permitido — solo se pueden leer archivos dentro de data/.
# Usar resolve() en ambos lados garantiza que .. y symlinks no escapen la sandbox,
# independientemente de cómo el LLM construya la ruta (relativa, absoluta, con ..).
_BASE_DIR = (Path(__file__).parent.parent.parent / "data").resolve()


def file_reader(
    path: Annotated[str, Field(description="Ruta al archivo a leer, relativa al directorio data/.")],
) -> str:
    """Lee el contenido de un archivo de texto dentro del directorio data/.

    Solo acepta rutas dentro de data/ — rechaza cualquier intento de acceder
    a archivos fuera de ese directorio (rutas con .., rutas absolutas externas).
    Codificación esperada: UTF-8.
    """
    # Se resuelve la ruta candidata contra el directorio base para neutralizar .. y rutas absolutas.
    candidate = (_BASE_DIR / path).resolve()

    # Verificación de sandbox: la ruta resuelta debe estar dentro de BASE_DIR.
    # is_relative_to() compara componentes del path, no strings — evita el falso positivo
    # de startswith() donde /data_evil/ pasaría el chequeo contra /data/.
    if not candidate.is_relative_to(_BASE_DIR):
        return f"Error: acceso denegado. Solo se pueden leer archivos dentro de data/."

    if not candidate.exists():
        return f"Error: el archivo '{path}' no existe en data/."

    if not candidate.is_file():
        return f"Error: '{path}' no es un archivo."

    return candidate.read_text(encoding="utf-8")


file_reader_schema = ToolSchema.from_callable(file_reader)
