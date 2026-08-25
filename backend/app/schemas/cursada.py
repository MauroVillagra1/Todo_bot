"""
Schemas para Cursada, CursadaProfesor y CursadaExcepcion.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, model_validator

from app.models.cursada import ModalidadEnum, TipoExcepcionEnum

if TYPE_CHECKING:
    # Solo para type hints — no genera ciclos en runtime
    from app.schemas.academico import ComisionRead, MateriaRead


# ── Cursada ───────────────────────────────────────────────────────────────────

class CursadaBase(BaseModel):
    materia_id: int
    comision_id: int
    periodo_id: int
    aula: str | None = Field(None, max_length=50)
    horario: str | None = Field(None, max_length=200, examples=["Lunes y Miércoles 18:00–20:00"])
    modalidad: ModalidadEnum = ModalidadEnum.presencial
    info_adicional: dict[str, Any] | None = None


class CursadaCreate(CursadaBase):
    pass


class CursadaRead(CursadaBase):
    id: int
    creado_en: datetime
    actualizado_en: datetime

    model_config = {"from_attributes": True}


class CursadaReadDetallada(CursadaRead):
    """
    Versión enriquecida con datos de materia y comisión embebidos.
    Se usa en las respuestas del chatbot para dar contexto completo.
    """
    materia: Any | None = None   # MateriaRead en runtime
    comision: Any | None = None  # ComisionRead en runtime


# ── CursadaProfesor ───────────────────────────────────────────────────────────

class CursadaProfesorCreate(BaseModel):
    cursada_id: int
    profesor_id: int


class CursadaProfesorRead(CursadaProfesorCreate):
    id: int
    asignado_en: datetime

    model_config = {"from_attributes": True}


# ── CursadaExcepcion ──────────────────────────────────────────────────────────

class CursadaExcepcionBase(BaseModel):
    cursada_id: int
    tipo: TipoExcepcionEnum
    motivo: str | None = None
    # Suspensión/reubicación es siempre de un SOLO día
    fecha: date
    aula_nueva: str | None = Field(None, max_length=50)
    horario_nuevo: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def validate_tipo(self) -> "CursadaExcepcionBase":
        if self.tipo == TipoExcepcionEnum.reubicacion:
            if not self.aula_nueva and not self.horario_nuevo:
                raise ValueError(
                    "Una reubicación debe indicar aula_nueva, horario_nuevo, o ambos"
                )
        return self


class CursadaExcepcionCreate(CursadaExcepcionBase):
    pass  # cargado_por se inyecta desde el token, no viene en el body


class CursadaExcepcionRead(CursadaExcepcionBase):
    id: int
    cargado_por: int
    creado_en: datetime

    model_config = {"from_attributes": True}
