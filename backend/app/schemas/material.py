"""
Schemas para MaterialApoyo.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.material import TipoMaterialEnum


class MaterialApoyoBase(BaseModel):
    cursada_id: int
    tipo: TipoMaterialEnum
    titulo: str = Field(..., min_length=2, max_length=255)
    url: str | None = None
    descripcion: str | None = None


class MaterialApoyoCreate(MaterialApoyoBase):
    pass  # cargado_por se inyecta desde el token en el servicio


class MaterialApoyoRead(MaterialApoyoBase):
    id: int
    cargado_por: int
    creado_en: datetime

    model_config = {"from_attributes": True}
