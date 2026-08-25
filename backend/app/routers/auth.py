"""
Router de autenticación.
  POST /api/v1/auth/login  → recibe email+password, devuelve JWT
  GET  /api/v1/auth/me     → devuelve el usuario autenticado actual
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.usuario import UsuarioRead

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica al usuario y devuelve un token JWT.
    El token incluye el ID y el rol del usuario en el payload.
    """
    user: Usuario | None = (
        db.query(Usuario)
        .filter(Usuario.email == credentials.email, Usuario.activo == True)  # noqa: E712
        .first()
    )

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=user.id, rol=user.rol.value)

    return TokenResponse(
        access_token=token,
        usuario=UsuarioRead.model_validate(user),
    )


@router.get("/me", response_model=UsuarioRead)
def get_me(current_user: Usuario = Depends(get_current_user)):
    """Devuelve los datos del usuario que realizó la petición."""
    return current_user
