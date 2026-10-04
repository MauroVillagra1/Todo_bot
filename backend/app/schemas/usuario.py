"""
Schemas Pydantic para Usuario.

Convención usada en todo el proyecto:
  - *Base   → campos compartidos entre Create y Read
  - *Create → lo que recibe la API (sin id, sin timestamps)
  - *Read   → lo que devuelve la API (con id y timestamps, sin password)
  - *Update → campos opcionales para PATCH
"""
from datetime import datetime
from typing import Annotated

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
    """Datos necesarios para crear un usuario (solo ADMIN o consola)."""
    email: EmailInstitucional
    rol: RolEnum = RolEnum.MIEMBRO
    password: Password


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
    email: EmailInstitucional | None = None
    rol: RolEnum | None = None
    activo: bool | None = None
    password: Password | None = None
