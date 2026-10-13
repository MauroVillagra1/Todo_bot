"""
Tokens JWT de la sesión, con el patrón Factory (PyJWT, HS256).

  TokenFactory.crear("access", usuario)    → token corto que va en cada pedido (Authorization: Bearer)
  TokenFactory.crear("refresh", usuario)   → token largo que solo sirve para pedir un access nuevo
  TokenFactory.validar(token, "access")    → claims, o TokenInvalido

Cada tipo de token es una clase registrada en la fábrica con su duración y sus claims propios:
agregar otro (ej. uno para confirmar un mail) es registrar una clase, sin tocar a quien los usa.

Todos los tokens llevan sub (id del usuario), typ (tipo), ver (versión de sesión del usuario),
iat, exp, jti, iss y aud. Al validar se exigen el algoritmo, el emisor, el destinatario y el tipo:
un refresh no sirve como access ni al revés. Subir `usuario.version_sesion` (cerrar sesión,
cambiar la contraseña) invalida todos los tokens emitidos antes.
"""
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import jwt

from app.core.config import get_settings

EMISOR = "utnia-api"
DESTINATARIO = "utnia-web"
ALGORITMOS_PERMITIDOS = ["HS256", "HS384", "HS512"]  # nunca "none" ni asimétricos con la misma clave


class TokenInvalido(Exception):
    """Token vencido, mal firmado, de otro tipo o con datos que faltan."""


class TipoDeToken(ABC):
    """Producto de la fábrica: cuánto dura un tipo de token y qué agrega al payload."""
    nombre: ClassVar[str]

    @abstractmethod
    def duracion(self) -> timedelta: ...

    def claims_extra(self, usuario) -> dict:
        return {}


class TokenFactory:
    _tipos: ClassVar[dict[str, type[TipoDeToken]]] = {}

    @classmethod
    def registrar(cls, tipo: type[TipoDeToken]) -> type[TipoDeToken]:
        """Decorador: suma un tipo de token a la fábrica."""
        cls._tipos[tipo.nombre] = tipo
        return tipo

    @classmethod
    def _tipo(cls, nombre: str) -> TipoDeToken:
        if nombre not in cls._tipos:
            raise ValueError(f"Tipo de token desconocido: {nombre}")
        return cls._tipos[nombre]()

    @classmethod
    def crear(cls, nombre: str, usuario) -> str:
        tipo = cls._tipo(nombre)
        settings = get_settings()
        ahora = datetime.now(timezone.utc)
        payload = {
            "sub": str(usuario.id),
            "typ": tipo.nombre,
            "ver": usuario.version_sesion or 0,
            "iat": ahora,
            "exp": ahora + tipo.duracion(),
            "jti": secrets.token_urlsafe(16),
            "iss": EMISOR,
            "aud": DESTINATARIO,
            **tipo.claims_extra(usuario),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=_algoritmo())

    @classmethod
    def validar(cls, token: str, nombre: str) -> dict:
        tipo = cls._tipo(nombre)
        try:
            claims = jwt.decode(
                token, get_settings().SECRET_KEY, algorithms=[_algoritmo()],
                audience=DESTINATARIO, issuer=EMISOR,
                options={"require": ["sub", "typ", "ver", "iat", "exp", "jti", "iss", "aud"]},
            )
        except jwt.PyJWTError as e:
            raise TokenInvalido(str(e)) from e
        if claims["typ"] != tipo.nombre:
            raise TokenInvalido(f"Se esperaba un token '{tipo.nombre}'")
        return claims


def _algoritmo() -> str:
    algoritmo = get_settings().ALGORITHM
    if algoritmo not in ALGORITMOS_PERMITIDOS:
        raise ValueError(f"ALGORITHM no permitido: {algoritmo}")
    return algoritmo


@TokenFactory.registrar
class TokenDeAcceso(TipoDeToken):
    nombre = "access"

    def duracion(self) -> timedelta:
        return timedelta(minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES)

    def claims_extra(self, usuario) -> dict:
        return {"rol": getattr(usuario.rol, "value", usuario.rol)}


@TokenFactory.registrar
class TokenDeRefresco(TipoDeToken):
    nombre = "refresh"

    def duracion(self) -> timedelta:
        return timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)


def tokens_de_sesion(usuario) -> dict:
    """Par access + refresh para una sesión nueva (login, registro, renovación)."""
    return {"access_token": TokenFactory.crear("access", usuario),
            "refresh_token": TokenFactory.crear("refresh", usuario)}
