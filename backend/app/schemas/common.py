"""
Schemas genéricos reutilizables en toda la API.
"""
from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Wrapper estándar para respuestas paginadas.

    Ejemplo de uso en un router:
        return PaginatedResponse(items=results, total=count, page=1, page_size=20)
    """
    items: List[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Respuesta simple de confirmación o error."""
    message: str


class ErrorDetail(BaseModel):
    """Estructura estándar para errores de la API."""
    detail: str
    code: str | None = None
