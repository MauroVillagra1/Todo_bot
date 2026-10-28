"""
Router de autenticación.
  POST /api/v1/auth/login    → recibe email+password, devuelve access + refresh (JWT)
  POST /api/v1/auth/refresh  → con el refresh devuelve un par nuevo (rotación)
  POST /api/v1/auth/logout   → cierra todas las sesiones del usuario (revoca sus tokens)
  GET  /api/v1/auth/me       → devuelve el usuario autenticado actual
  POST /api/v1/auth/registro            → datos de la cuenta; manda un código al mail
  POST /api/v1/auth/registro/verificar  → código correcto: crea la cuenta (USUARIO; docentes MOD) y loguea
  POST /api/v1/auth/recuperar           → manda un código si la cuenta existe
  POST /api/v1/auth/recuperar/confirmar → código correcto: cambia la contraseña
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, motivo_suspension
from app.core.security import HASH_DE_RELLENO, hash_password, verify_password
from app.core.tokens import TokenFactory, TokenInvalido, tokens_de_sesion
from app.models.codigo import CodigoVerificacion, PropositoCodigoEnum as P
from app.models.usuario import Usuario, rol_inicial
from app.schemas.auth import (
    CambioPassword, CodigoIngresado, LoginRequest, Mensaje, PerfilUpdate, RecuperacionConfirmacion, RecuperacionSolicitud,
    RefreshRequest, RegistroSolicitud, TokenResponse,
)
from app.schemas.usuario import UsuarioRead, es_email_institucional
from app.services.email import EmailNoConfigurado, enviar_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


# Fuerza bruta: tras estos errores seguidos la cuenta no puede ingresar por un rato
MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN = timedelta(minutes=15)
CREDENCIALES_INCORRECTAS = "Email o contraseña incorrectos"


def _sesion(usuario: Usuario) -> TokenResponse:
    return TokenResponse(**tokens_de_sesion(usuario), usuario=UsuarioRead.model_validate(usuario))


def _bloqueado(usuario: Usuario) -> bool:
    return bool(usuario.bloqueado_hasta) and _utc(usuario.bloqueado_hasta) > _ahora()


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Devuelve un access token (corto) y un refresh token (largo) con el ID, el rol y la versión de sesión."""
    user: Usuario | None = db.query(Usuario).filter(Usuario.email == credentials.email).first()

    if user and _bloqueado(user):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Demasiados intentos fallidos. Probá de nuevo en 15 minutos.")
    # Sin cuenta se verifica igual contra un hash de relleno: el tiempo de respuesta no
    # revela qué emails existen. Mismo error para dominio no institucional.
    correcta = verify_password(credentials.password, user.password_hash if user else HASH_DE_RELLENO)
    if not user or not correcta or not es_email_institucional(user.email):
        if user:
            user.intentos_fallidos += 1
            if user.intentos_fallidos >= MAX_INTENTOS_LOGIN:
                user.bloqueado_hasta, user.intentos_fallidos = _ahora() + BLOQUEO_LOGIN, 0
                logger.warning("Login bloqueado por intentos fallidos: usuario %s", user.id)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INCORRECTAS,
                            headers={"WWW-Authenticate": "Bearer"})

    # Solo con la contraseña correcta se avisa que la cuenta está suspendida
    motivo = motivo_suspension(user)
    if motivo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=motivo)

    user.intentos_fallidos, user.bloqueado_hasta = 0, None
    db.commit()
    return _sesion(user)


