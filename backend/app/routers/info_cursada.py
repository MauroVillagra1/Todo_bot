"""
Router InfoCursada — el profesor carga/actualiza la info de su cursada:
condiciones de aprobación, parciales, TFI, modalidad, etc.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_profesor
from app.models.cursada import CursadaProfesor
from app.models.info_cursada import InfoCursada
from app.models.usuario import RolEnum, Usuario

router = APIRouter(prefix="/info-cursada", tags=["Info del cursado"])


class InfoCursadaPayload(BaseModel):
    cursada_id: int
    condiciones_aprobacion: str | None = None
    cantidad_parciales: int | None = None
    tiene_tfi: bool | None = False
    descripcion_tfi: str | None = None
    modalidad_cursado: str | None = None
    info_adicional: str | None = None


class InfoCursadaRead(InfoCursadaPayload):
    id: int
    cargado_por: int
    model_config = {"from_attributes": True}


def _verificar_acceso(cursada_id: int, usuario: Usuario, db: Session) -> None:
    if usuario.rol == RolEnum.administrador:
        return
    asignado = db.query(CursadaProfesor).filter(
        CursadaProfesor.cursada_id == cursada_id,
        CursadaProfesor.profesor_id == usuario.id,
    ).first()
    if not asignado:
        raise HTTPException(
            status_code=403,
            detail="Solo podés cargar info en cursadas donde estás asignado como profesor",
        )


@router.put("/{cursada_id}", response_model=InfoCursadaRead)
def guardar_info(
    cursada_id: int,
    data: InfoCursadaPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_profesor),
):
    """Crea o actualiza la info del cursado (upsert). Solo el profesor asignado o admin."""
    if data.cursada_id != cursada_id:
        raise HTTPException(status_code=422, detail="cursada_id no coincide")

    _verificar_acceso(cursada_id, current_user, db)

    obj = db.query(InfoCursada).filter(InfoCursada.cursada_id == cursada_id).first()
    if obj:
        # Actualizar
        for field, value in data.model_dump(exclude={"cursada_id"}).items():
            setattr(obj, field, value)
        obj.cargado_por = current_user.id
    else:
        obj = InfoCursada(**data.model_dump(), cargado_por=current_user.id)
        db.add(obj)

    try:
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al guardar la información")

    return obj


@router.get("/{cursada_id}", response_model=InfoCursadaRead | None)
def obtener_info(
    cursada_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Devuelve la info del cursado. Visible para cualquier usuario autenticado."""
    return db.query(InfoCursada).filter(InfoCursada.cursada_id == cursada_id).first()
