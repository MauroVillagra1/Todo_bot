"""
Schemas para autenticación (login y respuesta de token).
"""
from pydantic import BaseModel, EmailStr, Field, field_validator

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
    """Respuesta del endpoint de login."""
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioRead


class RegistroSolicitud(BaseModel):
    """Paso 1 del registro: datos de la cuenta; se manda un código al mail."""
    nombre: str = Field(..., min_length=2, max_length=150)
    email: EmailInstitucional
    password: Password


class CodigoIngresado(BaseModel):
    email: EmailInstitucional
    codigo: str = Field(..., pattern=r"^\d{6}$")


class RecuperacionSolicitud(BaseModel):
    email: EmailInstitucional


class RecuperacionConfirmacion(CodigoIngresado):
    password: Password


class Mensaje(BaseModel):
    mensaje: str
