"""
Schemas para autenticación (login y respuesta de token).
"""
import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field, field_validator

from app.schemas.usuario import EmailInstitucional, Password, UsuarioRead


class LoginRequest(BaseModel):
    """Credenciales que envía el cliente para iniciar sesión."""
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(BaseModel):
    """Sesión: access token (va en cada pedido) y refresh token (solo para renovarlo)."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioRead


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., max_length=2000)


def _limpiar_nombre(v: str) -> str:
    """Letras (con tildes), espacios, apóstrofo y guion; sin espacios de más."""
    v = re.sub(r"\s+", " ", v).strip()
    if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+", v):
        raise ValueError("Usá solo letras")
    return v


Nombre = Annotated[str, Field(min_length=2, max_length=74), AfterValidator(_limpiar_nombre)]


class RegistroSolicitud(BaseModel):
    """Paso 1 del registro: datos de la cuenta; se manda un código al mail."""
    nombre: Nombre
    apellido: Nombre
    email: EmailInstitucional
    password: Password

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"


class PerfilUpdate(BaseModel):
    """Lo que cada usuario puede cambiar de su cuenta (el mail institucional no)."""
    nombre: Nombre
    apellido: Nombre

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"


class CambioPassword(BaseModel):
    actual: str = Field(..., max_length=200)
    nueva: Password


class CodigoIngresado(BaseModel):
    email: EmailInstitucional
    codigo: str = Field(..., pattern=r"^\d{6}$")


class RecuperacionSolicitud(BaseModel):
    email: EmailInstitucional


class RecuperacionConfirmacion(CodigoIngresado):
    password: Password


class Mensaje(BaseModel):
    mensaje: str
