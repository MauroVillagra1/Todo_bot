"""
Schemas para el dominio académico base:
  Materia, PeriodoAcademico, Comision, UsuarioComision.
"""
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.academico import DuracionEnum, TipoPeriodoEnum


# ── Materia ───────────────────────────────────────────────────────────────────

class MateriaBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=200)
    codigo: str = Field(..., min_length=2, max_length=20, examples=["MAT101"])
    duracion: DuracionEnum


class MateriaCreate(MateriaBase):
    pass


class MateriaRead(MateriaBase):
    id: int
    creado_en: datetime

    model_config = {"from_attributes": True}


# ── PeriodoAcademico ──────────────────────────────────────────────────────────

class PeriodoAcademicoBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100, examples=["2025 — Primer Cuatrimestre"])
    tipo: TipoPeriodoEnum
    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def validate_fechas(self) -> "PeriodoAcademicoBase":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PeriodoAcademicoCreate(PeriodoAcademicoBase):
    pass


class PeriodoAcademicoRead(PeriodoAcademicoBase):
    id: int
    creado_en: datetime

    model_config = {"from_attributes": True}


# ── Comision ──────────────────────────────────────────────────────────────────

class ComisionBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50, examples=["2K1"])
    periodo_id: int


class ComisionCreate(ComisionBase):
    pass


class ComisionRead(ComisionBase):
    id: int
    creado_en: datetime
    # Datos del período embebidos para respuestas enriquecidas
    periodo: PeriodoAcademicoRead | None = None

    model_config = {"from_attributes": True}


# ── UsuarioComision ───────────────────────────────────────────────────────────

class UsuarioComisionCreate(BaseModel):
    usuario_id: int
    comision_id: int


class UsuarioComisionRead(UsuarioComisionCreate):
    id: int
    inscripto_en: datetime

    model_config = {"from_attributes": True}
