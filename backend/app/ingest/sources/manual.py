"""
Fuentes sin API permitida (canales de WhatsApp, o Instagram sin token):
el contenido entra por carga manual de un MOD (POST /fuentes/{id}/publicaciones).
El worker no trae nada de estas fuentes, así que no falla ni gasta nada.
"""
from datetime import datetime
from typing import Iterator

from app.ingest.sources.base import ItemCrudo, Source


class ManualSource(Source):
    def obtener_cambios(self, desde: datetime | None) -> Iterator[ItemCrudo]:
        return iter(())
