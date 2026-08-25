"""
Dependencias reutilizables de FastAPI para autenticación y autorización (RBAC).
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Grupos de roles
_ROLES_STAFF      = {"administrador", "administrativo", "jefe_departamento", "profesor", "profesor_directivo"}
_ROLES_PROFESORES = {"profesor", "profesor_directivo"}
_ROLES_ADMIN_ALL  = {"administrador"}
_ROLES_ADMIN_ACAD = {"administrador", "jefe_departamento"}
_ROLES_CALENDARIO = {"administrador", "administrativo"}


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    from app.models.usuario import Usuario

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
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

# Cualquier usuario autenticado
require_authenticated = get_current_user

# Solo administrador del sistema
require_admin = require_rol("administrador")

# Administrador + administrativo (gestión calendario)
require_calendario = require_rol("administrador", "administrativo")

# Administrador + jefe de departamento (gestión académica)
require_acad_admin = require_rol("administrador", "jefe_departamento")

# Todo el staff (no alumno)
require_staff = require_rol(
    "administrador", "administrativo", "jefe_departamento",
    "profesor", "profesor_directivo",
)

# Solo profesores (y alias legacy)
require_profesor = require_rol("profesor", "profesor_directivo")
