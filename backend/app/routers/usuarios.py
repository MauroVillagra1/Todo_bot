"""
Router de usuarios (gestión de cuentas, solo ADMIN).
Las cuentas se crean por registro público (mail institucional) o por consola
(create_admin.py); desde la app el ADMIN no crea cuentas. Puede:
  GET    /api/v1/usuarios?q=&rol=     → listar y buscar
  PATCH  /api/v1/usuarios/{id}        → dar o quitar el rango MOD
  POST   /api/v1/usuarios/{id}/ban    → suspender (días) o banear permanente (sin días)
  DELETE /api/v1/usuarios/{id}/ban    → levantar la suspensión
Las cuentas ADMIN no se tocan desde la app.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.usuario import RolEnum, Usuario
from app.schemas.common import PaginatedResponse
from app.schemas.usuario import CambioRol, Suspension, UsuarioRead

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


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
    _admin=Depends(require_admin),
):
    """Lista usuarios (búsqueda por nombre o email). Solo administradores."""
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
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioRead)
def cambiar_rol(usuario_id: int, data: CambioRol, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    """Da o quita el rango MOD (MIEMBRO ↔ MOD)."""
    usuario = _no_admin(db, usuario_id)
    usuario.rol = RolEnum(data.rol)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/{usuario_id}/ban", response_model=UsuarioRead)
def suspender(usuario_id: int, data: Suspension, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    """Con `dias`: suspensión temporal. Sin `dias`: baneo permanente."""
    usuario = _no_admin(db, usuario_id)
    if data.dias:
        usuario.activo = True
        usuario.baneado_hasta = datetime.now(timezone.utc) + timedelta(days=data.dias)
    else:
        usuario.activo = False
        usuario.baneado_hasta = None
    usuario.motivo_ban = data.motivo.strip()
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}/ban", response_model=UsuarioRead)
def levantar_suspension(usuario_id: int, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    usuario = _no_admin(db, usuario_id)
    usuario.activo, usuario.baneado_hasta, usuario.motivo_ban = True, None, None
    db.commit()
    db.refresh(usuario)
    return usuario
