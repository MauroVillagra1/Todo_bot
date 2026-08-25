"""
Router para entidades académicas base: Materias, Períodos, Comisiones.
Lectura abierta a cualquier usuario autenticado.
Creación/modificación restringida a administradores.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_authenticated
from app.models.academico import Comision, Materia, PeriodoAcademico, UsuarioComision
from app.schemas.academico import (
    ComisionCreate, ComisionRead,
    MateriaCreate, MateriaRead,
    PeriodoAcademicoCreate, PeriodoAcademicoRead,
    UsuarioComisionCreate, UsuarioComisionRead,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["Académico"])


# ── Materias ──────────────────────────────────────────────────────────────────

@router.post("/materias", response_model=MateriaRead, status_code=201)
def crear_materia(data: MateriaCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(Materia).filter(Materia.codigo == data.codigo).first():
        raise HTTPException(status_code=409, detail="Ya existe una materia con ese código")
    obj = Materia(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/materias", response_model=PaginatedResponse[MateriaRead])
def listar_materias(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _=Depends(require_authenticated),
):
    offset = (page - 1) * page_size
    total = db.query(Materia).count()
    items = db.query(Materia).offset(offset).limit(page_size).all()
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/materias/{materia_id}", response_model=MateriaRead)
def obtener_materia(materia_id: int, db: Session = Depends(get_db), _=Depends(require_authenticated)):
    obj = db.get(Materia, materia_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return obj


# ── Períodos académicos ────────────────────────────────────────────────────────

@router.post("/periodos", response_model=PeriodoAcademicoRead, status_code=201)
def crear_periodo(data: PeriodoAcademicoCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = PeriodoAcademico(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/periodos", response_model=list[PeriodoAcademicoRead])
def listar_periodos(db: Session = Depends(get_db), _=Depends(require_authenticated)):
    return db.query(PeriodoAcademico).order_by(PeriodoAcademico.fecha_inicio.desc()).all()


@router.get("/periodos/{periodo_id}", response_model=PeriodoAcademicoRead)
def obtener_periodo(periodo_id: int, db: Session = Depends(get_db), _=Depends(require_authenticated)):
    obj = db.get(PeriodoAcademico, periodo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Período no encontrado")
    return obj


# ── Comisiones ────────────────────────────────────────────────────────────────

@router.post("/comisiones", response_model=ComisionRead, status_code=201)
def crear_comision(data: ComisionCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    obj = Comision(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/comisiones", response_model=list[ComisionRead])
def listar_comisiones(db: Session = Depends(get_db), _=Depends(require_authenticated)):
    return db.query(Comision).all()


@router.get("/comisiones/{comision_id}", response_model=ComisionRead)
def obtener_comision(comision_id: int, db: Session = Depends(get_db), _=Depends(require_authenticated)):
    obj = db.get(Comision, comision_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Comisión no encontrada")
    return obj


# ── Inscripciones alumno ↔ comisión ───────────────────────────────────────────

@router.post("/comisiones/inscripciones", response_model=UsuarioComisionRead, status_code=201)
def inscribir_alumno(
    data: UsuarioComisionCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Asigna un alumno a una comisión. Solo administradores."""
    existe = (
        db.query(UsuarioComision)
        .filter(
            UsuarioComision.usuario_id == data.usuario_id,
            UsuarioComision.comision_id == data.comision_id,
        )
        .first()
    )
    if existe:
        raise HTTPException(status_code=409, detail="El alumno ya está inscripto en esa comisión")
    obj = UsuarioComision(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
