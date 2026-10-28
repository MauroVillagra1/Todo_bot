"""
Router de mesas de examen: la planilla del panel que usa el chat. Editan SMOD y ADMIN; las fechas
las lee cualquier usuario (se muestran en el calendario).
  GET/POST          /api/v1/mesas/fechas         → turnos: mesa, cierre de inscripción y fecha del examen
  PATCH/DELETE      /api/v1/mesas/fechas/{id}
  GET/POST          /api/v1/mesas/materias       → en qué mesa se rinde cada materia y su tribunal
  PATCH/DELETE      /api/v1/mesas/materias/{id}
Todo cambio queda en registro_cambios y vacía la caché del chat.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_smod
from app.ingest.datos_mesas import norma
from app.models.auditoria import RegistroCambios
from app.models.cache import CacheRespuesta
from app.models.mesa import MesaFecha, MesaMateria

router = APIRouter(prefix="/mesas", tags=["Mesas de examen"])

HORA = r"^([01]\d|2[0-3]):[0-5]\d$"
SEDES = ("Casa Central", "Anexo Concepción")
CAMPOS_FECHA = ("mesa", "turno", "cierre_inscripcion", "fecha_examen")
CAMPOS_MATERIA = ("materia", "mesa", "sede", "presidente", "vocal1", "vocal2", "hora", "anio_tribunal")


class FechaBase(BaseModel):
    mesa: int | None = Field(None, ge=1, le=3)
    turno: int | None = Field(None, ge=1, le=20)
    cierre_inscripcion: date | None = None
    fecha_examen: date | None = None


class FechaCreate(FechaBase):
    mesa: int = Field(ge=1, le=3)
    cierre_inscripcion: date
    fecha_examen: date


class FechaRead(FechaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MateriaBase(BaseModel):
    materia: str | None = Field(None, min_length=2, max_length=200)
    mesa: int | None = Field(None, ge=1, le=3)
    sede: str | None = None
    presidente: str | None = Field(None, max_length=120)
    vocal1: str | None = Field(None, max_length=120)
    vocal2: str | None = Field(None, max_length=120)
    hora: str | None = None
    anio_tribunal: int | None = Field(None, ge=2000, le=2100)

    @field_validator("presidente", "vocal1", "vocal2", "hora", mode="before")
    @classmethod
    def _vacio_a_none(cls, v):
        return (v or "").strip() or None

    @field_validator("hora")
    @classmethod
    def _hora(cls, v):
        import re
        if v and not re.match(HORA, v):
            raise ValueError("Hora inválida (HH:MM)")
        return v

    @field_validator("sede")
    @classmethod
    def _sede(cls, v):
        if v is not None and v not in SEDES:
            raise ValueError(f"Sede: {' o '.join(SEDES)}")
        return v


class MateriaCreate(MateriaBase):
    materia: str = Field(min_length=2, max_length=200)
    mesa: int = Field(ge=1, le=3)
    sede: str = "Casa Central"


class MateriaRead(MateriaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


def _foto(obj, campos) -> dict:
    return {c: (v.isoformat() if isinstance(v := getattr(obj, c), date) else v) for c in campos}


def _auditar(db: Session, tabla: str, obj, accion: str, antes: dict | None, despues: dict | None, admin) -> None:
    db.query(CacheRespuesta).delete()  # el chat responde mesas con SQL: que se vea el cambio ya
    db.add(RegistroCambios(tabla_afectada=tabla, registro_id=obj.id, valor_anterior=antes, valor_nuevo=despues,
                           accion=accion, usuario_id=admin.id))


def _validar_fecha(f: MesaFecha) -> None:
    if f.cierre_inscripcion > f.fecha_examen:
        raise HTTPException(422, "El cierre de inscripción tiene que ser antes (o el mismo día) que el examen")


# ── Fechas ────────────────────────────────────────────────────────────────────

@router.get("/fechas", response_model=list[FechaRead])
def listar_fechas(db: Session = Depends(get_db), _usuario=Depends(get_current_user)):
    return db.query(MesaFecha).order_by(MesaFecha.fecha_examen, MesaFecha.mesa).all()


@router.post("/fechas", response_model=FechaRead, status_code=status.HTTP_201_CREATED)
def crear_fecha(datos: FechaCreate, db: Session = Depends(get_db), admin=Depends(require_smod)):
    f = MesaFecha(**datos.model_dump())
    _validar_fecha(f)
    db.add(f)
    db.flush()
    _auditar(db, "mesas_fechas", f, "creacion", None, _foto(f, CAMPOS_FECHA), admin)
    db.commit()
    return f


@router.patch("/fechas/{fecha_id}", response_model=FechaRead)
def actualizar_fecha(fecha_id: int, datos: FechaBase, db: Session = Depends(get_db), admin=Depends(require_smod)):
    f = db.get(MesaFecha, fecha_id) or _no_existe()
    antes = _foto(f, CAMPOS_FECHA)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        if valor is None and campo != "turno":
            raise HTTPException(422, f"«{campo}» no puede quedar vacío")
        setattr(f, campo, valor)
    try:
        _validar_fecha(f)
    except HTTPException:
        db.rollback()
        raise
    _auditar(db, "mesas_fechas", f, "actualizacion", antes, _foto(f, CAMPOS_FECHA), admin)
    db.commit()
    return f


@router.delete("/fechas/{fecha_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_fecha(fecha_id: int, db: Session = Depends(get_db), admin=Depends(require_smod)):
    f = db.get(MesaFecha, fecha_id) or _no_existe()
    _auditar(db, "mesas_fechas", f, "eliminacion", _foto(f, CAMPOS_FECHA), None, admin)
    db.delete(f)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Materias y tribunales ─────────────────────────────────────────────────────

@router.get("/materias", response_model=list[MateriaRead])
def listar_materias(db: Session = Depends(get_db), _admin=Depends(require_smod)):
    return db.query(MesaMateria).order_by(MesaMateria.mesa, MesaMateria.materia, MesaMateria.sede).all()


@router.post("/materias", response_model=MateriaRead, status_code=status.HTTP_201_CREATED)
def crear_materia(datos: MateriaCreate, db: Session = Depends(get_db), admin=Depends(require_smod)):
    valores = datos.model_dump()
    valores["materia"] = valores["materia"].strip()
    m = MesaMateria(materia_norm=norma(valores["materia"]), **valores)
    db.add(m)
    db.flush()
    _auditar(db, "mesas_materias", m, "creacion", None, _foto(m, CAMPOS_MATERIA), admin)
    db.commit()
    return m


@router.patch("/materias/{materia_id}", response_model=MateriaRead)
def actualizar_materia(materia_id: int, datos: MateriaBase, db: Session = Depends(get_db),
                       admin=Depends(require_smod)):
    m = db.get(MesaMateria, materia_id) or _no_existe()
    antes = _foto(m, CAMPOS_MATERIA)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        if valor is None and campo in ("materia", "mesa", "sede"):
            raise HTTPException(422, f"«{campo}» no puede quedar vacío")
        setattr(m, campo, valor.strip() if campo == "materia" else valor)
    m.materia_norm = norma(m.materia)
    _auditar(db, "mesas_materias", m, "actualizacion", antes, _foto(m, CAMPOS_MATERIA), admin)
    db.commit()
    return m


@router.delete("/materias/{materia_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_materia(materia_id: int, db: Session = Depends(get_db), admin=Depends(require_smod)):
    m = db.get(MesaMateria, materia_id) or _no_existe()
    _auditar(db, "mesas_materias", m, "eliminacion", _foto(m, CAMPOS_MATERIA), None, admin)
    db.delete(m)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _no_existe():
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
