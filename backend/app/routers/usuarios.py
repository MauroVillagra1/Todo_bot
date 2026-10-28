"""
Router de usuarios (gestión de cuentas).
Las cuentas se crean por registro público (mail institucional) o por consola
(create_admin.py); desde la app nadie crea cuentas.
  GET    /api/v1/usuarios?q=&rol=     → listar y buscar (SMOD y ADMIN)
  PATCH  /api/v1/usuarios/{id}        → cambiar el rango: ADMIN da MIEMBRO, MOD o SMOD;
                                        SMOD solo da o quita MOD (a MIEMBRO o MOD)
  POST   /api/v1/usuarios/{id}/ban    → suspender (días) o banear permanente (ADMIN)
  DELETE /api/v1/usuarios/{id}/ban    → levantar la suspensión (ADMIN)
Las cuentas ADMIN no se tocan desde la app. Todo cambio queda en el historial (se puede deshacer).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_smod
from app.models.usuario import RolEnum, Usuario
from app.schemas.common import PaginatedResponse
from app.schemas.usuario import CambioRol, Suspension, UsuarioRead
from app.services.auditoria import foto, registrar

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

CAMPOS_AUDITADOS = ("email", "rol", "activo", "baneado_hasta", "motivo_ban")
RANGOS_DE_SMOD = {RolEnum.MIEMBRO, RolEnum.MOD}


def _auditar(db: Session, usuario: Usuario, antes: dict, actor) -> None:
    registrar(db, "usuarios", usuario.id, "actualizacion", antes, foto(usuario, CAMPOS_AUDITADOS), actor)


def _no_admin(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if usuario.rol == RolEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Las cuentas ADMIN no se pueden modificar desde la app")
    return usuario


@router.get("/", response_model=PaginatedResponse[UsuarioRead])
def listar_usuarios(
    page: int = 1,
    page_size: int = 50,
    q: str = "",
    rol: RolEnum | None = None,
    db: Session = Depends(get_db),
    _smod=Depends(require_smod),
):
    """Lista usuarios (búsqueda por nombre o email)."""
    consulta = db.query(Usuario)
    if q.strip():
        patron = f"%{q.strip().lower()}%"
        consulta = consulta.filter(or_(Usuario.email.ilike(patron), Usuario.nombre.ilike(patron)))
    if rol:
        consulta = consulta.filter(Usuario.rol == rol)
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    total = consulta.count()
    usuarios = consulta.order_by(Usuario.nombre, Usuario.id).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(items=usuarios, total=total, page=page, page_size=page_size)


@router.get("/{usuario_id}", response_model=UsuarioRead)
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db), _smod=Depends(require_smod)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioRead)
def cambiar_rol(usuario_id: int, data: CambioRol, db: Session = Depends(get_db), actor=Depends(require_smod)):
    """ADMIN: MIEMBRO, MOD o SMOD. SMOD: solo da o quita MOD."""
    usuario = _no_admin(db, usuario_id)
    nuevo = RolEnum(data.rol)
    if actor.rol != RolEnum.ADMIN and (usuario.rol not in RANGOS_DE_SMOD or nuevo not in RANGOS_DE_SMOD):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Un SMOD solo puede dar o quitar el rango de moderador")
    antes = foto(usuario, CAMPOS_AUDITADOS)
    usuario.rol = nuevo
    _auditar(db, usuario, antes, actor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/{usuario_id}/ban", response_model=UsuarioRead)
def suspender(usuario_id: int, data: Suspension, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Con `dias`: suspensión temporal. Sin `dias`: baneo permanente."""
    usuario = _no_admin(db, usuario_id)
    antes = foto(usuario, CAMPOS_AUDITADOS)
    if data.dias:
        usuario.activo = True
        usuario.baneado_hasta = datetime.now(timezone.utc) + timedelta(days=data.dias)
    else:
        usuario.activo = False
        usuario.baneado_hasta = None
    usuario.motivo_ban = data.motivo.strip()
    _auditar(db, usuario, antes, admin)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}/ban", response_model=UsuarioRead)
def levantar_suspension(usuario_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    usuario = _no_admin(db, usuario_id)
    antes = foto(usuario, CAMPOS_AUDITADOS)
    usuario.activo, usuario.baneado_hasta, usuario.motivo_ban = True, None, None
    _auditar(db, usuario, antes, admin)
    db.commit()
    db.refresh(usuario)
    return usuario
