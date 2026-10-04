"""
Schemas Pydantic para Usuario.

Convención usada en todo el proyecto:
  - *Base   → campos compartidos entre Create y Read
  - *Create → lo que recibe la API (sin id, sin timestamps)
  - *Read   → lo que devuelve la API (con id y timestamps, sin password)
  - *Update → campos opcionales para PATCH
"""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.models.usuario import RolEnum


def es_email_institucional(email: str) -> bool:
    """True si el dominio del email está en DOMINIOS_PERMITIDOS."""
    dominio = email.rsplit("@", 1)[-1].lower()
    return dominio in {d.lower() for d in get_settings().DOMINIOS_PERMITIDOS}


def validar_email_institucional(email: str) -> str:
    """Normaliza a minúsculas y rechaza dominios no institucionales."""
    email = email.strip().lower()
    if not es_email_institucional(email):
        raise ValueError("Solo se permiten correos institucionales de la UTN FRT")
    return email


def validar_password(password: str) -> str:
    if not any(c.isdigit() for c in password):
        raise ValueError("La contraseña debe contener al menos un número")
    return password


EmailInstitucional = Annotated[EmailStr, AfterValidator(validar_email_institucional)]
Password = Annotated[
    str,
    Field(min_length=8, description="Contraseña en texto plano (se hashea en el servicio)"),
    AfterValidator(validar_password),
]


class UsuarioBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150, examples=["Ana García"])
    email: EmailStr
    rol: RolEnum


class UsuarioCreate(UsuarioBase):
    """Datos para crear un usuario por consola (create_admin.py). Desde la app solo hay registro público."""
    email: EmailInstitucional
    rol: RolEnum = RolEnum.MIEMBRO
    password: Password


class UsuarioRead(UsuarioBase):
    """Datos que se devuelven al cliente. Nunca incluye el hash."""
    id: int
    activo: bool  # False = suspensión permanente
    baneado_hasta: datetime | None = None
    motivo_ban: str | None = None
    creado_en: datetime
    actualizado_en: datetime

    model_config = {"from_attributes": True}


class CambioRol(BaseModel):
    """Desde la app un ADMIN solo da o quita el rango de moderador."""
    rol: Literal[RolEnum.MIEMBRO, RolEnum.MOD]


class Suspension(BaseModel):
    dias: int | None = Field(None, ge=1, le=3650, description="Vacío = permanente")
    motivo: str = Field(min_length=3, max_length=300)