@router.post("/refresh", response_model=TokenResponse)
def renovar(datos: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh válido → par nuevo. Sesión cerrada, contraseña cambiada o cuenta suspendida → 401/403."""
    try:
        claims = TokenFactory.validar(datos.refresh_token, "refresh")
    except TokenInvalido:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión venció. Ingresá de nuevo.")
    user = db.get(Usuario, int(claims["sub"]))
    if user is None or claims["ver"] != user.version_sesion:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión se cerró. Ingresá de nuevo.")
    motivo = motivo_suspension(user)
    if motivo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo)
    return _sesion(user)


@router.post("/logout", response_model=Mensaje)
def logout(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoca todos los tokens del usuario (en todos los dispositivos): útil en PCs compartidas."""
    current_user.version_sesion += 1
    db.commit()
    return Mensaje(mensaje="Sesión cerrada.")


@router.get("/me", response_model=UsuarioRead)
def get_me(current_user: Usuario = Depends(get_current_user)):
    """Devuelve los datos del usuario que realizó la petición."""
    return current_user


@router.patch("/me", response_model=UsuarioRead)
def editar_perfil(datos: PerfilUpdate, current_user: Usuario = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Mi perfil: por ahora solo el nombre y apellido (el mail institucional no se cambia)."""
    current_user.nombre = datos.nombre
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/password", response_model=TokenResponse)
def cambiar_password(datos: CambioPassword, current_user: Usuario = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Pide la contraseña actual. Cierra las demás sesiones y devuelve una nueva para este dispositivo."""
    if not verify_password(datos.actual, current_user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta.")
    if verify_password(datos.nueva, current_user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña nueva tiene que ser distinta de la actual.")
    current_user.password_hash = hash_password(datos.nueva)
    current_user.version_sesion += 1
    db.commit()
    return _sesion(current_user)


# ── Códigos por mail (registro y recuperación) ────────────────────────────────

VIGENCIA_CODIGO = timedelta(minutes=15)
ESPERA_ENTRE_CODIGOS = timedelta(seconds=60)
MAX_CODIGOS_POR_HORA = 5
MAX_INTENTOS = 5
MSG_RECUPERACION = "Si existe una cuenta con ese correo, te enviamos un código de 6 dígitos."
YA_REGISTRADO = "Ya existe una cuenta con ese correo. Iniciá sesión o recuperá tu contraseña."
CODIGO_VENCIDO = "El código venció o no existe. Pedí uno nuevo."


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)  # SQLite las devuelve sin zona


def _hash_codigo(email: str, codigo: str) -> str:
    clave = get_settings().SECRET_KEY.encode()
    return hmac.new(clave, f"{email}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _codigos(db: Session, email: str, proposito: P):
    return db.query(CodigoVerificacion).filter(
        CodigoVerificacion.email == email, CodigoVerificacion.proposito == proposito
    )


def _demasiado_pronto(db: Session, email: str, proposito: P) -> str | None:
    hace_una_hora = _ahora() - timedelta(hours=1)
    recientes = [
        c for c in _codigos(db, email, proposito).order_by(CodigoVerificacion.id.desc()).limit(MAX_CODIGOS_POR_HORA)
        if _utc(c.creado_en) >= hace_una_hora
    ]
    if recientes and _utc(recientes[0].creado_en) > _ahora() - ESPERA_ENTRE_CODIGOS:
        return "Esperá un minuto antes de pedir otro código."
    if len(recientes) >= MAX_CODIGOS_POR_HORA:
        return "Pediste demasiados códigos. Probá de nuevo en una hora."
    return None


def _enviar_codigo(db: Session, email: str, proposito: P, datos: dict) -> None:
    """Invalida los códigos anteriores, crea uno nuevo y lo manda. Solo se guarda si el mail salió."""
    codigo = f"{secrets.randbelow(10**6):06d}"
    for anterior in _codigos(db, email, proposito).filter(CodigoVerificacion.usado.is_(False)):
        anterior.usado = True
    db.add(CodigoVerificacion(
        email=email, proposito=proposito, codigo_hash=_hash_codigo(email, codigo), datos=datos,
        expira_en=_ahora() + VIGENCIA_CODIGO, creado_en=_ahora(),
    ))
    accion = "crear tu cuenta" if proposito == P.REGISTRO else "cambiar tu contraseña"
    try:
        enviar_email(
            email, f"Juliette (UTN FRT): tu código es {codigo}",
            f"Tu código para {accion} en Juliette es: {codigo}\n\n"
            f"Vence en {VIGENCIA_CODIGO.seconds // 60} minutos. Si no lo pediste, ignorá este mail.",
        )
    except EmailNoConfigurado:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El envío de correos todavía no está configurado.")
    except Exception as e:
        db.rollback()
        logger.warning("No se pudo enviar el mail a %s: %s", email, str(e)[:300])
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "No se pudo enviar el mail. Probá de nuevo en unos minutos.")
    db.commit()


def _validar_codigo(db: Session, email: str, proposito: P, codigo: str) -> CodigoVerificacion:
    """Devuelve el código marcado como usado (falta el commit) o corta con 400."""
    vigente = (
        _codigos(db, email, proposito).filter(CodigoVerificacion.usado.is_(False))
        .order_by(CodigoVerificacion.id.desc()).first()
    )
    if not vigente or _utc(vigente.expira_en) < _ahora():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CODIGO_VENCIDO)
    if vigente.intentos >= MAX_INTENTOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Demasiados intentos. Pedí un código nuevo.")
    if not hmac.compare_digest(vigente.codigo_hash, _hash_codigo(email, codigo)):
        vigente.intentos += 1
        db.commit()
        restantes = MAX_INTENTOS - vigente.intentos
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Código incorrecto. Te quedan {restantes} intentos." if restantes
            else "Código incorrecto. Pedí un código nuevo.",
        )
    vigente.usado = True
    return vigente


def _existe(db: Session, email: str) -> bool:
    return db.query(Usuario).filter(Usuario.email == email).first() is not None


@router.post("/registro", response_model=Mensaje)
def solicitar_registro(datos: RegistroSolicitud, db: Session = Depends(get_db)):
    if _existe(db, datos.email):
        raise HTTPException(status.HTTP_409_CONFLICT, YA_REGISTRADO)
    if espera := _demasiado_pronto(db, datos.email, P.REGISTRO):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, espera)
    # La cuenta todavía no existe: nombre y contraseña (hasheada) esperan junto al código
    _enviar_codigo(db, datos.email, P.REGISTRO,
                   {"nombre": datos.nombre_completo, "password_hash": hash_password(datos.password)})
    return Mensaje(mensaje=f"Te enviamos un código de 6 dígitos a {datos.email}.")


