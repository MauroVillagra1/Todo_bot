"""
Schemas para autenticación (login y respuesta de token).
"""
from pydantic import BaseModel, EmailStr

from app.schemas.usuario import UsuarioRead


class LoginRequest(BaseModel):
    """Credenciales que envía el cliente para iniciar sesión."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Respuesta del endpoint de login."""
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioRead
