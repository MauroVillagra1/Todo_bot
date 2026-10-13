"""
Utilidades de seguridad: hashing de contraseñas (bcrypt).
Los tokens JWT de la sesión están en core/tokens.py (TokenFactory).
"""
from passlib.context import CryptContext

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


# Hash de una contraseña cualquiera: si el email no existe se verifica igual contra este,
# así el login tarda lo mismo y no revela qué cuentas existen por el tiempo de respuesta
HASH_DE_RELLENO = "$2b$12$ntSbY9r0re/qEGwDi3Hlx.vsUa8d9P4zT1CDVKORUPT.88u9IOCfu"  # bcrypt de un texto cualquiera (fijo: no se calcula al arrancar)
