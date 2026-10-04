"""
Dependencias reutilizables de FastAPI para autenticación y autorización (RBAC).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token

http_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: Session = Depends(get_db),
):
    from app.models.usuario import Usuario

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(Usuario, int(user_id))
    if user is None:
        raise credentials_exception
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")
    return user


def require_rol(*roles: str):
    """Fábrica de dependencias RBAC."""
    role_set = set(roles)
    def _dependency(current_user=Depends(get_current_user)):
        if current_user.rol not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere uno de los roles: {', '.join(sorted(role_set))}",
            )
        return current_user
    return _dependency


# ── Dependencias pre-construidas ──────────────────────────────────────────────

# MIEMBRO: cualquier usuario autenticado y activo
require_miembro = get_current_user

# MOD: revisión de información, contradicciones, fuentes y estados
require_mod = require_rol("MOD", "ADMIN")

# ADMIN: fuentes, configuración, usuarios y administración del sistema
require_admin = require_rol("ADMIN")
