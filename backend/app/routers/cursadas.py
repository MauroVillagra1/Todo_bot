"""
Router de cursadas, asignación de profesores y excepciones.

Permisos:
  - Crear/modificar cursadas → administrador / jefe_departamento
  - Cargar excepciones → profesor (solo sus propias cursadas) o administrador
  - Leer → cualquier usuario autenticado (filtrado por rol)
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_acad_admin, require_staff
from app.models.cursada import Cursada, CursadaExcepcion, CursadaProfesor
from app.models.usuario import RolEnum, Usuario
from app.schemas.cursada import (
    CursadaCreate, CursadaExcepcionCreate, CursadaExcepcionRead,
    CursadaProfesorCreate, CursadaProfesorRead, CursadaRead,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/cursadas", tags=["Cursadas"])

# Días de la semana en español (para validar coincidencia de fecha con horario)
_DIAS_ES = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}
_DIAS_NORM = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}


def _dias_en_horario(horario: str | None) -> set[int]:
    """Extrae los índices de día (0=lunes…6=domingo) que aparecen en el texto del horario."""
    if not horario:
        return set()
    horario_lower = horario.lower()
    return {v for k, v in _DIAS_NORM.items() if k in horario_lower}


def _verificar_acceso_profesor(cursada_id: int, usuario: Usuario, db: Session) -> Cursada:
    """Verifica que el usuario sea profesor asignado a la cursada. Devuelve la cursada."""
    cursada = db.get(Cursada, cursada_id)
    if not cursada:
        raise HTTPException(status_code=404, detail="Cursada no encontrada")

    if usuario.rol == RolEnum.administrador:
        return cursada  # admin puede todo

    # Verificar que es profesor de esa cursada
    asignado = db.query(CursadaProfesor).filter(
        CursadaProfesor.cursada_id == cursada_id,
        CursadaProfesor.profesor_id == usuario.id,
    ).first()
    if not asignado:
        raise HTTPException(
            status_code=403,
            detail="Solo podés gestionar cursadas donde estás asignado como profesor",
        )
    return cursada


# ── CRUD Cursadas ─────────────────────────────────────────────────────────────

@router.post("/", response_model=CursadaRead, status_code=201)
def crear_cursada(
    data: CursadaCreate,
    db: Session = Depends(get_db),
    _=Depends(require_acad_admin),
):
    obj = Cursada(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/", response_model=PaginatedResponse[CursadaRead])
def listar_cursadas(
    comision_id: int | None = None,
    periodo_id: int | None = None,
    solo_mias: bool = False,
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista cursadas.
    - Alumnos: solo su comisión.
    - Profesores: todas, o solo las suyas con ?solo_mias=true.
    - Admin/jefe/administrativo: todas.
    """
    query = db.query(Cursada)

    if current_user.rol == RolEnum.alumno:
        comisiones_alumno = [uc.comision_id for uc in current_user.comisiones]
        query = query.filter(Cursada.comision_id.in_(comisiones_alumno))
    elif current_user.es_profesor or solo_mias:
        # Profesores pueden ver solo las suyas
        ids_cursadas = [cp.cursada_id for cp in current_user.cursadas_como_profesor]
        query = query.filter(Cursada.id.in_(ids_cursadas))
    else:
        if comision_id:
            query = query.filter(Cursada.comision_id == comision_id)

    if periodo_id:
        query = query.filter(Cursada.periodo_id == periodo_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/mias", response_model=list[CursadaRead])
def mis_cursadas(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Devuelve las cursadas asignadas al profesor logueado, con info del horario incluida.
    Útil para poblar selects en el panel del profesor.
    """
    if not current_user.es_profesor and current_user.rol != RolEnum.administrador:
        raise HTTPException(status_code=403, detail="Solo disponible para profesores")

    ids = [cp.cursada_id for cp in current_user.cursadas_como_profesor]
    cursadas = db.query(Cursada).filter(Cursada.id.in_(ids)).all()
    return cursadas


@router.get("/{cursada_id}", response_model=CursadaRead)
def obtener_cursada(
    cursada_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    obj = db.get(Cursada, cursada_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Cursada no encontrada")

    if current_user.rol == RolEnum.alumno:
        comisiones_alumno = [uc.comision_id for uc in current_user.comisiones]
        if obj.comision_id not in comisiones_alumno:
            raise HTTPException(status_code=403, detail="Sin acceso a esta cursada")

    return obj


# ── Asignación de profesores ──────────────────────────────────────────────────

@router.post("/{cursada_id}/profesores", response_model=CursadaProfesorRead, status_code=201)
def asignar_profesor(
    cursada_id: int,
    data: CursadaProfesorCreate,
    db: Session = Depends(get_db),
    _=Depends(require_acad_admin),
):
    if data.cursada_id != cursada_id:
        raise HTTPException(status_code=422, detail="cursada_id en body no coincide con la URL")
    existe = db.query(CursadaProfesor).filter(
        CursadaProfesor.cursada_id == cursada_id,
        CursadaProfesor.profesor_id == data.profesor_id,
    ).first()
    if existe:
        raise HTTPException(status_code=409, detail="El profesor ya está asignado a esta cursada")
    obj = CursadaProfesor(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{cursada_id}/profesores", response_model=list[CursadaProfesorRead])
def listar_profesores_cursada(
    cursada_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(CursadaProfesor).filter(CursadaProfesor.cursada_id == cursada_id).all()


# ── Excepciones (suspensiones / reubicaciones) ────────────────────────────────

@router.post("/{cursada_id}/excepciones", response_model=CursadaExcepcionRead, status_code=201)
def cargar_excepcion(
    cursada_id: int,
    data: CursadaExcepcionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_staff),
):
    """
    Carga una suspensión o reubicación para UN DÍA específico.
    - Profesores: solo en sus propias cursadas.
    - Admin: en cualquier cursada.
    - Advertencia si la fecha no coincide con un día habitual de la cursada.
    """
    if data.cursada_id != cursada_id:
        raise HTTPException(status_code=422, detail="cursada_id en body no coincide con la URL")

    cursada = _verificar_acceso_profesor(cursada_id, current_user, db)

    # Validar coincidencia de día (advertencia, no bloqueo)
    dias_cursada = _dias_en_horario(cursada.horario)
    dia_seleccionado = data.fecha.weekday()
    advertencia = None
    if dias_cursada and dia_seleccionado not in dias_cursada:
        nombre_dia = _DIAS_ES[dia_seleccionado].capitalize()
        dias_nombres = [_DIAS_ES[d].capitalize() for d in sorted(dias_cursada)]
        advertencia = (
            f"La fecha seleccionada ({nombre_dia}) no coincide con los días "
            f"habituales de esta cursada ({', '.join(dias_nombres)}). "
            f"Se registró igual."
        )

    obj = CursadaExcepcion(
        cursada_id=cursada_id,
        tipo=data.tipo,
        motivo=data.motivo,
        fecha=data.fecha,
        aula_nueva=data.aula_nueva,
        horario_nuevo=data.horario_nuevo,
        cargado_por=current_user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    response_data = CursadaExcepcionRead.model_validate(obj).model_dump()
    if advertencia:
        response_data["advertencia"] = advertencia
    return response_data


@router.get("/{cursada_id}/excepciones", response_model=list[CursadaExcepcionRead])
def listar_excepciones(
    cursada_id: int,
    fecha: date | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(CursadaExcepcion).filter(CursadaExcepcion.cursada_id == cursada_id)
    if fecha:
        query = query.filter(CursadaExcepcion.fecha == fecha)
    else:
        # Por defecto: solo excepciones desde hoy en adelante
        query = query.filter(CursadaExcepcion.fecha >= date.today())
    return query.order_by(CursadaExcepcion.fecha.asc()).all()
