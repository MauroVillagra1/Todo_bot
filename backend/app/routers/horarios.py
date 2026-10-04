"""
Router de la grilla de horarios (solo ADMIN): la tabla del panel ordenada por
año → comisión → bloques (materia, docente, aula).
  GET    /api/v1/horarios        → los mismos bloques que usa el chat
  POST   /api/v1/horarios        → agrega un bloque a mano (sin PDF de origen)
  PATCH  /api/v1/horarios/{id}   → corrige materia, docente, aula, día, hora…
  DELETE /api/v1/horarios/{id}
Todo cambio queda en registro_cambios. Si el PDF de origen se publica de nuevo
con cambios, sus bloques se regeneran desde el PDF nuevo.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.ingest.horarios import normalizar_comision, normalizar_materia
from app.models.auditoria import RegistroCambios
from app.models.horario import HorarioClase
from app.models.ingesta import Documento
from app.rag.horarios import mas_recientes, vigentes

router = APIRouter(prefix="/horarios", tags=["Horarios"])

HORA = r"^([01]\d|2[0-3]):[0-5]\d$"
CAMPOS = ("comision", "anio", "plan", "turno", "periodo", "aula", "dia", "inicio", "fin",
          "materia", "docente", "lugar", "electiva")


class BloqueBase(BaseModel):
    @field_validator("comision", check_fields=False)
    @classmethod
    def _comision(cls, v):
        if v is None:
            return v
        c = normalizar_comision(v)
        if not c:
            raise ValueError("Comisión inválida (ej. 1K01)")
        return c

    @field_validator("plan", "turno", "periodo", "aula", "docente", "lugar", check_fields=False)
    @classmethod
    def _vacio_a_none(cls, v):
        return (v or "").strip() or None


class BloqueCreate(BloqueBase):
    comision: str
    anio: int | None = Field(None, ge=1, le=6)
    plan: str | None = Field(None, max_length=10)
    turno: str | None = Field(None, max_length=30)
    periodo: str | None = Field(None, max_length=40)
    aula: str | None = Field(None, max_length=40)
    dia: int = Field(ge=1, le=6)
    inicio: str = Field(pattern=HORA)
    fin: str = Field(pattern=HORA)
    materia: str = Field(min_length=2, max_length=200)
    docente: str | None = Field(None, max_length=200)
    lugar: str | None = Field(None, max_length=60)
    electiva: bool = False


class BloqueUpdate(BloqueBase):
    comision: str | None = None
    anio: int | None = Field(None, ge=1, le=6)
    plan: str | None = Field(None, max_length=10)
    turno: str | None = Field(None, max_length=30)
    periodo: str | None = Field(None, max_length=40)
    aula: str | None = Field(None, max_length=40)
    dia: int | None = Field(None, ge=1, le=6)
    inicio: str | None = Field(None, pattern=HORA)
    fin: str | None = Field(None, pattern=HORA)
    materia: str | None = Field(None, min_length=2, max_length=200)
    docente: str | None = Field(None, max_length=200)
    lugar: str | None = Field(None, max_length=60)
    electiva: bool | None = None


class BloqueRead(BaseModel):
    id: int
    comision: str | None
    anio: int | None
    plan: str | None
    turno: str | None
    periodo: str | None
    aula: str | None
    dia: int
    inicio: str
    fin: str
    materia: str
    docente: str | None
    lugar: str | None
    electiva: bool
    origen: str  # nombre del PDF o "Carga manual"


def _foto(h: HorarioClase) -> dict:
    return {c: getattr(h, c) for c in CAMPOS}


def _leer(h: HorarioClase, origen: str) -> BloqueRead:
    return BloqueRead(id=h.id, origen=origen, **_foto(h))


def _origen(d) -> str:
    return (d.nombre or d.url.rsplit("/", 1)[-1]) if d is not None else "Carga manual"


def _validar_horas(h: HorarioClase) -> None:
    if h.inicio >= h.fin:
        raise HTTPException(status_code=422,
                            detail="La hora de fin tiene que ser posterior a la de inicio")


def _auditar(db: Session, h: HorarioClase, accion: str, antes: dict | None, despues: dict | None, admin) -> None:
    db.add(RegistroCambios(tabla_afectada="horarios_clases", registro_id=h.id, valor_anterior=antes,
                           valor_nuevo=despues, accion=accion, usuario_id=admin.id))


@router.get("/", response_model=list[BloqueRead])
def listar_horarios(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    filas = mas_recientes(vigentes(db).all())
    filas.sort(key=lambda f: (f[0].anio or 9, f[0].comision or "", f[0].plan or "", f[0].periodo or "",
                              f[0].dia, f[0].inicio))
    return [_leer(h, _origen(d)) for h, d in filas]


@router.post("/", response_model=BloqueRead, status_code=status.HTTP_201_CREATED)
def crear_bloque(datos: BloqueCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    valores = datos.model_dump()
    valores["anio"] = valores["anio"] or int(valores["comision"][0])
    valores["materia"] = valores["materia"].strip()
    h = HorarioClase(documento_id=None, materia_norm=normalizar_materia(valores["materia"])[:200], **valores)
    _validar_horas(h)
    db.add(h)
    db.flush()
    _auditar(db, h, "creacion", None, _foto(h), admin)
    db.commit()
    return _leer(h, _origen(None))


@router.patch("/{bloque_id}", response_model=BloqueRead)
def actualizar_bloque(bloque_id: int, datos: BloqueUpdate, db: Session = Depends(get_db),
                      admin=Depends(require_admin)):
    h = db.get(HorarioClase, bloque_id)
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bloque no encontrado")
    antes = _foto(h)
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("comision", "dia", "inicio", "fin", "materia", "electiva"):
        if campo in cambios and cambios[campo] is None:
            raise HTTPException(status_code=422, detail=f"«{campo}» no puede quedar vacío")
    for campo, valor in cambios.items():
        setattr(h, campo, valor.strip() if campo == "materia" else valor)
    if "materia" in cambios:
        h.materia_norm = normalizar_materia(h.materia)[:200]
    try:
        _validar_horas(h)
    except HTTPException:
        db.rollback()
        raise
    _auditar(db, h, "actualizacion", antes, _foto(h), admin)
    db.commit()
    return _leer(h, _origen(db.get(Documento, h.documento_id) if h.documento_id else None))


@router.delete("/{bloque_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_bloque(bloque_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    h = db.get(HorarioClase, bloque_id)
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bloque no encontrado")
    _auditar(db, h, "eliminacion", _foto(h), None, admin)
    db.delete(h)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
