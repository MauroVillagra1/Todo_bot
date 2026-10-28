"""
Router de carga directa de información (MOD y ADMIN).
  POST /api/v1/informacion       → un dato cualquiera: tipo (obligatorio), texto (obligatorio), link (opcional)
  POST /api/v1/informacion/paro  → paro docente, no docente o ambos, con fecha y cantidad de días.
       El texto lo arma el backend: si la facultad queda abierta o cerrada sale del tipo de paro.
  GET  /api/v1/informacion/avisos → paros vigentes (cualquier usuario): el banner del chat
  DELETE /api/v1/informacion/{id} → dar de baja algo cargado por un moderador (ej. un paro levantado)

Entra por el mismo pipeline que la carga manual (publicación → chunks → INFORMACION) y queda
buscable en el chat de inmediato. El tipo elegido por el MOD manda sobre la clasificación automática.
"""
import enum
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_mod
from app.ingest.pipeline import guardar_publicacion
from app.ingest.sources import ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.ingest.verify import estado_por_confiabilidad
from app.models.cache import CacheRespuesta
from app.models.informacion import (
    EstadoInformacionEnum as E, Evidencia, Informacion, TipoInformacionEnum, Verificacion,
)
from app.models.ingesta import Fuente, Publicacion, TipoFuenteEnum
from app.rag.fechas import hoy_argentina
from app.services.avisos import PREFIJO_PARO, paros

router = APIRouter(prefix="/informacion", tags=["Información"])

FUENTE_MODERADORES = "Carga de moderadores"
# La cargan MOD/ADMIN de la facultad: queda CONFIRMADA (el ADMIN puede bajarla en Fuentes)
CONFIABILIDAD_MODERADORES = 100
MAX_DIAS_PARO = 30
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class TipoParoEnum(str, enum.Enum):
    DOCENTE = "DOCENTE"
    NO_DOCENTE = "NO_DOCENTE"
    AMBOS = "AMBOS"


class InformacionManual(BaseModel):
    tipo: TipoInformacionEnum
    contenido: str = Field(min_length=10, max_length=20000)
    url: HttpUrl | None = None
    # Reglamentos, normativa, requisitos: no tienen fecha de vencimiento
    sin_vencimiento: bool = False


class Paro(BaseModel):
    tipo: TipoParoEnum
    fecha: date = Field(description="Primer día del paro")
    dias: int = Field(1, ge=1, le=MAX_DIAS_PARO, description="Cantidad de días seguidos")
    url: HttpUrl | None = None
    detalle: str | None = Field(None, max_length=2000, description="Aclaraciones (opcional)")


class InformacionCargada(BaseModel):
    informacion_id: int
    titulo: str
    contenido: str
    tipo: str
    estado: str
    fecha_inicio: date | None = None
    fecha_fin: date | None


def _fuente_moderadores(db: Session) -> Fuente:
    fuente = db.query(Fuente).filter(Fuente.nombre == FUENTE_MODERADORES).first()
    if not fuente:
        fuente = Fuente(nombre=FUENTE_MODERADORES, tipo=TipoFuenteEnum.MANUAL, url=get_settings().SITE_URL,
                        confiabilidad_base=CONFIABILIDAD_MODERADORES, activa=True, config={})
        db.add(fuente)
        db.flush()
    return fuente


def _cargar(db: Session, tipo: TipoInformacionEnum, titulo: str, contenido: str, url: HttpUrl | None,
            prefijo: str = "moderador:", sin_vencimiento: bool = False) -> InformacionCargada:
    fuente = _fuente_moderadores(db)
    ahora = datetime.now(timezone.utc)
    item = ItemCrudo(
        id_externo=f"{prefijo}{uuid.uuid4().hex}",
        url=str(url) if url else fuente.url,
        titulo=titulo,
        contenido_html="".join(f"<p>{escape(linea)}</p>" for linea in contenido.splitlines()),
        fecha_publicacion=ahora,
        fecha_modificacion=ahora,
    )
    guardar_publicacion(db, fuente, item)
    db.commit()
    procesar_pendientes(db)  # queda buscable en el chat de inmediato

    info = (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Publicacion.fuente_id == fuente.id, Publicacion.id_externo == item.id_externo)
        .one()
    )
    info.tipo = tipo  # lo eligió el MOD: manda sobre las reglas de clasificación
    if sin_vencimiento and info.fecha_fin:
        info.fecha_fin = None
        info.estado = estado_por_confiabilidad(fuente.confiabilidad_base)
        db.add(Verificacion(informacion_id=info.id, resultado=info.estado, puntuacion=fuente.confiabilidad_base,
                            explicacion="Sin vencimiento: lo indicó quien la cargó (normativa o requisito permanente)"))
    db.commit()
    return _leer(info)