@router.post("/registro/verificar", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def verificar_registro(datos: CodigoIngresado, db: Session = Depends(get_db)):
    codigo = _validar_codigo(db, datos.email, P.REGISTRO, datos.codigo)
    if _existe(db, datos.email):  # se creó por otro lado mientras tanto
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, YA_REGISTRADO)
    usuario = Usuario(nombre=codigo.datos["nombre"], email=datos.email, rol=rol_inicial(datos.email),
                      password_hash=codigo.datos["password_hash"])
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return _sesion(usuario)


@router.post("/recuperar", response_model=Mensaje)
def solicitar_recuperacion(datos: RecuperacionSolicitud, db: Session = Depends(get_db)):
    # Misma respuesta exista o no la cuenta: no revela qué correos están registrados
    usuario = db.query(Usuario).filter(Usuario.email == datos.email, Usuario.activo.is_(True)).first()
    if usuario and not _demasiado_pronto(db, datos.email, P.RECUPERACION):
        _enviar_codigo(db, datos.email, P.RECUPERACION, {})
    return Mensaje(mensaje=MSG_RECUPERACION)


@router.post("/recuperar/confirmar", response_model=Mensaje)
def confirmar_recuperacion(datos: RecuperacionConfirmacion, db: Session = Depends(get_db)):
    _validar_codigo(db, datos.email, P.RECUPERACION, datos.codigo)
    usuario = db.query(Usuario).filter(Usuario.email == datos.email, Usuario.activo.is_(True)).first()
    if not usuario:
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, CODIGO_VENCIDO)
    usuario.password_hash = hash_password(datos.password)
    # Contraseña nueva: se cierran las sesiones abiertas (por si alguien más tenía acceso)
    usuario.version_sesion += 1
    usuario.intentos_fallidos, usuario.bloqueado_hasta = 0, None
    db.commit()
    return Mensaje(mensaje="Listo, ya podés iniciar sesión con tu nueva contraseña.")
