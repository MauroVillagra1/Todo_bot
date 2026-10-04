"""
Schemas para autenticación (login y respuesta de token).
"""
from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.usuario import UsuarioRead


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
