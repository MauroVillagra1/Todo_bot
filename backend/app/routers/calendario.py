"""
Router del calendario académico.
  GET    /api/v1/calendario          → todas las actividades (cualquier usuario: también se muestran en el chat)
  POST   /api/v1/calendario          → agregar (ADMIN)
  PATCH  /api/v1/calendario/{id}     → corregir (ADMIN)
  DELETE /api/v1/calendario/{id}     → borrar (ADMIN)
Todo cambio queda en registro_cambios y vacía la caché del chat.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.auditoria import RegistroCambios
from app.models.cache import CacheRespuesta
from app.models.calendario import CATEGORIAS, EventoCalendario

router = APIRouter(prefix="/calendario", tags=["Calendario académico"])

CAMPOS = ("fecha_inicio", "fecha_fin", "actividad", "categoria", "detalle")


class EventoBase(BaseModel):
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    actividad: str | None = Field(None, min_length=3, max_length=300)
    categoria: str | None = None
    detalle: str | None = Field(None, max_length=300)

    @field_validator("categoria")
    @classmethod
    def _categoria(cls, v):
        if v is not None and v not in CATEGORIAS:
            raise ValueError(f"Categoría inválida: {', '.join(CATEGORIAS)}")
        return v

    @field_validator("detalle", mode="before")
    @classmethod
    def _vacio_a_none(cls, v):
        return (v or "").strip() or None


class EventoCreate(EventoBase):
    fecha_inicio: date
    actividad: str = Field(min_length=3, max_length=300)
    categoria: str = "OTRO"


class EventoRead(EventoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


def _foto(e: EventoCalendario) -> dict:
    return {c: (v.isoformat() if isinstance(v := getattr(e, c), date) else v) for c in CAMPOS}


def _validar(e: EventoCalendario) -> None:
    if e.fecha_fin and e.fecha_fin < e.fecha_inicio:
        raise HTTPException(422, "La fecha de fin tiene que ser igual o posterior a la de inicio")
    if e.fecha_fin == e.fecha_inicio:
        e.fecha_fin = None


def _auditar(db: Session, e: EventoCalendario, accion: str, antes: dict | None, despues: dict | None, admin) -> None:
    db.query(CacheRespuesta).delete()
    db.add(RegistroCambios(tabla_afectada="calendario_eventos", registro_id=e.id, valor_anterior=antes,
                           valor_nuevo=despues, accion=accion, usuario_id=admin.id))


@router.get("/", response_model=list[EventoRead])
def listar(db: Session = Depends(get_db), _usuario=Depends(get_current_user)):
    return db.query(EventoCalendario).order_by(EventoCalendario.fecha_inicio, EventoCalendario.id).all()


@router.post("/", response_model=EventoRead, status_code=status.HTTP_201_CREATED)
def crear(datos: EventoCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    e = EventoCalendario(**datos.model_dump())
    e.actividad = e.actividad.strip()
    _validar(e)
    db.add(e)
    db.flush()
    _auditar(db, e, "creacion", None, _foto(e), admin)
    db.commit()
    return e


@router.patch("/{evento_id}", response_model=EventoRead)
def actualizar(evento_id: int, datos: EventoBase, db: Session = Depends(get_db), admin=Depends(require_admin)):
    e = db.get(EventoCalendario, evento_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Actividad no encontrada")
    antes = _foto(e)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("fecha_inicio", "actividad", "categoria"):
            raise HTTPException(422, f"«{campo}» no puede quedar vacío")
        setattr(e, campo, valor.strip() if campo == "actividad" else valor)
    try:
        _validar(e)
    except HTTPException:
        db.rollback()
        raise
    _auditar(db, e, "actualizacion", antes, _foto(e), admin)
    db.commit()
    return e


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(evento_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    e = db.get(EventoCalendario, evento_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Actividad no encontrada")
    _auditar(db, e, "eliminacion", _foto(e), None, admin)
    db.delete(e)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
