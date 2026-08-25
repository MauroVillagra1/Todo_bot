"""
Schemas Pydantic para Usuario.

Convención usada en todo el proyecto:
  - *Base   → campos compartidos entre Create y Read
  - *Create → lo que recibe la API (sin id, sin timestamps)
  - *Read   → lo que devuelve la API (con id y timestamps, sin password)
  - *Update → campos opcionales para PATCH
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.usuario import RolEnum


class UsuarioBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150, examples=["Ana García"])
    email: EmailStr
    rol: RolEnum


class UsuarioCreate(UsuarioBase):
    """Datos necesarios para registrar un nuevo usuario."""
    password: str = Field(..., min_length=8, description="Contraseña en texto plano (se hashea en el servicio)")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v


class UsuarioRead(UsuarioBase):
    """Datos que se devuelven al cliente. Nunca incluye el hash."""
    id: int
    activo: bool
    creado_en: datetime
    actualizado_en: datetime

    model_config = {"from_attributes": True}


class UsuarioUpdate(BaseModel):
    """Todos los campos son opcionales para soportar PATCH parcial."""
    nombre: str | None = Field(None, min_length=2, max_length=150)
    email: EmailStr | None = None
    activo: bool | None = None
    password: str | None = Field(None, min_length=8)
