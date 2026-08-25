"""
Router de eventos del calendario académico.

Permisos:
  - Crear/editar eventos: administrador o administrativo.
    - El alcance SIEMPRE es "general" (no se puede restringir a comisión/materia desde aquí).
    - Tipos disponibles: paro, asueto, evento_cultural, otro (NO fecha_examen).
  - Leer: cualquier usuario autenticado.
    - Alumnos: solo eventos generales.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_calendario
from app.models.eventos import AlcanceEventoEnum, EventoCalendario, TipoEventoEnum
from app.models.usuario import Usuario
from app.schemas.eventos import EventoCalendarioRead

router = APIRouter(prefix="/eventos", tags=["Calendario"])

# Tipos permitidos para administrativos (no incluye fecha_examen)
_TIPOS_CALENDARIO = {
    TipoEventoEnum.paro,
    TipoEventoEnum.asueto,
    TipoEventoEnum.evento_cultural,
    TipoEventoEnum.otro,
}


class EventoCalendarioCreateAdmin(BaseModel):
    """Schema restringido para carga por administrativos: sin fecha_examen, alcance siempre general."""
    titulo: str = Field(..., min_length=2, max_length=255)
    tipo: TipoEventoEnum
    motivo: str | None = None
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: str | None = None
    hora_fin: str | None = None

    @model_validator(mode="after")
    def validar(self) -> "EventoCalendarioCreateAdmin":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")
        if self.tipo not in _TIPOS_CALENDARIO:
            raise ValueError("Tipo de evento no permitido. Use: paro, asueto, evento_cultural, otro")
        return self


@router.post("/", response_model=EventoCalendarioRead, status_code=201)
def crear_evento(
    data: EventoCalendarioCreateAdmin,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_calendario),
):
    """
    Crea un evento de calendario. Solo administrador o administrativo.
    El alcance siempre es GENERAL. El origen es el nombre del usuario.
    """
    obj = EventoCalendario(
        titulo=data.titulo,
        tipo=data.tipo,
        origen=current_user.nombre,
        motivo=data.motivo,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
        alcance=AlcanceEventoEnum.general,   # siempre general
        comision_id=None,
        cursada_id=None,
        cargado_por=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{evento_id}", response_model=EventoCalendarioRead)
def modificar_evento(
    evento_id: int,
    data: EventoCalendarioCreateAdmin,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_calendario),
):
    """Modifica un evento existente. Solo quien lo creó o un administrador."""
    obj = db.get(EventoCalendario, evento_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    if current_user.rol != "administrador" and obj.cargado_por != current_user.id:
        raise HTTPException(status_code=403, detail="Solo podés modificar eventos que vos creaste")

    obj.titulo       = data.titulo
    obj.tipo         = data.tipo
    obj.motivo       = data.motivo
    obj.fecha_inicio = data.fecha_inicio
    obj.fecha_fin    = data.fecha_fin
    obj.hora_inicio  = data.hora_inicio
    obj.hora_fin     = data.hora_fin
    obj.origen       = current_user.nombre
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{evento_id}", status_code=204)
def eliminar_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_calendario),
):
    obj = db.get(EventoCalendario, evento_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    if current_user.rol != "administrador" and obj.cargado_por != current_user.id:
        raise HTTPException(status_code=403, detail="Solo podés eliminar eventos que vos creaste")
    db.delete(obj)
    db.commit()


@router.get("/", response_model=list[EventoCalendarioRead])
def listar_eventos(
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    query = db.query(EventoCalendario)

    # Alumnos y profesores: solo eventos generales
    if current_user.rol in ("alumno", "profesor", "profesor_directivo"):
        query = query.filter(EventoCalendario.alcance == AlcanceEventoEnum.general)

    if fecha_desde:
        query = query.filter(EventoCalendario.fecha_fin >= fecha_desde)
    if fecha_hasta:
        query = query.filter(EventoCalendario.fecha_inicio <= fecha_hasta)

    return query.order_by(EventoCalendario.fecha_inicio.asc()).all()


@router.get("/{evento_id}", response_model=EventoCalendarioRead)
def obtener_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = db.get(EventoCalendario, evento_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return obj
