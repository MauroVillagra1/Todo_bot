"""
Interfaz común de los adaptadores de fuentes (ING-01).
Cada adaptador solo sabe *traer* contenido; detectar duplicados, guardar
y versionar lo hace el pipeline, igual para todas las fuentes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from app.models.ingesta import Fuente

USER_AGENT = "UTNIA-bot/0.1 (asistente informativo UTN FRT; +https://utnia.netlify.app)"


@dataclass
class ItemCrudo:
    """Una publicación tal como la entrega la fuente, antes de procesarla."""
    id_externo: str
    url: str
    titulo: str
    contenido_html: str
    fecha_publicacion: datetime | None
    fecha_modificacion: datetime | None


class Source(ABC):
    def __init__(self, fuente: Fuente):
        self.fuente = fuente
        self.config = fuente.config or {}

    @abstractmethod
    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        """
        Devuelve los ítems creados o modificados después de `desde`
        (todos si es None). No debe usar LLM.
        """
