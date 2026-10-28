"""
Router de sugerencias de datos.
  POST /api/v1/sugerencias                  → cualquier usuario propone un dato
  GET  /api/v1/sugerencias/mias             → las propias, con su estado
  GET  /api/v1/sugerencias?estado=PENDIENTE → para revisar (SMOD y ADMIN)
  POST /api/v1/sugerencias/{id}/aceptar     → quien revisa puede corregir título/texto;
       entra por el mismo pipeline que la carga manual y queda buscable en el chat
  POST /api/v1/sugerencias/{id}/rechazar    → con un motivo que ve quien la envió
  POST /api/v1/sugerencias/{id}/borrar      → SMOD y ADMIN: una aceptada deja de usarse en el chat (con motivo)
Aceptar, rechazar y borrar quedan en el historial de cambios; borrar se puede deshacer.
"""
from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_smod
from app.ingest.pipeline import guardar_publicacion
from app.ingest.sources import ItemCrudo
from app.ingest.verify import procesar_pendientes
from app.models.cache import CacheRespuesta
from app.models.informacion import EstadoInformacionEnum as E, Evidencia, Informacion, Verificacion
from app.models.ingesta import Fuente, Publicacion, TipoFuenteEnum
from app.models.sugerencia import EstadoSugerenciaEnum as S, Sugerencia
from app.models.usuario import Usuario
from app.services.auditoria import registrar

router = APIRouter(prefix="/sugerencias", tags=["Sugerencias"])

FUENTE_SUGERENCIAS = "Sugerencias de usuarios"
# Revisadas en el panel pero sin documento oficial: quedan PROBABLE
CONFIABILIDAD_SUGERENCIAS = 80
MAX_PENDIENTES_POR_USUARIO = 10


class SugerenciaCreate(BaseModel):
    titulo: str = Field(min_length=3, max_length=300)
    contenido: str = Field(min_length=10, max_length=5000)
    url: HttpUrl | None = Field(None, description="Link de donde sale el dato (opcional)")


class Aceptacion(BaseModel):
    titulo: str | None = Field(None, min_length=3, max_length=300)
    contenido: str | None = Field(None, min_length=10, max_length=5000)