def _leer(info: Informacion) -> InformacionCargada:
    return InformacionCargada(informacion_id=info.id, titulo=info.titulo, contenido=info.contenido,
                              tipo=info.tipo.value, estado=info.estado.value, fecha_inicio=info.fecha_inicio,
                              fecha_fin=info.fecha_fin)


def _titulo_de(contenido: str) -> str:
    """Primera línea con texto, recortada: el formulario no pide título."""
    primera = next((l.strip() for l in contenido.splitlines() if l.strip()), contenido.strip())
    return primera if len(primera) <= 120 else primera[:117].rstrip() + "…"


def _dia(d: date) -> str:
    return f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m/%Y}"


def texto_de_paro(datos: Paro) -> tuple[str, str]:
    """(título, contenido) del aviso. Docente: abierta. No docente o ambos: cerrada."""
    quien = {
        TipoParoEnum.DOCENTE: "docente",
        TipoParoEnum.NO_DOCENTE: "no docente",
        TipoParoEnum.AMBOS: "docente y no docente",
    }[datos.tipo]
    fin = datos.fecha + timedelta(days=datos.dias - 1)
    if datos.dias == 1:
        cuando, cuando_corto = f"el {_dia(datos.fecha)}", f"{datos.fecha:%d/%m/%Y}"
    else:
        cuando = f"de {datos.dias} días, del {_dia(datos.fecha)} al {_dia(fin)}"
        cuando_corto = f"{datos.fecha:%d/%m} al {fin:%d/%m/%Y} ({datos.dias} días)"

    if datos.tipo == TipoParoEnum.DOCENTE:
        estado = ("La facultad permanece ABIERTA: el edificio y la atención administrativa funcionan, "
                  "pero los docentes que adhieren al paro no dan clase.")
    else:
        estado = ("La facultad permanece CERRADA: no hay clases ni atención administrativa "
                  "porque el personal no docente no abre el edificio.")

    titulo = f"Paro {quien}: {cuando_corto}"
    contenido = f"Paro {quien} {cuando}.\n{estado}"
    if datos.detalle and datos.detalle.strip():
        contenido += f"\n{datos.detalle.strip()}"
    return titulo, contenido


@router.post("", response_model=InformacionCargada, status_code=status.HTTP_201_CREATED)
def cargar_informacion(datos: InformacionManual, db: Session = Depends(get_db), _mod=Depends(require_mod)):
    contenido = datos.contenido.strip()
    return _cargar(db, datos.tipo, _titulo_de(contenido), contenido, datos.url,
                   sin_vencimiento=datos.sin_vencimiento)


@router.post("/paro", response_model=InformacionCargada, status_code=status.HTTP_201_CREATED)
def cargar_paro(datos: Paro, db: Session = Depends(get_db), _mod=Depends(require_mod)):
    titulo, contenido = texto_de_paro(datos)
    return _cargar(db, TipoInformacionEnum.AVISO, titulo, contenido, datos.url, prefijo=PREFIJO_PARO)


@router.get("/avisos", response_model=list[InformacionCargada])
def avisos_vigentes(db: Session = Depends(get_db), _usuario=Depends(get_current_user)):
    """Paros de hoy en adelante: el chat los muestra arriba, sin que nadie pregunte."""
    return [_leer(p) for p in paros(db, hoy_argentina())]


@router.delete("/{informacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_de_baja(informacion_id: int, db: Session = Depends(get_db), _mod=Depends(require_mod)):
    """Solo lo cargado por moderadores: queda en el historial pero el chat deja de usarlo."""
    info = (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Fuente, Fuente.id == Evidencia.fuente_id)
        .filter(Informacion.id == informacion_id, Fuente.nombre == FUENTE_MODERADORES)
        .first()
    )
    if not info:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No se encontró información cargada por moderadores con ese id")
    info.estado = E.REEMPLAZADA  # la búsqueda excluye REEMPLAZADA
    db.add(Verificacion(informacion_id=info.id, resultado=E.REEMPLAZADA, puntuacion=info.confianza,
                        explicacion="Dada de baja por un moderador"))
    db.query(CacheRespuesta).delete()  # que el chat deje de responderla ya
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
