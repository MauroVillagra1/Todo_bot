"""
Schemas para EventoCalendario.
"""
from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.models.eventos import AlcanceEventoEnum, TipoEventoEnum


class EventoCalendarioBase(BaseModel):
    titulo: str = Field(..., min_length=2, max_length=255)
    tipo: TipoEventoEnum
    origen: str | None = Field(None, max_length=100)
    motivo: str | None = None
    fecha_inicio: date
    fecha_fin: date
    hora_inicio: time | None = None
    hora_fin: time | None = None
    alcance: AlcanceEventoEnum = AlcanceEventoEnum.general
    # Opcionales según alcance
    comision_id: int | None = None
    cursada_id: int | None = None

    @model_validator(mode="after")
    def validate_alcance_y_fechas(self) -> "EventoCalendarioBase":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior o igual a fecha_inicio")

        if self.alcance == AlcanceEventoEnum.comision and not self.comision_id:
            raise ValueError("Se requiere comision_id cuando el alcance es 'comision'")

        if self.alcance == AlcanceEventoEnum.materia_especifica and not self.cursada_id:
            raise ValueError("Se requiere cursada_id cuando el alcance es 'materia_especifica'")

        return self


class EventoCalendarioCreate(EventoCalendarioBase):
    pass  # cargado_por se inyecta desde el token JWT en el servicio


class EventoCalendarioRead(EventoCalendarioBase):
    id: int
    cargado_por: int
    creado_en: datetime

    model_config = {"from_attributes": True}