class Rechazo(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class SugerenciaRead(BaseModel):
    id: int
    titulo: str
    contenido: str
    url: str | None
    estado: str
    motivo: str | None
    autor: str | None = None
    creada_en: datetime
    revisada_en: datetime | None
    informacion_estado: str | None = None


def _leer(db: Session, s: Sugerencia, con_autor: bool = False) -> SugerenciaRead:
    autor = None
    if con_autor:
        u = db.get(Usuario, s.usuario_id)
        autor = f"{u.nombre} ({u.email})" if u else None
    info_estado = None
    if s.publicacion_id:
        info = (
            db.query(Informacion)
            .join(Evidencia, Evidencia.informacion_id == Informacion.id)
            .filter(Evidencia.publicacion_id == s.publicacion_id)
            .first()
        )
        info_estado = info.estado.value if info else None
    return SugerenciaRead(
        id=s.id, titulo=s.titulo, contenido=s.contenido, url=s.url, estado=s.estado.value,
        motivo=s.motivo, autor=autor, creada_en=s.creada_en, revisada_en=s.revisada_en,
        informacion_estado=info_estado,
    )


def _pendiente(db: Session, sugerencia_id: int) -> Sugerencia:
    s = db.get(Sugerencia, sugerencia_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sugerencia no encontrada")
    if s.estado != S.PENDIENTE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La sugerencia ya fue revisada")
    return s


def _fuente_sugerencias(db: Session) -> Fuente:
    fuente = db.query(Fuente).filter(Fuente.nombre == FUENTE_SUGERENCIAS).first()
    if not fuente:
        fuente = Fuente(nombre=FUENTE_SUGERENCIAS, tipo=TipoFuenteEnum.MANUAL, url=get_settings().SITE_URL,
                        confiabilidad_base=CONFIABILIDAD_SUGERENCIAS, activa=True, config={})
        db.add(fuente)
        db.flush()
    return fuente


@router.post("/", response_model=SugerenciaRead, status_code=status.HTTP_201_CREATED)
def crear_sugerencia(datos: SugerenciaCreate, db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    pendientes = (
        db.query(Sugerencia)
        .filter(Sugerencia.usuario_id == usuario.id, Sugerencia.estado == S.PENDIENTE)
        .count()
    )
    if pendientes >= MAX_PENDIENTES_POR_USUARIO:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tenés {pendientes} sugerencias sin revisar; esperá a que un moderador las vea.",
        )
    s = Sugerencia(usuario_id=usuario.id, titulo=datos.titulo.strip(), contenido=datos.contenido.strip(),
                   url=str(datos.url) if datos.url else None, estado=S.PENDIENTE)
    db.add(s)
    db.flush()
    registrar(db, "sugerencias", s.id, "creacion", None, {"titulo": s.titulo, "estado": S.PENDIENTE.value}, usuario)
    db.commit()
    return _leer(db, s)


@router.get("/mias", response_model=list[SugerenciaRead])
def mis_sugerencias(db: Session = Depends(get_db), usuario=Depends(get_current_user)):
    filas = db.query(Sugerencia).filter(Sugerencia.usuario_id == usuario.id).order_by(Sugerencia.id.desc()).limit(50)
    return [_leer(db, s) for s in filas]


@router.get("/", response_model=list[SugerenciaRead])
def listar_sugerencias(
    estado: S = Query(S.PENDIENTE),
    db: Session = Depends(get_db),
    _smod=Depends(require_smod),
):
    orden = Sugerencia.id.asc() if estado == S.PENDIENTE else Sugerencia.id.desc()  # pendientes: la más vieja primero
    filas = db.query(Sugerencia).filter(Sugerencia.estado == estado).order_by(orden).limit(100)
    return [_leer(db, s, con_autor=True) for s in filas]


@router.post("/{sugerencia_id}/aceptar", response_model=SugerenciaRead)
def aceptar_sugerencia(
    sugerencia_id: int,
    datos: Aceptacion,
    db: Session = Depends(get_db),
    mod=Depends(require_smod),
):
    s = _pendiente(db, sugerencia_id)
    if datos.titulo:
        s.titulo = datos.titulo.strip()
    if datos.contenido:
        s.contenido = datos.contenido.strip()

    fuente = _fuente_sugerencias(db)
    ahora = datetime.now(timezone.utc)
    item = ItemCrudo(
        id_externo=f"sugerencia:{s.id}",
        url=s.url or fuente.url,
        titulo=s.titulo,
        contenido_html="".join(f"<p>{escape(linea)}</p>" for linea in s.contenido.splitlines()),
        fecha_publicacion=ahora,
        fecha_modificacion=ahora,
    )
    guardar_publicacion(db, fuente, item)
    pub = (
        db.query(Publicacion)
        .filter(Publicacion.fuente_id == fuente.id, Publicacion.id_externo == item.id_externo,
                Publicacion.vigente.is_(True))
        .one()
    )
    s.estado, s.revisor_id, s.revisada_en, s.publicacion_id = S.ACEPTADA, mod.id, ahora, pub.id
    registrar(db, "sugerencias", s.id, "aceptacion", {"titulo": s.titulo, "estado": S.PENDIENTE.value},
              {"titulo": s.titulo, "estado": S.ACEPTADA.value}, mod)
    db.commit()
    procesar_pendientes(db)  # queda buscable en el chat de inmediato
    return _leer(db, s, con_autor=True)


def informaciones_de(db: Session, sugerencia_id: int) -> list[Informacion]:
    """Las informaciones que salieron de la sugerencia (todas sus versiones publicadas)."""
    return (
        db.query(Informacion)
        .join(Evidencia, Evidencia.informacion_id == Informacion.id)
        .join(Publicacion, Publicacion.id == Evidencia.publicacion_id)
        .filter(Publicacion.id_externo == f"sugerencia:{sugerencia_id}")
        .distinct().all()
    )


@router.post("/{sugerencia_id}/borrar", response_model=SugerenciaRead)
def borrar_sugerencia(
    sugerencia_id: int,
    datos: Rechazo,
    db: Session = Depends(get_db),
    smod=Depends(require_smod),
):
    """Una sugerencia aceptada deja de usarse en el chat. Queda en el historial (el ADMIN puede deshacerlo)."""
    s = db.get(Sugerencia, sugerencia_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sugerencia no encontrada")
    if s.estado != S.ACEPTADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solo se borran sugerencias aceptadas")
    motivo = datos.motivo.strip()
    infos = informaciones_de(db, s.id)
    antes = {"titulo": s.titulo, "estado": s.estado.value, "motivo": s.motivo,
             "informaciones": {str(i.id): i.estado.value for i in infos}}
    for info in infos:
        if info.estado != E.REEMPLAZADA:
            info.estado = E.REEMPLAZADA
            db.add(Verificacion(informacion_id=info.id, resultado=E.REEMPLAZADA, puntuacion=info.confianza,
                                explicacion=f"Sugerencia borrada por {smod.nombre}: {motivo}"))
    db.query(Publicacion).filter(Publicacion.id_externo == f"sugerencia:{s.id}").update({"vigente": False})
    s.estado, s.motivo = S.BORRADA, motivo
    registrar(db, "sugerencias", s.id, "baja", antes, {"titulo": s.titulo, "estado": S.BORRADA.value, "motivo": motivo},
              smod)
    db.query(CacheRespuesta).delete()  # que el chat deje de usarla ya
    db.commit()
    return _leer(db, s, con_autor=True)


@router.post("/{sugerencia_id}/rechazar", response_model=SugerenciaRead)
def rechazar_sugerencia(
    sugerencia_id: int,
    datos: Rechazo,
    db: Session = Depends(get_db),
    mod=Depends(require_smod),
):
    s = _pendiente(db, sugerencia_id)
    s.estado, s.revisor_id, s.revisada_en, s.motivo = S.RECHAZADA, mod.id, datetime.now(timezone.utc), datos.motivo.strip()
    registrar(db, "sugerencias", s.id, "rechazo", {"titulo": s.titulo, "estado": S.PENDIENTE.value},
              {"titulo": s.titulo, "estado": S.RECHAZADA.value, "motivo": s.motivo}, mod)
    db.commit()
    return _leer(db, s, con_autor=True)
