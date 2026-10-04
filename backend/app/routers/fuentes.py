"""
Router de fuentes.
  GET  /api/v1/fuentes                         → lista de fuentes (MOD y ADMIN)
  POST /api/v1/fuentes/{id}/publicaciones      → carga manual de un posteo de
       Instagram/WhatsApp autorizado (MOD y ADMIN). Pasa por el mismo pipeline
       que la ingesta automática: hash, versionado, chunks y verificación.
"""
import hashlib
from datetime import date, datetime, time, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_mod
from app.ingest.pipeline import DUPLICADO, guardar_publicacion
from app.ingest.sources import TIPOS_CARGA_MANUAL, ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.models.informacion import Evidencia, Informacion
from app.models.ingesta import Fuente, Publicacion

router = APIRouter(prefix="/fuentes", tags=["Fuentes"])


class FuenteRead(BaseModel):
    id: int
    nombre: str
    tipo: str
    url: str
    confiabilidad_base: int
    activa: bool
    ultima_revision: datetime | None
    carga_manual: bool


class PublicacionManual(BaseModel):
    url: HttpUrl = Field(description="Link al posteo original (Instagram o canal de WhatsApp)")
    titulo: str = Field(min_length=3, max_length=300)
    contenido: str = Field(min_length=10, max_length=20000, description="Texto del posteo")
    fecha_publicacion: date


class PublicacionManualResultado(BaseModel):
    resultado: str  # nuevo | actualizado | duplicado
    publicacion_id: int
    informacion_id: int | None
    estado: str | None
    tipo: str | None


@router.get("/", response_model=list[FuenteRead])
def listar_fuentes(db: Session = Depends(get_db), _mod=Depends(require_mod)):
    return [
        FuenteRead(
            id=f.id, nombre=f.nombre, tipo=f.tipo.value, url=f.url,
            confiabilidad_base=f.confiabilidad_base, activa=f.activa,
            ultima_revision=f.ultima_revision, carga_manual=f.tipo in TIPOS_CARGA_MANUAL,
        )
        for f in db.query(Fuente).order_by(Fuente.id).all()
    ]


@router.post("/{fuente_id}/publicaciones", response_model=PublicacionManualResultado,
             status_code=status.HTTP_201_CREATED)
def cargar_publicacion(
    fuente_id: int,
    datos: PublicacionManual,
    db: Session = Depends(get_db),
    _mod=Depends(require_mod),
):
    fuente = db.get(Fuente, fuente_id)
    if not fuente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuente no encontrada")
    if fuente.tipo not in TIPOS_CARGA_MANUAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta fuente se actualiza sola; la carga manual es para Instagram y WhatsApp",
        )

    url = str(datos.url)
    fecha = datetime.combine(datos.fecha_publicacion, time(12), tzinfo=timezone.utc)
    item = ItemCrudo(
        # El mismo link cargado de nuevo con otro texto = versión nueva del mismo posteo
        id_externo="manual:" + hashlib.sha256(url.encode()).hexdigest()[:32],
        url=url,
        titulo=datos.titulo,
        contenido_html="".join(f"<p>{escape(linea)}</p>" for linea in datos.contenido.splitlines()),
        fecha_publicacion=fecha,
        fecha_modificacion=fecha,
    )
    resultado = guardar_publicacion(db, fuente, item)
    db.commit()
    procesar_pendientes(db)  # queda buscable en el chat de inmediato

    pub = (
        db.query(Publicacion)
        .filter(Publicacion.fuente_id == fuente.id, Publicacion.id_externo == item.id_externo,
                Publicacion.vigente.is_(True))
        .one()
    )
    info = (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .filter(Evidencia.publicacion_id == pub.id)
        .first()
    )
    return PublicacionManualResultado(
        resultado=resultado,
        publicacion_id=pub.id,
        informacion_id=info.id if info else None,
        estado=info.estado.value if info else None,
        tipo=info.tipo.value if info else None,
    )
