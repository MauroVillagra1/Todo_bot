from app.ingest.sources.base import DocumentoCrudo, ItemCrudo, Source
from app.ingest.sources.instagram import InstagramSource
from app.ingest.sources.manual import ManualSource
from app.ingest.sources.moodle import MoodleSource
from app.ingest.sources.pagina import PaginaSource
from app.ingest.sources.wordpress import WordPressSource
from app.models.ingesta import Fuente, TipoFuenteEnum

_ADAPTADORES: dict[TipoFuenteEnum, type[Source]] = {
    TipoFuenteEnum.WORDPRESS: WordPressSource,
    TipoFuenteEnum.INSTAGRAM: InstagramSource,
    TipoFuenteEnum.WHATSAPP: ManualSource,  # no existe API para leer canales
    TipoFuenteEnum.MANUAL: ManualSource,
}

# Tipos en los que un MOD puede cargar publicaciones a mano
TIPOS_CARGA_MANUAL = {TipoFuenteEnum.INSTAGRAM, TipoFuenteEnum.WHATSAPP, TipoFuenteEnum.MANUAL}


def obtener_adaptador(fuente: Fuente) -> Source:
    # Sitio web que es un Moodle (catálogo público del campus virtual)
    if (fuente.config or {}).get("moodle"):
        return MoodleSource(fuente)
    # Páginas sueltas con avisos (ej. ingreso al SYSACAD)
    if (fuente.config or {}).get("paginas"):
        return PaginaSource(fuente)
    clase = _ADAPTADORES.get(fuente.tipo)
    if clase is None:
        raise NotImplementedError(f"No hay adaptador para fuentes de tipo {fuente.tipo.value}")
    return clase(fuente)


__all__ = ["DocumentoCrudo", "ItemCrudo", "Source", "TIPOS_CARGA_MANUAL", "obtener_adaptador"]
