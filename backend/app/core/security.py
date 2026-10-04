"""
Utilidades de seguridad: hashing de contraseñas y manejo de tokens JWT.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Hashing de contraseñas (bcrypt) ───────────────────────────────────────────
# passlib 1.7.4 + bcrypt >= 4.0 tienen un warning que en algunos entornos
# se convierte en error. Este workaround lo silencia.
import bcrypt as _bcrypt  # noqa: E402
import passlib.handlers.bcrypt as _ph_bcrypt  # noqa: E402
_ph_bcrypt.__version__ = _bcrypt.__version__

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Retorna el hash bcrypt de una contraseña en texto plano."""
    # bcrypt tiene un límite de 72 bytes; truncamos para evitar el error
    # con versiones recientes de la librería
    return pwd_context.hash(plain_password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña en texto plano coincida con su hash."""
    return pwd_context.verify(plain_password[:72], hashed_password)


# ── Tokens JWT ────────────────────────────────────────────────────────────────
def create_access_token(
    subject: Any,
    rol: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Genera un token JWT firmado.

    Args:
        subject: Identificador del usuario (típicamente el ID o email).
        rol:     Rol del usuario para incluirlo en el payload.
        expires_delta: Tiempo de vida personalizado; si es None usa el default
                       definido en ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Token JWT como string.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "rol": rol,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodifica y valida un token JWT.

    Returns:
        El payload del token como dict.

    Raises:
        JWTError: Si el token es inválido o expiró.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
