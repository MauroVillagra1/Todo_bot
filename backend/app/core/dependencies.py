"""
Dependencias reutilizables de FastAPI para autenticación y autorización (RBAC).
"""
from datetime import timedelta, timezone

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
    motivo = motivo_suspension(user)
    if motivo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=motivo)
    return user


def motivo_suspension(user) -> str | None:
    """Mensaje para el usuario si su cuenta está suspendida (permanente o temporal), o None."""
    if not user.activo:
        return "Tu cuenta fue suspendida" + (f": {user.motivo_ban}" if user.motivo_ban else ".")
    hasta = user.suspendido_hasta()
    if hasta:
        fecha = hasta.astimezone(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
        return f"Tu cuenta está suspendida hasta el {fecha}" + (f": {user.motivo_ban}" if user.motivo_ban else ".")
    return None


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
