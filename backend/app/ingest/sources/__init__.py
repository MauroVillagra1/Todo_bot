from app.ingest.sources.base import ItemCrudo, Source
from app.ingest.sources.wordpress import WordPressSource
from app.models.ingesta import Fuente, TipoFuenteEnum

_ADAPTADORES: dict[TipoFuenteEnum, type[Source]] = {
    TipoFuenteEnum.WORDPRESS: WordPressSource,
}


def obtener_adaptador(fuente: Fuente) -> Source:
    clase = _ADAPTADORES.get(fuente.tipo)
    if clase is None:
        raise NotImplementedError(f"No hay adaptador para fuentes de tipo {fuente.tipo.value}")
    return clase(fuente)


__all__ = ["ItemCrudo", "Source", "obtener_adaptador"]
