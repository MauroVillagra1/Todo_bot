"""
Router del historial de cambios (solo ADMIN).
  GET  /api/v1/historial?usuario_id=&tabla=&accion=&desde=&hasta=&page=  → cambios, del más nuevo al más viejo
  GET  /api/v1/historial/autores                                          → quiénes hicieron cambios (para filtrar)
  POST /api/v1/historial/{id}/deshacer                                    → vuelve atrás ese cambio
Ver services/auditoria.py: qué se puede deshacer y cómo.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.auditoria import RegistroCambios
from app.models.usuario import Usuario
from app.services import auditoria

router = APIRouter(prefix="/historial", tags=["Historial de cambios"])

ARGENTINA = timezone(timedelta(hours=-3))


class CambioRead(BaseModel):
    id: int
    fecha: datetime
    tabla: str
    seccion: str
    accion: str
    registro_id: int
    resumen: str
    usuario_id: int
    usuario: str
    valor_anterior: dict | None
    valor_nuevo: dict | None
    deshecho_por_id: int | None
    deshacible: bool


class PaginaCambios(BaseModel):
    items: list[CambioRead]
    total: int
    page: int
    page_size: int


class Autor(BaseModel):
    id: int
    nombre: str
    email: str
    cambios: int


def _leer(r: RegistroCambios, u: Usuario | None) -> CambioRead:
    return CambioRead(
        id=r.id, fecha=r.fecha, tabla=r.tabla_afectada, seccion=auditoria.NOMBRES_TABLA.get(r.tabla_afectada, r.tabla_afectada),
        accion=r.accion, registro_id=r.registro_id, resumen=auditoria.resumen(r), usuario_id=r.usuario_id,
        usuario=f"{u.nombre} ({u.email})" if u else f"#{r.usuario_id}",
        valor_anterior=r.valor_anterior, valor_nuevo=r.valor_nuevo, deshecho_por_id=r.deshecho_por_id,
        deshacible=auditoria.deshacible(r),
    )


def _inicio_del_dia(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=ARGENTINA)


@router.get("", response_model=PaginaCambios)
def listar(
    usuario_id: int | None = None,
    tabla: str | None = None,
    accion: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    consulta = db.query(RegistroCambios, Usuario).outerjoin(Usuario, Usuario.id == RegistroCambios.usuario_id)
    if usuario_id:
        consulta = consulta.filter(RegistroCambios.usuario_id == usuario_id)
    if tabla:
        consulta = consulta.filter(RegistroCambios.tabla_afectada == tabla)
    if accion:
        consulta = consulta.filter(RegistroCambios.accion == accion)
    if desde:
        consulta = consulta.filter(RegistroCambios.fecha >= _inicio_del_dia(desde))
    if hasta:  # el día "hasta" completo
        consulta = consulta.filter(RegistroCambios.fecha < _inicio_del_dia(hasta + timedelta(days=1)))
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    total = consulta.count()
    filas = consulta.order_by(RegistroCambios.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginaCambios(items=[_leer(r, u) for r, u in filas], total=total, page=page, page_size=page_size)


@router.get("/autores", response_model=list[Autor])
def autores(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    filas = (
        db.query(Usuario, func.count(RegistroCambios.id))
        .join(RegistroCambios, RegistroCambios.usuario_id == Usuario.id)
        .group_by(Usuario.id).order_by(Usuario.nombre).all()
    )
    return [Autor(id=u.id, nombre=u.nombre, email=u.email, cambios=n) for u, n in filas]


@router.post("/{cambio_id}/deshacer", response_model=CambioRead)
def deshacer(cambio_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    r = db.get(RegistroCambios, cambio_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cambio no encontrado")
    nueva = auditoria.deshacer(db, r, admin)
    return _leer(nueva, admin)
